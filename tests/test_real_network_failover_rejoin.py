from __future__ import annotations

import asyncio
import socket
import threading
from pathlib import Path

import pytest

from structures.resources.events import GuiClusterSnapshotReadEvent, UserEventAppendedEvent, UserUpsertedEvent
from structures.resources.membership import GuiConnectionConfig, GuiUserBootstrapRequest, RequestAuth
from xenage.crypto import Ed25519KeyPair
from xenage.network.http_transport import NodeHTTPServer, SignedTransportClient
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.nodes.runtime import RuntimeNode
from xenage.serialization import encode_value

_RESERVED_PORTS: set[int] = set()
_PORT_LOCK = threading.Lock()


def free_port() -> int:
    while True:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with _PORT_LOCK:
            if port in _RESERVED_PORTS:
                continue
            _RESERVED_PORTS.add(port)
            return port


def start_server(node: ControlPlaneNode, port: int) -> tuple[NodeHTTPServer, threading.Thread]:
    server = NodeHTTPServer("127.0.0.1", port, node)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.wait_until_ready()
    return server, thread


def stop_server(server: NodeHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=2)


def assert_strict_seqnos(node: ControlPlaneNode) -> None:
    event_ids = [item.event_id for item in node.event_manager.current.items]
    if event_ids:
        assert event_ids == list(range(1, len(event_ids) + 1))
    user_sequences = [item.sequence for item in node.user_state_manager.get_state().event_log]
    if user_sequences:
        assert user_sequences == list(range(1, len(user_sequences) + 1))


async def bootstrap_gui_config(leader: ControlPlaneNode, leader_url: str, user_id: str = "admin") -> GuiConnectionConfig:
    user_key = Ed25519KeyPair.generate()
    request = GuiUserBootstrapRequest(
        bootstrap_token=leader.issue_gui_bootstrap_token(60),
        user_id=user_id,
        public_key=user_key.public_key_b64(),
        control_plane_urls=[leader_url],
    )
    response = await leader.handle_request(
        "POST",
        "/v1/gui/bootstrap-user",
        encode_value(request),
        RequestAuth(node_id="", timestamp=0, nonce="", signature=""),
        "",
    )
    return GuiConnectionConfig(
        cluster_name=response.cluster_name,
        control_plane_urls=response.control_plane_urls,
        user_id=response.user_id,
        role=response.role,
        public_key=response.public_key,
        private_key=user_key.private_key_b64(),
    )


