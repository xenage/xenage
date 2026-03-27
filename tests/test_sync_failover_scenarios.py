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
    state2_bytes = cp2.state_manager.state_payload(state2)
    state2_signature = cp3_key.sign(state2_bytes)
    
    # Event 2: GroupLeaderPromoted
    promo_event = {
        "event_id": 2,
        "event_type": "group.leader_promoted",
        "happened_at": "2026-03-15T12:05:00Z",
        "actor_node_id": "cp-3",
        "leader_node_id": "cp-3",
        "leader_pubkey": cp3_key.public_key_b64(),
        "leader_epoch": 2,
        "version": 2,
        "expires_at": state2.expires_at,
        "leader_signature": state2_signature
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
    await cp2.sync_logic.sync_on_startup()
    
    final_state = cp2.state_manager.get_state()
    assert final_state.leader_node_id == "cp-3"
    assert final_state.version == 2

@pytest.mark.asyncio
async def test_sync_stale_leader_skip(tmp_path):
    # CP-1 starts with state: leader=CP-2
    # CP-2 is DOWN
    # CP-3 is UP and is the NEW leader
    
    cp1_path = tmp_path / "cp1"
    cp1_path.mkdir()
    cp1 = ControlPlaneNode("cp-1", cp1_path, ["http://cp-1:8731"])
    
    cp2_key = Ed25519KeyPair.generate()
    cp2_pub = cp2_key.public_key_b64()
    cp3_key = Ed25519KeyPair.generate()
    cp3_pub = cp3_key.public_key_b64()

    # Initial state where CP-2 is leader
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_pub, endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_pub, endpoints=["http://cp-3:8733"])
    
    initial_state = GroupState(
        group_id="group-1",
        version=1,
        leader_epoch=1,
        leader_node_id="cp-2",
        leader_pubkey=cp2_pub,
        control_planes=[cp1.node_record(), cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8733"),
        ],
        expires_at="2026-03-15T12:00:00Z",
    )
    cp1.state_manager.replace_state(initial_state, trusted_leader_pubkey=cp2_pub, verify_signature_required=False)
    
    # State 2: CP-3 promoted
    state2 = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_pub,
        control_planes=initial_state.control_planes,
        runtimes=[],
        endpoints=initial_state.endpoints,
        expires_at="2026-03-15T12:10:00Z",
    )
    state2_signed = cp1.state_manager.sign_state(state2, cp3_key)

    promo_event_data = {
        "event_id": 2,
        "event_type": "group.leader_promoted",
        "happened_at": "2026-03-15T12:05:00Z",
        "actor_node_id": "cp-3",
        "leader_node_id": "cp-3",
        "leader_pubkey": cp3_pub,
        "leader_epoch": 2,
        "version": 2,
        "expires_at": state2.expires_at,
        "leader_signature": state2_signed.leader_signature
    }
    
    event_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_pub,
        leader_epoch=2,
        items=[promo_event_data],
        has_more=False,
        last_event_id=2
    )
    
    mock_responses = {
        "http://cp-2:8732": Exception("Connection refused"),
        "http://cp-3:8733": encode_value(event_page)
    }
    
    transport = MockTransport(mock_responses)
    cp1.client.get = transport.get
    cp1.client.post_json = transport.post_json
    
    await cp1.sync_logic.sync_on_startup()
    
    final_state = cp1.state_manager.get_state()
    assert final_state.leader_node_id == "cp-3"


@pytest.mark.asyncio
async def test_sync_startup_reconciles_state_when_event_ids_match(tmp_path):
    cp1_path = tmp_path / "cp1_equal_event_id"
    cp1_path.mkdir()
    cp1 = ControlPlaneNode("cp-1", cp1_path, ["http://cp-1:8731"])

    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    cp2_pub = cp2_key.public_key_b64()
    cp3_pub = cp3_key.public_key_b64()

    cp1_record = cp1.node_record()
    cp2_record = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_pub, endpoints=["http://cp-2:8732"])
    cp3_record = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_pub, endpoints=["http://cp-3:8733"])

    stale_state = GroupState(
        group_id="group-1",
        version=5,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=cp1_record.public_key,
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8731"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8732"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8733"),
        ],
        expires_at="2026-03-15T12:00:00Z",
    )
    stale_state_signed = cp1.state_manager.sign_state(stale_state, cp1.key_pair)
    cp1.state_manager.replace_state(stale_state_signed, trusted_leader_pubkey=cp1_record.public_key)

    # Build local event history up to id=12 so startup sync asks after_event_id=12.
    for _ in range(12):
        cp1.event_manager.record_group_state("cp-1", stale_state_signed)

    promoted_state = GroupState(
        group_id="group-1",
        version=6,
        leader_epoch=2,
        leader_node_id="cp-3",
        leader_pubkey=cp3_pub,
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=stale_state.endpoints,
        expires_at="2026-03-15T12:10:00Z",
    )
    promoted_state_signed = cp1.state_manager.sign_state(promoted_state, cp3_key)

    # Same event horizon as local node, but peer metadata reports new leader.
    same_id_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_pub,
        leader_epoch=2,
        items=[],
        has_more=False,
        last_event_id=12,
    )

    calls: dict[str, int] = {}

    async def get(url: str, path: str):
        base_path = path.partition("?")[0]
        key = f"{url}{base_path}"
        calls[key] = calls.get(key, 0) + 1

        if url == "http://cp-2:8732":
            raise Exception("Connection refused")

        if url == "http://cp-3:8733" and base_path == "/v1/control-plane/events":
            return encode_value(same_id_page)
        if url == "http://cp-3:8733" and base_path == "/v1/state/current":
            return encode_value(promoted_state_signed)
        raise Exception(f"unexpected call {url}{path}")

    async def post_json(url, path, body, response_type):
        return {"status": "ok"}

    cp1.client.get = get
    cp1.client.post_json = post_json

    await cp1.sync_logic.sync_on_startup()

    final_state = cp1.state_manager.get_state()
    assert final_state.leader_node_id == "cp-3"
    assert final_state.leader_epoch == 2
    assert final_state.version == 6
    assert calls.get("http://cp-3:8733/v1/state/current", 0) >= 1
