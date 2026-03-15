from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from structures.resources.membership import GuiConnectionConfig, GuiUserBootstrapRequest, GroupEndpoint, JoinRequest, RequestAuth
from structures.resources.events import GuiClusterSnapshotReadEvent, ControlPlaneEventPage
from xenage.crypto import Ed25519KeyPair
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.serialization import encode_value, decode_value
from xenage.cluster.time_utils import utc_now

def setup_cluster(tmp_path: Path, node_ids: list[str]) -> list[ControlPlaneNode]:
    nodes = []
    for node_id in node_ids:
        # Use different ports for each node in mock URLs
        port = 8734 + len(nodes)
        node = ControlPlaneNode(node_id, tmp_path / node_id, [f"http://{node_id}:{port}"])
        nodes.append(node)
    return nodes

class MockCluster:
    def __init__(self, nodes: list[ControlPlaneNode]):
        self.nodes = {n.identity.node_id: n for n in nodes}
        self.offline_nodes: set[str] = set()
        
        for node in nodes:
            node.client.get = self.make_get(node)
            node.client.post_json = self.make_post(node)

    def make_get(self, requester: ControlPlaneNode):
        async def mock_get(url: str, path: str) -> bytes:
            node_id = url.split("//")[1].split(":")[0]
            if node_id in self.offline_nodes:
                raise Exception(f"Connection failed to {node_id}")
            
            target = self.nodes.get(node_id)
            if not target:
                raise Exception(f"Unknown node {node_id}")

            if "/v1/control-plane/events" in path:
                # Parse query params
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(path).query)
                after_id = int(query.get("after_event_id", [0])[0])
                limit = int(query.get("limit", [250])[0])
                
                state = target.state_manager.get_state()
                page = target.event_manager.event_page(
                    state.leader_node_id,
                    after_id,
                    limit
                )
                
                # Mock page needs more fields now
                from structures.resources.events import ControlPlaneEventPage
                page = ControlPlaneEventPage(
                    leader_node_id=state.leader_node_id,
                    leader_pubkey=state.leader_pubkey,
                    leader_epoch=state.leader_epoch,
                    last_event_id=page.last_event_id,
                    items=page.items,
                    has_more=page.has_more
                )
                
                return encode_value(page)
            
            if path == "/v1/heartbeat":
                return encode_value({"status": "ok", "node_id": node_id})
            
            raise Exception(f"Mock GET not implemented for {path}")
        return mock_get

    def make_post(self, requester: ControlPlaneNode):
        async def mock_post(url: str, path: str, body: Any, response_type: type) -> Any:
            node_id = url.split("//")[1].split(":")[0]
            if node_id in self.offline_nodes:
                raise Exception(f"Connection failed to {node_id}")
            
            target = self.nodes.get(node_id)
            if not target:
                raise Exception(f"Unknown node {node_id}")

            # Note: In a real node, handle_request would route this.
            # Here we manually dispatch to node methods for simplicity of testing logic.
            
            # This is a bit of a hack but avoids setting up a full HTTP server
            auth = requester.identity.node_id # Simplified auth
            
            if path == "/v1/join":
                # We need to call target.handle_request or target.apply_join
                # handle_request requires more setup, so let's use apply_join directly if it's a join
                from structures.resources.membership import JoinResponse
                try:
                    res_state = target.apply_join(body, 60)
                    return JoinResponse(accepted=True, group_state=res_state)
                except Exception as e:
                    return JoinResponse(accepted=False, reason=str(e))
            
            if path == "/v1/control-plane/sync-status":
                target.upsert_sync_status(requester.identity.node_id, body.status, body.reason)
                return {}

            raise Exception(f"Mock POST not implemented for {path}")
        return mock_post

@pytest.mark.asyncio
async def test_sync_after_downtime(tmp_path: Path):
    # node_ids: cp-a, cp-b, cp-c. Sorted order is cp-a, cp-b, cp-c.
    nodes = setup_cluster(tmp_path, ["cp-a", "cp-b", "cp-c"])
    cluster = MockCluster(nodes)
    cp_a, cp_b, cp_c = nodes
    
    # 1. Initialize cluster with cp-a as leader
    initial_state = cp_a.initialize_group("group-1", 60)
    
    # 2. Add cp-b and cp-c
    token_b = cp_a.issue_bootstrap_token(60)
    token_c = cp_a.issue_bootstrap_token(60)
    
    # Join cp-b
    state_b = await cp_b.join_peer(cp_a.endpoints[0], initial_state.leader_pubkey, token_b)
    # Join cp-c
    state_c = await cp_c.join_peer(cp_a.endpoints[0], initial_state.leader_pubkey, token_c)
    
    # Manually sync followers after joining to ensure they have all history
    await cp_b.sync_control_plane_events()
    await cp_c.sync_control_plane_events()
    
    # Verify all nodes are in sync
    assert cp_a.event_manager.get_last_event_id() == cp_b.event_manager.get_last_event_id()
    assert cp_a.event_manager.get_last_event_id() == cp_c.event_manager.get_last_event_id()
    
    # 3. Take cp-c offline
    cluster.offline_nodes.add("cp-c")
    
    # 4. Perform updates on leader cp-a
    # Append some events
    cp_a.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="admin"))
    cp_a.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="admin"))
    admin_key = Ed25519KeyPair.generate()
    bootstrap_request = GuiUserBootstrapRequest(
        bootstrap_token=cp_a.issue_gui_bootstrap_token(60),
        user_id="admin",
        public_key=admin_key.public_key_b64(),
        control_plane_urls=[cp_a.endpoints[0]],
    )
    response = await cp_a.handle_request(
        "POST",
        "/v1/gui/bootstrap-user",
        encode_value(bootstrap_request),
        RequestAuth(node_id="", timestamp=0, nonce="", signature=""),
        "",
    )
    config = GuiConnectionConfig(
        cluster_name=response.cluster_name,
        control_plane_urls=response.control_plane_urls,
        user_id=response.user_id,
        role=response.role,
        public_key=response.public_key,
        private_key=admin_key.private_key_b64(),
    )
    
    # Sync cp-b
    await cp_b.sync_control_plane_events()
    
    last_id_a = cp_a.event_manager.get_last_event_id()
    assert cp_b.event_manager.get_last_event_id() == last_id_a
    assert cp_c.event_manager.get_last_event_id() < last_id_a
    synced_admin_b = cp_b.user_state_manager.find_user("admin")
    assert synced_admin_b is not None
    assert synced_admin_b.public_key == config.public_key
    assert cp_c.user_state_manager.find_user("admin") is None
    
    # 5. Bring cp-c back online
    cluster.offline_nodes.remove("cp-c")
    
    # 6. cp-c synchronizes
    await cp_c.sync_control_plane_events()
    
    # 7. Verify cp-c is now in sync
    assert cp_c.event_manager.get_last_event_id() == last_id_a
    synced_admin_c = cp_c.user_state_manager.find_user("admin")
    assert synced_admin_c is not None
    assert synced_admin_c.public_key == config.public_key
    logger.info("Sync after downtime successful")

