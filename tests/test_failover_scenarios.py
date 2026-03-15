from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from structures.resources.events import GuiClusterSnapshotReadEvent
from structures.resources.membership import GroupEndpoint, JoinRequest, NodeRecord
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.serialization import encode_value, decode_value
from xenage.cluster.time_utils import utc_now

def setup_cluster(tmp_path: Path, node_ids: list[str]) -> list[ControlPlaneNode]:
    nodes = []
    for node_id in node_ids:
        node = ControlPlaneNode(node_id, tmp_path / node_id, [f"http://{node_id}:8734"])
        nodes.append(node)
    return nodes

def test_failover_scenarios(tmp_path: Path):
    # node_ids: cp-a, cp-b, cp-c. Sorted order is cp-a, cp-b, cp-c.
    nodes = setup_cluster(tmp_path, ["cp-a", "cp-b", "cp-c"])
    cp_a, cp_b, cp_c = nodes
    
    # 1. Initialize cluster with cp-a as leader
    initial = cp_a.initialize_group("group-1", 60)
    
    # 2. Add cp-b and cp-c
    token_b = cp_a.issue_bootstrap_token(60)
    token_c = cp_a.issue_bootstrap_token(60)
    
    state_b = cp_a.apply_join(JoinRequest(bootstrap_token=token_b, node=cp_b.node_record()), 60)
    state_c = cp_a.apply_join(JoinRequest(bootstrap_token=token_c, node=cp_c.node_record()), 60)
    
    for node in [cp_b, cp_c]:
        node.state_manager.replace_state(state_c, trusted_leader_pubkey=initial.leader_pubkey)
        # Sync event logs to match
        node.event_manager.current = cp_a.event_manager.current
        node.storage.save_control_plane_event_log(node.event_manager.current)

    # Scenarios helper
    async def run_failover_check(node, alive_nodes):
        # Mock client to simulate who is alive
        async def fake_get(url, path):
            node_id_from_url = url.split("//")[1].split(":")[0]
            if node_id_from_url not in alive_nodes:
                raise Exception(f"Connection failed to {node_id_from_url}")
            if path == "/v1/heartbeat":
                return encode_value({"status": "ok", "node_id": node_id_from_url})
            if "/v1/control-plane/events" in path:
                # Return empty page for simplicity if not implementing full sync mock
                from structures.resources.events import ControlPlaneEventPage
                return encode_value(ControlPlaneEventPage(items=[], has_more=False, last_event_id=node.event_manager.get_last_event_id()))
            return b""
        
        node.client.get = fake_get
        return await node.check_failover(60)

    # Scenario A: Leader is alive - NO failover
    expired = cp_b.state_manager.build_next_state(
        state_c.leader_node_id, state_c.leader_pubkey, state_c.control_planes, 
        state_c.runtimes, state_c.endpoints, -1, cp_a.key_pair
    )
    cp_b.state_manager.replace_state(expired)
    
    # We need to mock sync_control_plane_events as it's called if leader is alive
    async def fake_sync(*args, **kwargs): return None
    cp_b.sync_logic.sync_control_plane_events = fake_sync

    res = asyncio.run(run_failover_check(cp_b, ["cp-a", "cp-b", "cp-c"]))
    assert res is not None # It returns the state after sync
    assert res.leader_node_id == "cp-a" 
    
    # Scenario B: Leader (cp-a) is dead, next candidate (cp-b) promotes
    # We use a NEW expired state so cp-b doesn't think it already synced
    expired2 = cp_b.state_manager.build_next_state(
        state_c.leader_node_id, state_c.leader_pubkey, state_c.control_planes, 
        state_c.runtimes, state_c.endpoints, -1, cp_a.key_pair
    )
    cp_b.state_manager.replace_state(expired2)
    res = asyncio.run(run_failover_check(cp_b, ["cp-b", "cp-c"]))
    assert res is not None
    assert res.leader_node_id == "cp-b"
    assert res.leader_epoch == state_c.leader_epoch + 1

    # Scenario C: Leader (cp-a) and next candidate (cp-b) are dead, cp-c promotes
    # Reset cp-c state to be expired and pointing to cp-a
    expired3 = cp_c.state_manager.build_next_state(
        state_c.leader_node_id, state_c.leader_pubkey, state_c.control_planes, 
        state_c.runtimes, state_c.endpoints, -1, cp_a.key_pair
    )
    cp_c.state_manager.replace_state(expired3)
    res = asyncio.run(run_failover_check(cp_c, ["cp-c"]))
    assert res is not None
    assert res.leader_node_id == "cp-c"
    
    # Scenario D: Split-brain avoidance. cp-c sees cp-b is alive, so cp-c does NOT promote.
    # Reset cp-c state
    expired4 = cp_c.state_manager.build_next_state(
        state_c.leader_node_id, state_c.leader_pubkey, state_c.control_planes, 
        state_c.runtimes, state_c.endpoints, -1, cp_a.key_pair
    )
    cp_c.state_manager.replace_state(expired4)
    # cp-b is alive but NOT leader yet (it hasn't promoted in cp-c's view)
    res = asyncio.run(run_failover_check(cp_c, ["cp-b", "cp-c"]))
    assert res is None # cp-c waits for cp-b

def test_no_local_events_on_follower(tmp_path: Path):
    cp_a = ControlPlaneNode("cp-a", tmp_path / "cp-a", ["http://cp-a:8734"])
    cp_b = ControlPlaneNode("cp-b", tmp_path / "cp-b", ["http://cp-b:8734"])
    
    initial = cp_a.initialize_group("group-1", 60)
    token_b = cp_a.issue_bootstrap_token(60)
    state_b = cp_a.apply_join(JoinRequest(bootstrap_token=token_b, node=cp_b.node_record()), 60)
    
    cp_b.state_manager.replace_state(state_b, trusted_leader_pubkey=initial.leader_pubkey)
    
    # 1. Try to append event on follower
    last_event_id_before = cp_b.event_manager.get_last_event_id()
    cp_b.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="test-user"))
    assert cp_b.event_manager.get_last_event_id() == last_event_id_before
    
    # 2. Try to ensure admin user on follower (it should return existing if it exists, but not create new)
    # Pre-condition: cp-b has no user "new-admin"
    assert cp_b.user_state_manager.find_user("new-admin") is None
    
    try:
        cp_b.ensure_admin_user("new-admin", "some-pubkey")
    except Exception as e:
        assert "read-only mode" in str(e)
    
    assert cp_b.user_state_manager.find_user("new-admin") is None
    
    # 3. Promote cp-b and try again
    expired = cp_b.state_manager.build_next_state(
        state_b.leader_node_id, state_b.leader_pubkey, state_b.control_planes, 
        state_b.runtimes, state_b.endpoints, -1, cp_a.key_pair
    )
    cp_b.state_manager.replace_state(expired)
    
    # Mock to make failover succeed
    async def fake_get_fail(url, path): raise Exception("offline")
    cp_b.client.get = fake_get_fail
    
    promoted = asyncio.run(cp_b.check_failover(60))
    assert promoted.leader_node_id == "cp-b"
    
    # Now it should be able to append events
    cp_b.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="test-user"))
    assert cp_b.event_manager.get_last_event_id() > last_event_id_before
    
    # And create admin users
    user = cp_b.ensure_admin_user("new-admin", "some-pubkey")
    assert user.user_id == "new-admin"
    assert cp_b.user_state_manager.find_user("new-admin") is not None
