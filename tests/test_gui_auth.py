from __future__ import annotations

import asyncio
import socket
import threading
from pathlib import Path

import pytest

from structures.resources.membership import JoinRequest
from structures.resources.membership import GuiConnectionConfig
from structures.resources.membership import GuiUserBootstrapRequest, RequestAuth
from xenage.cluster.time_utils import parse_timestamp
from xenage.crypto import Ed25519KeyPair
from xenage.network.cli_client import ControlPlaneClient
from xenage.network.http_transport import NodeHTTPServer, SignedTransportClient, TransportError
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.serialization import encode_value


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def bootstrap_gui_config(
    leader: ControlPlaneNode,
    leader_url: str,
    user_id: str = "admin",
    control_plane_urls: list[str] | None = None,
) -> GuiConnectionConfig:
    user_key = Ed25519KeyPair.generate()
    token = leader.issue_gui_bootstrap_token(60)
    request = GuiUserBootstrapRequest(
        bootstrap_token=token,
        user_id=user_id,
        public_key=user_key.public_key_b64(),
        control_plane_urls=control_plane_urls or [leader_url],
    )
    anonymous = RequestAuth(node_id="", timestamp=0, nonce="", signature="")
    response = asyncio.run(
        leader.handle_request(
            "POST",
            "/v1/gui/bootstrap-user",
            encode_value(request),
            anonymous,
            "",
        )
    )
    return GuiConnectionConfig(
        cluster_name=response.cluster_name,
        control_plane_urls=response.control_plane_urls,
        user_id=response.user_id,
        role=response.role,
        public_key=response.public_key,
        private_key=user_key.private_key_b64(),
    )


def test_gui_admin_signed_request_reads_cluster_snapshot(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-gui", 60)
    config = bootstrap_gui_config(leader, leader_url, "admin")

    server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.wait_until_ready()
    try:
        client = ControlPlaneClient(config)
        snapshot = client.fetch_cluster_snapshot()
        events = client.fetch_cluster_events(limit=50)
    finally:
        server.shutdown()
        thread.join(timeout=1)

    assert snapshot.group_id == "group-gui"
    assert any(node.node_id == "cp-a" for node in snapshot.nodes)
    assert any(node.status for node in snapshot.nodes)
    leader_row = next(node for node in snapshot.nodes if node.node_id == "cp-a")
    assert leader_row.age
    assert leader_row.last_poll_at
    parse_timestamp(leader_row.age)
    parse_timestamp(leader_row.last_poll_at)
    assert any(item.key == "leader_node_id" for item in snapshot.group_config)
    assert any(item.key == "node.cp-a.status" for item in snapshot.group_config)
    assert any(item.key == "control_plane_sync_status" for item in snapshot.group_config)
    assert any(event.action == "gui.cluster.snapshot.read" for event in events.items)


def test_gui_request_rejects_untrusted_key(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-gui", 60)
    config = bootstrap_gui_config(leader, leader_url, "admin")

    attacker = Ed25519KeyPair.generate()
    forged = GuiConnectionConfig(
        cluster_name=config.cluster_name,
        control_plane_urls=config.control_plane_urls,
        user_id=config.user_id,
        role=config.role,
        public_key=attacker.public_key_b64(),
        private_key=attacker.private_key_b64(),
    )

    server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.wait_until_ready()
    try:
        with pytest.raises(TransportError):
            ControlPlaneClient(forged).fetch_cluster_snapshot()
    finally:
        server.shutdown()
        thread.join(timeout=1)


def test_gui_admin_event_catches_up_after_follower_downtime(tmp_path: Path) -> None:
    leader_url = "http://cp-a:8734"
    follower_url = "http://cp-b:8735"
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    initial = leader.initialize_group("group-gui", 60)

    follower = ControlPlaneNode("cp-b", tmp_path / "follower", [follower_url])
    token = leader.issue_bootstrap_token(60)
    joined = leader.apply_join(JoinRequest(bootstrap_token=token, node=follower.node_record()), 60)
    follower.state_manager.replace_state(joined, trusted_leader_pubkey=initial.leader_pubkey)

    # Simulate the follower already having baseline control-plane history before user creation.
    follower.event_manager.current = leader.event_manager.current
    follower.storage.save_control_plane_event_log(follower.event_manager.current)
    follower.user_state_manager.replace_state(leader.user_state_manager.get_state())

    config = bootstrap_gui_config(leader, leader_url, "admin")
    assert all(item.nonce for item in leader.event_manager.current.items)
    assert follower.user_state_manager.find_user("admin") is None

    async def pull_from_leader(url: str, path: str) -> bytes:
        if path.startswith("/v1/control-plane/events"):
            query = path.partition("?")[2]
            values: dict[str, str] = {}
            for part in query.split("&"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    values[key] = value
            after_event_id = int(values.get("after_event_id", "0"))
            limit = int(values.get("limit", "250"))
            page = leader.event_manager.event_page(leader.identity.node_id, after_event_id, limit)
            return encode_value(page)
        if path == "/v1/heartbeat":
            return encode_value({"status": "ok", "node_id": leader.identity.node_id})
        raise TransportError(f"unsupported path {path}")

    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    follower.client.get = pull_from_leader  # type: ignore[method-assign]
    follower.client.post_json = fake_post  # type: ignore[method-assign]
    synced = asyncio.run(follower.sync_control_plane_events())
    assert synced is not None

    replicated = follower.user_state_manager.find_user("admin")
    assert replicated is not None
    assert replicated.public_key == config.public_key

    # Leader goes down before follower can pull-sync; follower promotes itself.
    state = follower.state_manager.require_state()
    expired = follower.state_manager.build_next_state(
        state.leader_node_id,
        state.leader_pubkey,
        state.control_planes,
        state.runtimes,
        state.endpoints,
        -1,
        leader.key_pair,
    )
    follower.state_manager.replace_state(expired)

    async def leader_down(url: str, path: str) -> bytes:
        raise TransportError("leader offline")

    follower.client.get = leader_down  # type: ignore[method-assign]
    promoted = asyncio.run(follower.check_failover(60))
    assert promoted is not None
    assert promoted.leader_node_id == "cp-b"

    gui_key = Ed25519KeyPair.from_private_key_b64(config.private_key)
    gui_signer = SignedTransportClient(config.user_id, config.public_key, gui_key)
    gui_auth = gui_signer.build_auth("GET", "/v1/gui/cluster", b"")
    snapshot = asyncio.run(follower.handle_request("GET", "/v1/gui/cluster", b"", gui_auth, config.public_key))
    assert snapshot.group_id == "group-gui"
