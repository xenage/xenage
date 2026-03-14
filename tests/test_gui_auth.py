from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

from structures.resources.membership import GuiConnectionConfig
from xenage.crypto import Ed25519KeyPair
from xenage.network.gui_client import GuiSignedClient
from xenage.network.http_transport import NodeHTTPServer, TransportError
from xenage.nodes.control_plane import ControlPlaneNode


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_gui_admin_signed_request_reads_cluster_snapshot(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-gui", 60)
    config = leader.issue_gui_connection_config(leader_url, "admin")

    server = NodeHTTPServer("127.0.0.1", leader_port, leader)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        snapshot = GuiSignedClient(config).fetch_cluster_snapshot()
    finally:
        server.shutdown()
        thread.join(timeout=1)

    assert snapshot.group_id == "group-gui"
    assert any(node.node_id == "cp-a" for node in snapshot.nodes)
    assert any(item.key == "leader_node_id" for item in snapshot.group_config)
    assert any(event.action == "gui.cluster.snapshot.read" for event in snapshot.event_log)


def test_gui_request_rejects_untrusted_key(tmp_path: Path) -> None:
    leader_port = free_port()
    leader_url = f"http://127.0.0.1:{leader_port}"
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", [leader_url])
    leader.initialize_group("group-gui", 60)
    config = leader.issue_gui_connection_config(leader_url, "admin")

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
    try:
        with pytest.raises(TransportError):
            GuiSignedClient(forged).fetch_cluster_snapshot()
    finally:
        server.shutdown()
        thread.join(timeout=1)