@pytest.mark.asyncio
async def test_real_network_failover_and_rejoin_preserves_single_leader(tmp_path: Path) -> None:
    cp1_port = free_port()
    cp2_port = free_port()
    cp3_port = free_port()

    cp1_url = f"http://127.0.0.1:{cp1_port}"
    cp2_url = f"http://127.0.0.1:{cp2_port}"
    cp3_url = f"http://127.0.0.1:{cp3_port}"

    cp1_path = tmp_path / "cp-1"
    cp2_path = tmp_path / "cp-2"
    cp3_path = tmp_path / "cp-3"
    rn1_path = tmp_path / "rn-1"
    rn2_path = tmp_path / "rn-2"

    cp1 = ControlPlaneNode("cp-1", cp1_path, [cp1_url])
    cp2 = ControlPlaneNode("cp-2", cp2_path, [cp2_url])
    cp3 = ControlPlaneNode("cp-3", cp3_path, [cp3_url])
    rn1 = RuntimeNode("rn-1", rn1_path)
    rn2 = RuntimeNode("rn-2", rn2_path)

    cp1_server, cp1_thread = start_server(cp1, cp1_port)
    cp2_server, cp2_thread = start_server(cp2, cp2_port)
    cp3_server, cp3_thread = start_server(cp3, cp3_port)

    cp1_restarted_server: NodeHTTPServer | None = None
    cp1_restarted_thread: threading.Thread | None = None
    try:
        initial = cp1.initialize_group("group-real-network", 60)
        token_b = cp1.issue_bootstrap_token(120)
        token_c = cp1.issue_bootstrap_token(120)
        token_r1 = cp1.issue_bootstrap_token(120)
        token_r2 = cp1.issue_bootstrap_token(120)

        await cp2.join_peer(cp1_url, initial.leader_pubkey, token_b)
        await cp3.join_peer(cp1_url, initial.leader_pubkey, token_c)
        await rn1.connect(cp1_url, initial.leader_pubkey, token_r1)
        await rn2.connect(cp1_url, initial.leader_pubkey, token_r2)

        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()
        assert cp2.state_manager.require_state().leader_node_id == "cp-1"
        assert cp3.state_manager.require_state().leader_node_id == "cp-1"

        # Kill current leader.
        stop_server(cp1_server, cp1_thread)

        # Force expiration to trigger failover.
        state_b = cp2.state_manager.require_state()
        expired_b = cp2.state_manager.build_next_state(
            state_b.leader_node_id,
            state_b.leader_pubkey,
            state_b.control_planes,
            state_b.runtimes,
            state_b.endpoints,
            -1,
            cp1.key_pair,
        )
        cp2.state_manager.replace_state(expired_b)

        state_c = cp3.state_manager.require_state()
        expired_c = cp3.state_manager.build_next_state(
            state_c.leader_node_id,
            state_c.leader_pubkey,
            state_c.control_planes,
            state_c.runtimes,
            state_c.endpoints,
            -1,
            cp1.key_pair,
        )
        cp3.state_manager.replace_state(expired_c)

        promoted = await cp2.check_failover(60)
        assert promoted is not None
        assert promoted.leader_node_id == "cp-2"

        # cp-3 learns cp-2 as leader via normal event sync.
        await cp3.sync_control_plane_events(preferred_leader_url=cp2_url)
        assert cp3.state_manager.require_state().leader_node_id == "cp-2"

        # Bring cp-1 back from disk and ensure it converges to cp-2 leader.
        cp1_restarted = ControlPlaneNode("cp-1", cp1_path, [cp1_url])
        cp1_restarted_server, cp1_restarted_thread = start_server(cp1_restarted, cp1_port)

        synced = await cp1_restarted.sync_logic.sync_on_startup()
        assert synced is not None
        assert synced.leader_node_id == "cp-2"
        assert cp1_restarted.state_manager.require_state().leader_node_id == "cp-2"

        leaders = {
            cp2.state_manager.require_state().leader_node_id,
            cp3.state_manager.require_state().leader_node_id,
            cp1_restarted.state_manager.require_state().leader_node_id,
        }
        assert leaders == {"cp-2"}
    finally:
        if cp1_restarted_server is not None and cp1_restarted_thread is not None:
            stop_server(cp1_restarted_server, cp1_restarted_thread)
        stop_server(cp2_server, cp2_thread)
        stop_server(cp3_server, cp3_thread)


