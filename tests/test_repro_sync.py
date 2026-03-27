import asyncio
import pytest
import time
from pathlib import Path
from xenage.nodes.control_plane.main import ControlPlaneNode
from structures.resources.membership import NodeRecord, GroupEndpoint, GroupState
from structures.resources.events import ControlPlaneEventPage
from xenage.crypto import Ed25519KeyPair
from xenage.serialization import encode_value
from xenage.cluster.time_utils import utc_now, format_timestamp
from datetime import timedelta
import os

def now_iso(seconds: int = 0) -> str:
    return format_timestamp(utc_now() + timedelta(seconds=seconds))

class MockTransport:
    def __init__(self, urls_to_responses):
        self.urls_to_responses = urls_to_responses
        self.call_count = {}

    async def get(self, url, path):
        full_url = f"{url}{path}"
        self.call_count[full_url] = self.call_count.get(full_url, 0) + 1
        if url in self.urls_to_responses:
            res = self.urls_to_responses[url]
            if isinstance(res, Exception):
                raise res
            return res
        raise Exception(f"Connection refused to {url}")

    async def post_json(self, url, path, body, response_type):
        return {"status": "ok"}

@pytest.mark.asyncio
async def test_cp2_fails_to_sync_from_cp3_after_failover(tmp_path):
    # Scenario:
    # 3 nodes: cp-1, cp-2, cp-3.
    # 1. cp-1 is initial leader (epoch 1).
    # 2. cp-1 and cp-2 go down.
    # 3. cp-3 promotes itself to leader (epoch 2) because all peers are down.
    # 4. cp-2 comes back up.
    # 5. cp-2 tries to sync from cp-3.
    # 6. Expectation: cp-2 succeeds in syncing and accepts cp-3 as leader.
    # 7. Reported failure: cp-2 fails with "leader signature validation failed".

    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()

    cp1_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://control-plane-1:8734"])
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://control-plane-2:8736"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://control-plane-3:8737"])

    # Node records with different keys for CP-3 (simulating rotating keys if that's the issue,
    # though here we just need to make sure we have the same key in the initial state)
    cp3_key_initial = Ed25519KeyPair.generate()
    cp3_record_initial = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key_initial.public_key_b64(), endpoints=["http://control-plane-3:8737"])

    # Initial state: cp-1 is leader
    state1 = GroupState(
        group_id="group-1",
        version=1,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=cp1_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record_initial],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://control-plane-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://control-plane-2:8736"),
            GroupEndpoint(node_id="cp-3", url="http://control-plane-3:8737"),
        ],
        expires_at=now_iso(300), 
    )
    
    # Setup cp-2 with this initial state
    cp2_path = tmp_path / "cp2"
    cp2_path.mkdir()
    from structures.resources.membership import StoredNodeIdentity
    from xenage.persistence.storage_layer import StorageLayer
    storage2 = StorageLayer(cp2_path)
    storage2.save_identity(StoredNodeIdentity(
        node_id="cp-2",
        role="control-plane",
        public_key=cp2_key.public_key_b64(),
        private_key=cp2_key.private_key_b64(),
        endpoints=["http://control-plane-2:8736"]
    ))
    
    cp2 = ControlPlaneNode("cp-2", cp2_path, ["http://control-plane-2:8736"])
    # Set state1 in cp-2 (as if it was already in its database)
    state1_signed = cp2.state_manager.sign_state(state1, cp1_key)
    cp2.state_manager.replace_state(state1_signed, trusted_leader_pubkey=cp1_key.public_key_b64())

    # Now cp-3 promotes itself.
    # State 2: cp-3 is leader, epoch 2, version 2.
    state2 = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=state1.endpoints,
        expires_at=now_iso(300),
    )
    state2_signed_by_cp3 = cp2.state_manager.sign_state(state2, cp3_key)
    
    # Events for promotion
    # Event 1: some dummy event (e.g. state sync)
    event1 = {
        "event_id": 1,
        "event_type": "group.endpoints_updated",
        "happened_at": now_iso(-10),
        "actor_node_id": "cp-1",
        "node_id": "cp-1",
        "endpoints": state1.endpoints,
        "version": 1,
        "expires_at": state1.expires_at,
    }

    # Event 2: promotion
    promo_event = {
        "event_id": 2,
        "event_type": "group.leader_promoted",
        "happened_at": now_iso(),
        "actor_node_id": "cp-3",
        "leader_node_id": "cp-3",
        "leader_pubkey": cp3_key.public_key_b64(),
        "leader_epoch": 2,
        "version": 2,
        "expires_at": state2.expires_at,
        "leader_signature": state2_signed_by_cp3.leader_signature,
        "control_planes": [cp1_record, cp2_record, cp3_record],
        "endpoints": state1.endpoints,
    }
    
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[event1, promo_event],
        has_more=False,
        last_event_id=2
    )

    # Mock responses for cp-2
    mock_responses = {
        "http://control-plane-1:8734": Exception("Connection refused"),
        "http://control-plane-3:8737": encode_value(event_page),
    }
    
    transport = MockTransport(mock_responses)
    cp2.client.get = transport.get
    cp2.client.post_json = transport.post_json
    
    # cp-2 tries to sync
    print("\nStarting sync on cp-2...")
    await cp2.sync_logic.sync_on_startup()
    
    # Verify result
    state = cp2.state_manager.get_state()
    print(f"Final leader: {state.leader_node_id}, epoch: {state.leader_epoch}, version: {state.version}")
    
    assert state.leader_node_id == "cp-3"
    assert state.leader_epoch == 2
    assert state.version == 2
