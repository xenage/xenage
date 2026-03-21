from __future__ import annotations

import asyncio
import socket
import threading
from pathlib import Path

import pytest

from structures.resources.membership import JoinRequest, NodeRecord
from xenage.crypto import Ed25519KeyPair
from xenage.cluster.state_manager import StateValidationError
from xenage.network.http_transport import NodeHTTPServer, TransportError
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.nodes.runtime import RuntimeNode

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


def test_runtime_joins_leader_over_http(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    bootstrap = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime")

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    leader_thread.start()
    assert leader_server.wait_until_ready()
    try:
        state = asyncio.run(runtime.connect(leader_url, bootstrap.leader_pubkey, token))
    finally:
        leader_server.shutdown()
        leader_thread.join(timeout=1)

    assert len(state.runtimes) == 1
    assert state.runtimes[0].node_id == "rt-a"
    assert state.runtimes[0].endpoints == []
    assert all(item.node_id != "rt-a" for item in state.endpoints)


def test_runtime_connect_rejects_fake_leader_pubkey(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime")
    fake_leader_key = Ed25519KeyPair.generate().public_key_b64()

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    leader_thread.start()
    assert leader_server.wait_until_ready()
    try:
        with pytest.raises(TransportError, match="leader pubkey mismatch in group state"):
            asyncio.run(runtime.connect(leader_url, fake_leader_key, token))
    finally:
        leader_server.shutdown()
        leader_thread.join(timeout=1)


def test_control_plane_join_rejects_fake_leader_pubkey(tmp_path: Path) -> None:
    leader_port = free_port()
    follower_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    follower_url = f"http://127.0.0.1:{follower_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    follower = ControlPlaneNode("cp-b", tmp_path / "follower", [follower_url])
    fake_leader_key = Ed25519KeyPair.generate().public_key_b64()

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    follower_server = NodeHTTPServer("127.0.0.1", follower_port, follower)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    follower_thread = threading.Thread(target=follower_server.serve_forever, daemon=True)
    leader_thread.start()
    follower_thread.start()
    assert leader_server.wait_until_ready()
    assert follower_server.wait_until_ready()
    try:
        with pytest.raises((TransportError, StateValidationError), match="(leader pubkey mismatch in group state|leader signature validation failed)"):
            asyncio.run(follower.join_peer(leader_url, fake_leader_key, token))
    finally:
        leader_server.shutdown()
        follower_server.shutdown()
        leader_thread.join(timeout=1)
        follower_thread.join(timeout=1)


def test_runtime_join_drops_endpoint_advertisement(tmp_path: Path) -> None:
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime_key = Ed25519KeyPair.generate()

    state = leader.apply_join(
        JoinRequest(
            bootstrap_token=token,
            node=NodeRecord(
                node_id="rt-a",
                role="runtime",
                public_key=runtime_key.public_key_b64(),
                endpoints=["http://rt-a:8735"],
            ),
        ),
        60,
    )

    runtime = next(item for item in state.runtimes if item.node_id == "rt-a")
    assert runtime.endpoints == []
    assert all(item.node_id != "rt-a" for item in state.endpoints)


def test_runtime_pulls_state_from_control_plane(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    boot = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime")

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    leader_thread.start()
    assert leader_server.wait_until_ready()
    try:
        asyncio.run(runtime.connect(leader_url, boot.leader_pubkey, token))
        before = runtime.state_manager.require_state().version
        token_rt2 = leader.issue_bootstrap_token(60)
        rt2_key = Ed25519KeyPair.generate()
        leader.apply_join(
            JoinRequest(
                bootstrap_token=token_rt2,
                node=NodeRecord(
                    node_id="rt-b",
                    role="runtime",
                    public_key=rt2_key.public_key_b64(),
                    endpoints=[],
                ),
            ),
            60,
        )
        pulled = asyncio.run(runtime.pull_group_state())
    finally:
        leader_server.shutdown()
        leader_thread.join(timeout=1)

    assert pulled is not None
    assert pulled.version > before
    assert any(item.node_id == "rt-b" for item in pulled.runtimes)


def test_runtime_poll_marks_runtime_ready_in_gui_snapshot(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    boot = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime")

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    leader_thread.start()
    assert leader_server.wait_until_ready()
    try:
        asyncio.run(runtime.connect(leader_url, boot.leader_pubkey, token))
        asyncio.run(runtime.pull_group_state())
        snapshot = asyncio.run(leader.api_logic.build_gui_snapshot())
    finally:
        leader_server.shutdown()
        leader_thread.join(timeout=1)

    runtime_row = next(item for item in snapshot.nodes if item.node_id == "rt-a")
    assert runtime_row.status == "ready"
    assert runtime_row.last_poll_at