@pytest.mark.asyncio
async def test_runtime_update_on_promoted_leader(tmp_path: Path):
    nodes = setup_cluster(tmp_path, ["cp-a", "cp-b", "cp-c"])
    cluster = MockCluster(nodes)
    cp_a, cp_b, cp_c = nodes
    
    # 1. Initialize and join
    initial_state = cp_a.initialize_group("group-1", 60)
    token_b = cp_a.issue_bootstrap_token(60)
    token_c = cp_a.issue_bootstrap_token(60)
    await cp_b.join_peer(cp_a.endpoints[0], initial_state.leader_pubkey, token_b)
    await cp_c.join_peer(cp_a.endpoints[0], initial_state.leader_pubkey, token_c)
    
    # Sync followers
    await cp_b.sync_control_plane_events()
    await cp_c.sync_control_plane_events()
    
    # Capture cp-a's public key for later use (needed for trusted_leader_pubkey)
    cp_a_pubkey = cp_a.key_pair.public_key
    
    # 2. Kill leader cp-a
    cluster.offline_nodes.add("cp-a")
    
    # 3. Trigger failover on cp-b (it's the next candidate after cp-a)
    # We need to make the state expired to trigger failover
    current_state = cp_b.state_manager.get_state()
    # Expire state on all nodes to trigger failover
    for node in [cp_b, cp_c]:
        expired_state = node.state_manager.build_next_state(
            current_state.leader_node_id, current_state.leader_pubkey, 
            current_state.control_planes, current_state.runtimes, 
            current_state.endpoints, -1, cp_a.key_pair
        )
        node.state_manager.replace_state(expired_state)
    
    # cp-b promotes itself
    promoted_state = await cp_b.check_failover(60)
    assert promoted_state.leader_node_id == "cp-b"
    
    # Now cp-c needs to find out cp-b is leader. 
    # check_failover on cp-c will try to contact cp-a (dead), then see cp-b is next candidate.
    # It will contact cp-b and should get cp-b's promoted state.
    # We pass trusted_leader_pubkey because we know the OLD leader's pubkey and allow the NEXT candidate to promote.
    res_c = await cp_c.sync_logic.sync_events_from_urls([cp_b.endpoints[0]], trusted_leader_pubkey=cp_a_pubkey)
    assert res_c is not None
    assert res_c.leader_node_id == "cp-b"
    
    # Verify cp-c's state manager now has the new leader
    assert cp_c.state_manager.get_state().leader_node_id == "cp-b"
    
    # 4. Perform updates on the NEW leader cp-b
    # Add a user
    user = cp_b.ensure_admin_user("new-admin", "pubkey-123")
    assert user.user_id == "new-admin"
    
    # Update node endpoints
    new_endpoints = ["http://cp-b:9000"]
    updated_state = cp_b.update_node_endpoints("cp-b", new_endpoints, 60)
    
    # Verify updates are recorded locally on cp-b
    assert cp_b.user_state_manager.find_user("new-admin") is not None
    # Check endpoints in updated state
    cp_b_endpoints = [e.url for e in updated_state.endpoints if e.node_id == "cp-b"]
    assert new_endpoints[0] in cp_b_endpoints
    
    # 5. Sync cp-c from new leader cp-b
    # Sync events to get the user and endpoint updates
    await cp_c.sync_control_plane_events()
    
    # 6. Verify cp-c has the updates
    assert cp_c.user_state_manager.find_user("new-admin") is not None
    cp_c_state = cp_c.state_manager.get_state()
    cp_c_cp_b_endpoints = [e.url for e in cp_c_state.endpoints if e.node_id == "cp-b"]
    assert new_endpoints[0] in cp_c_cp_b_endpoints
    
    logger.info("Runtime updates on promoted leader successful")
