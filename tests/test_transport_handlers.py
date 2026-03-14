from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

from structures.resources.membership import GroupState, JoinRequest, NodeRecord, PublishStateRequest
from xenage.crypto import Ed25519KeyPair
from xenage.network.http_transport import NodeHTTPServer, SignedTransportClient, TransportError
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.nodes.runtime import RuntimeNode


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_runtime_joins_leader_over_http(tmp_path: Path) -> None:
    leader_port = free_port()
    runtime_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    runtime_url = f"http://127.0.0.1:{runtime_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    bootstrap = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime", [runtime_url])

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    runtime_server = NodeHTTPServer("127.0.0.1", runtime_port, runtime)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    runtime_thread = threading.Thread(target=runtime_server.serve_forever, daemon=True)
    leader_thread.start()
    runtime_thread.start()
    try:
        state = runtime.connect(leader_url, bootstrap.leader_pubkey, token)
    finally:
        leader_server.shutdown()
        runtime_server.shutdown()
        leader_thread.join(timeout=1)
        runtime_thread.join(timeout=1)

    assert len(state.runtimes) == 1
    assert state.runtimes[0].node_id == "rt-a"


def test_runtime_connect_rejects_fake_leader_pubkey(tmp_path: Path) -> None:
    leader_port = free_port()
    runtime_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    runtime_url = f"http://127.0.0.1:{runtime_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime", [runtime_url])
    fake_leader_key = Ed25519KeyPair.generate().public_key_b64()

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    runtime_server = NodeHTTPServer("127.0.0.1", runtime_port, runtime)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    runtime_thread = threading.Thread(target=runtime_server.serve_forever, daemon=True)
    leader_thread.start()
    runtime_thread.start()
    try:
        with pytest.raises(TransportError, match="leader pubkey mismatch in group state"):
            runtime.connect(leader_url, fake_leader_key, token)
    finally:
        leader_server.shutdown()
        runtime_server.shutdown()
        leader_thread.join(timeout=1)
        runtime_thread.join(timeout=1)


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
    try:
        with pytest.raises(TransportError, match="leader pubkey mismatch in group state"):
            follower.join_peer(leader_url, fake_leader_key, token)
    finally:
        leader_server.shutdown()
        follower_server.shutdown()
        leader_thread.join(timeout=1)
        follower_thread.join(timeout=1)


def test_publish_state_rejects_fake_leader_signature(tmp_path: Path) -> None:
    leader_port = free_port()
    runtime_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    runtime_url = f"http://127.0.0.1:{runtime_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    bootstrap = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime", [runtime_url])

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    runtime_server = NodeHTTPServer("127.0.0.1", runtime_port, runtime)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    runtime_thread = threading.Thread(target=runtime_server.serve_forever, daemon=True)
    leader_thread.start()
    runtime_thread.start()
    try:
        runtime.connect(leader_url, bootstrap.leader_pubkey, token)
        current = runtime.state_manager.require_state()

        attacker = Ed25519KeyPair.generate()
        forged_unsigned = GroupState(
            group_id=current.group_id,
            version=current.version + 1,
            leader_epoch=current.leader_epoch,
            leader_node_id=current.leader_node_id,
            leader_pubkey=attacker.public_key_b64(),
            control_planes=current.control_planes,
            runtimes=current.runtimes,
            endpoints=current.endpoints,
            expires_at=current.expires_at,
        )
        forged = runtime.state_manager.sign_state(forged_unsigned, attacker)

        attacker_client = SignedTransportClient(
            node_id="cp-attacker",
            public_key=attacker.public_key_b64(),
            key_pair=attacker,
        )
        with pytest.raises(TransportError):
            attacker_client.post_json(
                runtime_url,
                "/v1/state/publish",
                PublishStateRequest(group_state=forged),
                GroupState,
            )
        assert runtime.state_manager.require_state().leader_pubkey == current.leader_pubkey
        assert runtime.state_manager.require_state().version == current.version
    finally:
        leader_server.shutdown()
        runtime_server.shutdown()
        leader_thread.join(timeout=1)
        runtime_thread.join(timeout=1)


def test_runtime_pulls_state_from_control_plane(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"

    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    boot = leader.initialize_group("group-http", 60)
    token = leader.issue_bootstrap_token(60)
    runtime = RuntimeNode("rt-a", tmp_path / "runtime", ["http://rt-a:8735"])

    leader_server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    leader_thread = threading.Thread(target=leader_server.serve_forever, daemon=True)
    leader_thread.start()
    try:
        runtime.connect(leader_url, boot.leader_pubkey, token)
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
                    endpoints=["http://rt-b:8735"],
                ),
            ),
            60,
        )
        pulled = runtime.pull_group_state()
    finally:
        leader_server.shutdown()
        leader_thread.join(timeout=1)

    assert pulled is not None
    assert pulled.version > before
    assert any(item.node_id == "rt-b" for item in pulled.runtimes)