@pytest.mark.asyncio
async def test_restarted_stale_leader_does_not_renew_if_peer_has_newer_term(tmp_path: Path) -> None:
    cp1_port = free_port()
    cp2_port = free_port()
    cp3_port = free_port()

    cp1_url = f"http://127.0.0.1:{cp1_port}"
    cp2_url = f"http://127.0.0.1:{cp2_port}"
    cp3_url = f"http://127.0.0.1:{cp3_port}"

    cp1_path = tmp_path / "cp-1-stale"
    cp2_path = tmp_path / "cp-2-stale"
    cp3_path = tmp_path / "cp-3-stale"

    cp1 = ControlPlaneNode("cp-1", cp1_path, [cp1_url])
    cp2 = ControlPlaneNode("cp-2", cp2_path, [cp2_url])
    cp3 = ControlPlaneNode("cp-3", cp3_path, [cp3_url])

    cp1_server, cp1_thread = start_server(cp1, cp1_port)
    cp2_server, cp2_thread = start_server(cp2, cp2_port)
    cp3_server, cp3_thread = start_server(cp3, cp3_port)

    cp1_restarted_server: NodeHTTPServer | None = None
    cp1_restarted_thread: threading.Thread | None = None
    try:
        initial = cp1.initialize_group("group-stale-restart", 60)
        token_b = cp1.issue_bootstrap_token(120)
        token_c = cp1.issue_bootstrap_token(120)
        await cp2.join_peer(cp1_url, initial.leader_pubkey, token_b)
        await cp3.join_peer(cp1_url, initial.leader_pubkey, token_c)
        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()

        stop_server(cp1_server, cp1_thread)

        # Expire state and promote cp-2.
        state_b = cp2.state_manager.require_state()
        expired_b = cp2.state_manager.build_next_state(
            state_b.leader_node_id,
            state_b.leader_pubkey,
            state_b.control_planes,
            state_b.runtimes,
            state_b.endpoints,
            -1,
            cp1.key_pair,
        )
        cp2.state_manager.replace_state(expired_b)
        state_c = cp3.state_manager.require_state()
        expired_c = cp3.state_manager.build_next_state(
            state_c.leader_node_id,
            state_c.leader_pubkey,
            state_c.control_planes,
            state_c.runtimes,
            state_c.endpoints,
            -1,
            cp1.key_pair,
        )
        cp3.state_manager.replace_state(expired_c)
        promoted = await cp2.check_failover(60)
        assert promoted is not None
        assert promoted.leader_node_id == "cp-2"
        await cp3.sync_control_plane_events(preferred_leader_url=cp2_url)

        # Restart cp-1 with stale disk state as self-leader and force it expired.
        cp1_restarted = ControlPlaneNode("cp-1", cp1_path, [cp1_url])
        stale = cp1_restarted.state_manager.require_state()
        forced_expired = cp1_restarted.state_manager.build_next_state(
            stale.leader_node_id,
            stale.leader_pubkey,
            stale.control_planes,
            stale.runtimes,
            stale.endpoints,
            -1,
            cp1_restarted.key_pair,
            increment_version=False,
        )
        cp1_restarted.state_manager.replace_state(forced_expired)
        cp1_restarted_server, cp1_restarted_thread = start_server(cp1_restarted, cp1_port)

        # Simulate failover loop tick on restarted stale leader.
        result = await cp1_restarted.check_failover(60)
        assert result is not None
        assert result.leader_node_id == "cp-2"
        assert cp1_restarted.state_manager.require_state().leader_node_id == "cp-2"
    finally:
        if cp1_restarted_server is not None and cp1_restarted_thread is not None:
            stop_server(cp1_restarted_server, cp1_restarted_thread)
        stop_server(cp2_server, cp2_thread)
        stop_server(cp3_server, cp3_thread)


@pytest.mark.asyncio
async def test_user_db_replication_and_user_events_for_live_and_catchup_followers(tmp_path: Path) -> None:
    cp1_port = free_port()
    cp2_port = free_port()
    cp3_port = free_port()
    cp1_url = f"http://127.0.0.1:{cp1_port}"
    cp2_url = f"http://127.0.0.1:{cp2_port}"
    cp3_url = f"http://127.0.0.1:{cp3_port}"

    cp1 = ControlPlaneNode("cp-1", tmp_path / "cp-1-db", [cp1_url])
    cp2 = ControlPlaneNode("cp-2", tmp_path / "cp-2-db", [cp2_url])
    cp3 = ControlPlaneNode("cp-3", tmp_path / "cp-3-db", [cp3_url])

    cp1_server, cp1_thread = start_server(cp1, cp1_port)
    cp2_server, cp2_thread = start_server(cp2, cp2_port)
    cp3_server, cp3_thread = start_server(cp3, cp3_port)
    try:
        initial = cp1.initialize_group("group-user-db-sync", 60)
        token_b = cp1.issue_bootstrap_token(120)
        token_c = cp1.issue_bootstrap_token(120)
        await cp2.join_peer(cp1_url, initial.leader_pubkey, token_b)
        await cp3.join_peer(cp1_url, initial.leader_pubkey, token_c)
        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()

        stop_server(cp3_server, cp3_thread)
        cp3_version_before = cp3.user_state_manager.get_state().version

        new_admin_key = Ed25519KeyPair.generate().public_key_b64()
        created_user = cp1.ensure_admin_user("new-admin", new_admin_key)
        assert created_user.user_id == "new-admin"
        assert created_user.public_key == new_admin_key

        upsert_events = [item for item in cp1.event_manager.current.items if isinstance(item, UserUpsertedEvent)]
        assert upsert_events
        assert upsert_events[-1].user.user_id == "new-admin"

        audit_events = [item for item in cp1.event_manager.current.items if isinstance(item, UserEventAppendedEvent)]
        assert audit_events
        assert audit_events[-1].event.action == "rbac.admin.user.upsert"
        assert audit_events[-1].event.details.get("user_id") == "new-admin"

        leader_db_users = cp1.storage.load_user_state().users
        assert any(item.user_id == "new-admin" for item in leader_db_users)

        await cp2.sync_control_plane_events()
        assert cp2.user_state_manager.find_user("new-admin") is not None
        cp2_db_users = cp2.storage.load_user_state().users
        assert any(item.user_id == "new-admin" for item in cp2_db_users)

        assert cp3.user_state_manager.get_state().version == cp3_version_before
        assert cp3.storage.load_user_state().version == cp3_version_before
        assert cp3.user_state_manager.find_user("new-admin") is None

        cp3_server, cp3_thread = start_server(cp3, cp3_port)
        await cp3.sync_control_plane_events(preferred_leader_url=cp1_url)
        assert cp3.user_state_manager.find_user("new-admin") is not None
        cp3_db_users = cp3.storage.load_user_state().users
        assert any(item.user_id == "new-admin" for item in cp3_db_users)

        assert cp1.user_state_manager.get_state().version == cp2.user_state_manager.get_state().version
        assert cp1.user_state_manager.get_state().version == cp3.user_state_manager.get_state().version
        assert cp1.event_manager.get_last_event_id() == cp2.event_manager.get_last_event_id()
        assert cp1.event_manager.get_last_event_id() == cp3.event_manager.get_last_event_id()
    finally:
        stop_server(cp3_server, cp3_thread)


