import asyncio
import pytest
from pathlib import Path
from xenage.nodes.control_plane.main import ControlPlaneNode
from structures.resources.membership import NodeRecord, GroupEndpoint, GroupState
from structures.resources.events import ControlPlaneEventPage
from xenage.crypto import Ed25519KeyPair
from xenage.serialization import encode_value

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
async def test_failover_sync_signature_validation(tmp_path):
    # Scenario:
    # 3 nodes: cp-1 (leader), cp-2, cp-3
    # cp-2 goes down.
    # cp-1 goes down.
    # cp-3 promotes itself (epoch 2).
    # cp-2 comes up. It still thinks cp-1 is leader (epoch 1).
    # cp-2 tries to sync from cp-3.
    # It receives GroupLeaderPromotedEvent (cp-3, epoch 2).
    
    cp2_path = tmp_path / "cp2"
    cp2_path.mkdir()
    cp2 = ControlPlaneNode("cp-2", cp2_path, ["http://cp-2:8732"])
    
    cp1_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    
    cp1_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8731"])
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2.node_record().public_key, endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8733"])
    
    # State 1: cp-1 is leader
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
        expires_at="2026-03-15T12:00:00Z",
    )
    # Sign it by cp-1
    state1 = cp2.state_manager.sign_state(state1, cp1_key)
    cp2.state_manager.replace_state(state1, trusted_leader_pubkey=cp1_key.public_key_b64())
    
    # cp-3 promotes itself to epoch 2, version 2
    state2 = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=state1.endpoints,
        expires_at="2026-03-15T12:10:00Z",
    )
    # cp-3 signs it
    state2_signed = cp2.state_manager.sign_state(state2, cp3_key)
    
    # Event 2: GroupLeaderPromoted
    promo_event = {
        "event_id": 1,
        "event_type": "group.leader_promoted",
        "happened_at": "2026-03-15T12:05:00Z",
        "actor_node_id": "cp-3",
        "leader_node_id": "cp-3",
        "leader_pubkey": cp3_key.public_key_b64(),
        "leader_epoch": 2,
        "version": 2,
        "expires_at": state2.expires_at,
        "leader_signature": state2_signed.leader_signature
    }
    
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[promo_event],
        has_more=False,
        last_event_id=2
    )
    
    mock_responses = {
        "http://cp-3:8733": encode_value(event_page)
    }
    
    transport = MockTransport(mock_responses)
    cp2.client.get = transport.get
    cp2.client.post_json = transport.post_json
    
    # Trigger sync from cp-3
    print("Triggering sync from cp-3...")
    # Note: sync_on_startup will try all peers
    await cp2.sync_logic.sync_on_startup()
    
    final_state = cp2.state_manager.get_state()
    print(f"Final leader: {final_state.leader_node_id}, version: {final_state.version}")
    
    assert final_state.leader_node_id == "cp-3"
    assert final_state.version == 2


@pytest.mark.asyncio
async def test_failover_sync_uses_promoted_event_snapshot_for_signature_validation(tmp_path):
    cp2_path = tmp_path / "cp2_snapshot"
    cp2_path.mkdir()
    cp2 = ControlPlaneNode("cp-2", cp2_path, ["http://cp-2:8732"])

    cp1_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()

    cp1_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8731"])
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2.node_record().public_key, endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8733"])

    stale_state = GroupState(
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
        expires_at="2026-03-15T12:00:00Z",
    )
    stale_state = cp2.state_manager.sign_state(stale_state, cp1_key)
    cp2.state_manager.replace_state(stale_state, trusted_leader_pubkey=cp1_key.public_key_b64())

    # Local follower membership is stale (cp-3 endpoint differs from promoted leader's signed state).
    divergent_local = GroupState(
        group_id=stale_state.group_id,
        version=stale_state.version,
        leader_epoch=stale_state.leader_epoch,
        leader_node_id=stale_state.leader_node_id,
        leader_pubkey=stale_state.leader_pubkey,
        control_planes=stale_state.control_planes,
        runtimes=stale_state.runtimes,
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:9999"),
        ],
        expires_at=stale_state.expires_at,
        leader_signature=stale_state.leader_signature,
    )
    cp2.state_manager.current_state = divergent_local
    cp2.storage.save_group_state(divergent_local)

    promoted_state = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8733"),
        ],
        expires_at="2026-03-15T12:10:00Z",
    )
    promoted_state = cp2.state_manager.sign_state(promoted_state, cp3_key)

    promo_event = {
        "event_id": 2,
        "event_type": "group.leader_promoted",
        "happened_at": "2026-03-15T12:05:00Z",
        "actor_node_id": "cp-3",
        "nonce": "promotion-nonce",
        "leader_node_id": "cp-3",
        "leader_pubkey": cp3_key.public_key_b64(),
        "leader_epoch": 2,
        "version": 2,
        "expires_at": promoted_state.expires_at,
        "leader_signature": promoted_state.leader_signature,
        "control_planes": promoted_state.control_planes,
        "runtimes": promoted_state.runtimes,
        "endpoints": promoted_state.endpoints,
        "node_statuses": promoted_state.node_statuses,
    }
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[promo_event],
        has_more=False,
        last_event_id=1,
        last_event_nonce="promotion-nonce",
    )

    transport = MockTransport({"http://cp-3:9999": encode_value(event_page)})
    cp2.client.get = transport.get
    cp2.client.post_json = transport.post_json

    await cp2.sync_logic.sync_on_startup()
    final_state = cp2.state_manager.get_state()
    assert final_state.leader_node_id == "cp-3"
    assert final_state.version == 2
    cp3_endpoints = [item.url for item in final_state.endpoints if item.node_id == "cp-3"]
    assert cp3_endpoints == ["http://cp-3:8733"]
