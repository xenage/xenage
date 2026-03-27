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
async def test_split_brain_recovery_on_startup(tmp_path):
    # Scenario:
    # 3 nodes: cp-1, cp-2, cp-3. Order: cp-1, cp-2, cp-3
    # Initially cp-1 is leader (epoch 1).
    # A and B (cp-1 and cp-2) go down.
    # C (cp-3) promotes itself to leader (epoch 2).
    # B (cp-2) comes back up.
    # It should sync from C and see C as leader.
    # If it fails to sync from C, it might wrongly promote itself because it's next in line after A.

    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()

    cp1_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8731"])
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8733"])

    # Initial state: cp-1 is leader
    state1 = GroupState(
        group_id="group-1",
        version=1,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=cp1_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8733"),
        ],
        expires_at="2020-01-01T00:00:00Z", # Already expired
    )
    
    # Setup cp-2 with this initial state
    cp2_path = tmp_path / "cp2"
    cp2_path.mkdir()
    # We need to manually save the identity so it uses the same key
    from structures.resources.membership import StoredNodeIdentity
    from xenage.persistence.storage_layer import StorageLayer
    storage2 = StorageLayer(cp2_path)
    storage2.save_identity(StoredNodeIdentity(
        node_id="cp-2",
        role="control-plane",
        public_key=cp2_key.public_key_b64(),
        private_key=cp2_key.private_key_b64(),
        endpoints=["http://cp-2:8732"]
    ))
    
    cp2 = ControlPlaneNode("cp-2", cp2_path, ["http://cp-2:8732"])
    # Verify cp-2 has the correct identity
    assert cp2.identity.public_key == cp2_key.public_key_b64()
    
    # Set state1 in cp-2
    state1_signed = cp2.state_manager.sign_state(state1, cp1_key)
    cp2.state_manager.replace_state(state1_signed, trusted_leader_pubkey=cp1_key.public_key_b64())

    # cp-3 promoted itself to epoch 2
    state2 = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=state1.endpoints,
        expires_at=now_iso(60),
    )
    state2_signed_by_cp3 = cp2.state_manager.sign_state(state2, cp3_key)
    
    # Event for promotion
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
        "leader_signature": state2_signed_by_cp3.leader_signature
    }
    
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[promo_event],
        has_more=False,
        last_event_id=2
    )

    # Mock responses for cp-2
    # cp-1 is down
    # cp-3 is UP and has the new state
    mock_responses = {
        "http://cp-1:8731": Exception("Connection refused"),
        "http://cp-3:8733": encode_value(event_page),
    }
    
    transport = MockTransport(mock_responses)
    cp2.client.get = transport.get
    cp2.client.post_json = transport.post_json
    
    # 1. Simulate startup sync
    await cp2.sync_logic.sync_on_startup()
    
    # Verify B (cp-2) now sees C (cp-3) as leader
    state = cp2.state_manager.get_state()
    assert state.leader_node_id == "cp-3"
    assert state.leader_epoch == 2
    
    # 2. Simulate periodic check_failover
    # Since B sees C is alive and is leader, it should NOT promote itself
    await cp2.check_failover(ttl_seconds=60)
    
    state = cp2.state_manager.get_state()
    assert state.leader_node_id == "cp-3", "B should still see C as leader"
    assert not cp2.is_leader(), "B should NOT be leader"

@pytest.mark.asyncio
async def test_split_brain_failed_sync_on_startup(tmp_path):
    # Same as above, but B (cp-2) is the NEXT candidate after A (cp-1).
    # CP-2 starts, CP-1 is dead. 
    # CP-2 thinks it's its turn to promote because it's the next in deterministic order!
    # Even if CP-3 (C) has ALREADY promoted itself, CP-2 might promote itself too if it doesn't sync from C first.
    
    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()

    cp1_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8731"])
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8733"])

    state1 = GroupState(
        group_id="group-1",
        version=1,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=cp1_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8733"),
        ],
        expires_at="2020-01-01T00:00:00Z", # Expired
    )
    
    cp2_path = tmp_path / "cp2_fail"
    cp2_path.mkdir()
    from structures.resources.membership import StoredNodeIdentity
    from xenage.persistence.storage_layer import StorageLayer
    storage2 = StorageLayer(cp2_path)
    storage2.save_identity(StoredNodeIdentity(
        node_id="cp-2",
        role="control-plane",
        public_key=cp2_key.public_key_b64(),
        private_key=cp2_key.private_key_b64(),
        endpoints=["http://cp-2:8732"]
    ))
    
    cp2 = ControlPlaneNode("cp-2", cp2_path, ["http://cp-2:8732"])
    state1_signed = cp2.state_manager.sign_state(state1, cp1_key)
    cp2.state_manager.replace_state(state1_signed, trusted_leader_pubkey=cp1_key.public_key_b64())

    # cp-3 promoted itself to epoch 2
    state2 = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=state1.endpoints,
        expires_at=now_iso(60),
    )
    state2_signed_by_cp3 = cp2.state_manager.sign_state(state2, cp3_key)
    
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
        "leader_signature": state2_signed_by_cp3.leader_signature
    }
    
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[promo_event],
        has_more=False,
        last_event_id=2
    )

    # Mock: cp-1 down, but cp-3 is UP and has the new state
    mock_responses = {
        "http://cp-1:8731": Exception("Connection refused"),
        "http://cp-3:8733": encode_value(event_page),
    }
    
    transport = MockTransport(mock_responses)
    cp2.client.get = transport.get
    cp2.client.post_json = transport.post_json
    
    # Simulate that sync_on_startup was skipped or failed
    # Then Periodic failover check
    # CP-2 sees CP-1 is dead. It is the NEXT candidate in deterministic order (cp-1, cp-2, cp-3)
    # We want to ensure it DOES NOT promote itself if it can reach cp-3.
    await cp2.check_failover(ttl_seconds=60)
    
    # B (cp-2) should see C (cp-3) as leader, NOT promote itself.
    state = cp2.state_manager.get_state()
    assert state.leader_node_id == "cp-3", f"B should have synced from C, but it's leader is {state.leader_node_id}"
    assert state.leader_epoch == 2
    assert not cp2.is_leader(), "B should NOT be leader"