@pytest.mark.asyncio
async def test_followers_receive_admin_created_by_separate_process_same_db(tmp_path: Path) -> None:
    cp1_port = free_port()
    cp2_port = free_port()
    cp3_port = free_port()
    cp1_url = f"http://127.0.0.1:{cp1_port}"
    cp2_url = f"http://127.0.0.1:{cp2_port}"
    cp3_url = f"http://127.0.0.1:{cp3_port}"

    cp1_path = tmp_path / "cp-1-multiproc"
    cp1_server_node = ControlPlaneNode("cp-1", cp1_path, [cp1_url])
    cp2 = ControlPlaneNode("cp-2", tmp_path / "cp-2-multiproc", [cp2_url])
    cp3 = ControlPlaneNode("cp-3", tmp_path / "cp-3-multiproc", [cp3_url])

    cp1_server, cp1_thread = start_server(cp1_server_node, cp1_port)
    cp2_server, cp2_thread = start_server(cp2, cp2_port)
    cp3_server, cp3_thread = start_server(cp3, cp3_port)
    try:
        initial = cp1_server_node.initialize_group("group-multiproc", 60)
        token_b = cp1_server_node.issue_bootstrap_token(120)
        token_c = cp1_server_node.issue_bootstrap_token(120)
        await cp2.join_peer(cp1_url, initial.leader_pubkey, token_b)
        await cp3.join_peer(cp1_url, initial.leader_pubkey, token_c)
        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()
        assert cp2.user_state_manager.find_user("admin") is None
        assert cp3.user_state_manager.find_user("admin") is None

        # Emulate docker-compose: a separate process creates GUI user via bootstrap API.
        bootstrap_request = GuiUserBootstrapRequest(
            bootstrap_token=cp1_server_node.issue_gui_bootstrap_token(60),
            user_id="admin",
            public_key=Ed25519KeyPair.generate().public_key_b64(),
            control_plane_urls=[cp1_url],
        )
        await cp1_server_node.handle_request(
            "POST",
            "/v1/gui/bootstrap-user",
            encode_value(bootstrap_request),
            RequestAuth(node_id="", timestamp=0, nonce="", signature=""),
            "",
        )
        assert cp1_server_node.user_state_manager.find_user("admin") is not None

        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()
        assert cp2.user_state_manager.find_user("admin") is not None
        assert cp3.user_state_manager.find_user("admin") is not None
        assert any(isinstance(item, UserUpsertedEvent) for item in cp2.event_manager.current.items)
        assert any(isinstance(item, UserUpsertedEvent) for item in cp3.event_manager.current.items)
    finally:
        stop_server(cp1_server, cp1_thread)
        stop_server(cp2_server, cp2_thread)
        stop_server(cp3_server, cp3_thread)


@pytest.mark.asyncio
async def test_gui_failover_sync_is_seqno_strict_and_state_hash_consistent(tmp_path: Path) -> None:
    cp1_port = free_port()
    cp2_port = free_port()
    cp3_port = free_port()
    cp1_url = f"http://127.0.0.1:{cp1_port}"
    cp2_url = f"http://127.0.0.1:{cp2_port}"
    cp3_url = f"http://127.0.0.1:{cp3_port}"

    cp1 = ControlPlaneNode("cp-1", tmp_path / "cp-1-seq", [cp1_url])
    cp2 = ControlPlaneNode("cp-2", tmp_path / "cp-2-seq", [cp2_url])
    cp3 = ControlPlaneNode("cp-3", tmp_path / "cp-3-seq", [cp3_url])

    cp1_server, cp1_thread = start_server(cp1, cp1_port)
    cp2_server, cp2_thread = start_server(cp2, cp2_port)
    cp3_server, cp3_thread = start_server(cp3, cp3_port)
    try:
        initial = cp1.initialize_group("group-gui-seq", 60)
        token_b = cp1.issue_bootstrap_token(120)
        token_c = cp1.issue_bootstrap_token(120)
        await cp2.join_peer(cp1_url, initial.leader_pubkey, token_b)
        await cp3.join_peer(cp1_url, initial.leader_pubkey, token_c)
        await cp2.sync_control_plane_events()
        await cp3.sync_control_plane_events()

        assert cp1.event_manager.get_last_event_id() == cp2.event_manager.get_last_event_id()
        assert cp1.event_manager.get_last_event_id() == cp3.event_manager.get_last_event_id()
        assert cp1.event_manager.current_state_hash() == cp2.event_manager.current_state_hash()
        assert cp1.event_manager.current_state_hash() == cp3.event_manager.current_state_hash()
        assert_strict_seqnos(cp1)
        assert_strict_seqnos(cp2)
        assert_strict_seqnos(cp3)

        stop_server(cp3_server, cp3_thread)
        cp3_last_before = cp3.event_manager.get_last_event_id()
        cp3_user_before = cp3.user_state_manager.get_state().version

        config = await bootstrap_gui_config(cp1, cp1_url, "admin")
        cp1.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="admin"))
        await cp2.sync_control_plane_events()

        assert cp2.event_manager.get_last_event_id() == cp1.event_manager.get_last_event_id()
        assert cp2.user_state_manager.find_user("admin") is not None
        assert cp3.event_manager.get_last_event_id() == cp3_last_before
        assert cp3.user_state_manager.get_state().version == cp3_user_before
        assert cp3.user_state_manager.find_user("admin") is None

        cp3_server, cp3_thread = start_server(cp3, cp3_port)

        applied_ids: list[int] = []
        original_apply_remote_events = cp3.event_manager.apply_remote_events

        def tracked_apply_remote_events(events, trusted_leader_pubkey=None):  # type: ignore[no-untyped-def]
            applied_ids.extend(item.event_id for item in events)
            return original_apply_remote_events(events, trusted_leader_pubkey=trusted_leader_pubkey)

        cp3.event_manager.apply_remote_events = tracked_apply_remote_events  # type: ignore[method-assign]
        await cp3.sync_control_plane_events(preferred_leader_url=cp1_url)

        cp3_last_after = cp3.event_manager.get_last_event_id()
        assert applied_ids == list(range(cp3_last_before + 1, cp3_last_after + 1))
        assert cp3.user_state_manager.find_user("admin") is not None
        assert cp3.event_manager.current_state_hash() == cp1.event_manager.current_state_hash()
        assert_strict_seqnos(cp3)

        stop_server(cp1_server, cp1_thread)
        stop_server(cp2_server, cp2_thread)

        state = cp3.state_manager.require_state()
        expired = cp3.state_manager.build_next_state(
            state.leader_node_id,
            state.leader_pubkey,
            state.control_planes,
            state.runtimes,
            state.endpoints,
            -1,
            cp1.key_pair,
        )
        cp3.state_manager.replace_state(expired)
        promoted = await cp3.check_failover(60)
        assert promoted is not None
        assert promoted.leader_node_id == "cp-3"

        key = Ed25519KeyPair.from_private_key_b64(config.private_key)
        signer = SignedTransportClient(config.user_id, config.public_key, key)
        req_auth = signer.build_auth("GET", "/v1/gui/cluster", b"")
        response = await cp3.handle_request("GET", "/v1/gui/cluster", b"", req_auth, config.public_key)
        assert response.group_id == "group-gui-seq"
    finally:
        stop_server(cp3_server, cp3_thread)
