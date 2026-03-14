from __future__ import annotations

from pathlib import Path

from structures.resources.membership import GroupEndpoint, JoinRequest, NodeRecord
from xenage.crypto import Ed25519KeyPair
from xenage.nodes.control_plane import ControlPlaneNode, sort_control_planes
from xenage.serialization import encode_value


def test_sort_control_planes_is_stable_by_node_id() -> None:
    a = NodeRecord(node_id="cp-b", role="control-plane", public_key="b", endpoints=[])
    b = NodeRecord(node_id="cp-a", role="control-plane", public_key="a", endpoints=[])
    ordered = sort_control_planes([a, b])
    assert [item.node_id for item in ordered] == ["cp-a", "cp-b"]


def test_control_plane_join_revoke_and_failover(tmp_path: Path) -> None:
    leader = ControlPlaneNode("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    state = leader.initialize_group("group-1", 1)
    token = leader.issue_bootstrap_token(60)

    follower = ControlPlaneNode("cp-b", tmp_path / "follower", ["http://cp-b:8734"])
    joined = leader.apply_join(
        JoinRequest(bootstrap_token=token, node=follower.node_record()),
        60,
    )
    follower.state_manager.replace_state(joined, trusted_leader_pubkey=state.leader_pubkey)
    assert len(joined.control_planes) == 2

    runtime_key = Ed25519KeyPair.generate()
    runtime_record = NodeRecord(
        node_id="rt-a",
        role="runtime",
        public_key=runtime_key.public_key_b64(),
        endpoints=["http://rt-a:8735"],
    )
    token_runtime = leader.issue_bootstrap_token(60)
    state_with_runtime = leader.apply_join(
        JoinRequest(bootstrap_token=token_runtime, node=runtime_record),
        60,
    )
    assert len(state_with_runtime.runtimes) == 1

    promoted = follower.check_failover(60)
    assert promoted is None

    expired = follower.state_manager.build_next_state(
        state_with_runtime.leader_node_id,
        state_with_runtime.leader_pubkey,
        state_with_runtime.control_planes,
        state_with_runtime.runtimes,
        state_with_runtime.endpoints,
        -1,
        leader.key_pair,
    )
    follower.state_manager.replace_state(expired)
    promoted = follower.check_failover(60)
    assert promoted is not None
    assert promoted.leader_node_id == "cp-b"
    assert promoted.leader_epoch == state_with_runtime.leader_epoch + 1

    revoked = follower.revoke_node("rt-a", 60)
    assert revoked.runtimes == []


def test_only_deterministic_failover_candidate_promotes(tmp_path: Path) -> None:
    leader = ControlPlaneNode("cp-a", tmp_path / "cp-a", ["http://cp-a:8734"])
    bootstrap = leader.initialize_group("group-1", 1)
    token_b = leader.issue_bootstrap_token(60)
    token_c = leader.issue_bootstrap_token(60)

    cp_b = ControlPlaneNode("cp-b", tmp_path / "cp-b", ["http://cp-b:8734"])
    cp_c = ControlPlaneNode("cp-c", tmp_path / "cp-c", ["http://cp-c:8734"])
    state_with_b = leader.apply_join(JoinRequest(bootstrap_token=token_b, node=cp_b.node_record()), 60)
    state_with_c = leader.apply_join(JoinRequest(bootstrap_token=token_c, node=cp_c.node_record()), 60)

    cp_b.state_manager.replace_state(state_with_c, trusted_leader_pubkey=bootstrap.leader_pubkey)
    cp_c.state_manager.replace_state(state_with_c, trusted_leader_pubkey=bootstrap.leader_pubkey)

    expired = cp_b.state_manager.build_next_state(
        state_with_c.leader_node_id,
        state_with_c.leader_pubkey,
        state_with_c.control_planes,
        state_with_c.runtimes,
        state_with_c.endpoints,
        -1,
        leader.key_pair,
    )
    cp_b.state_manager.replace_state(expired)
    cp_c.state_manager.replace_state(expired)

    cp_b.publish_failover_state = lambda promoted_state, previous_leader_node_id: True  # type: ignore[method-assign]
    cp_c.publish_failover_state = lambda promoted_state, previous_leader_node_id: True  # type: ignore[method-assign]

    promoted_b = cp_b.check_failover(60)
    promoted_c = cp_c.check_failover(60)
    assert promoted_b is not None
    assert promoted_b.leader_node_id == "cp-b"
    assert promoted_c is None


def test_control_plane_sync_from_peers_updates_state_on_restart(tmp_path: Path) -> None:
    cp1 = ControlPlaneNode("cp-1", tmp_path / "cp-1", ["http://cp-1:8734"])
    cp2 = ControlPlaneNode("cp-2", tmp_path / "cp-2", ["http://cp-2:8736"])
    initial = cp1.initialize_group("group-1", 60)
    cp2.state_manager.replace_state(initial, trusted_leader_pubkey=initial.leader_pubkey)

    token = cp1.issue_bootstrap_token(60)
    joined = cp1.apply_join(JoinRequest(bootstrap_token=token, node=cp2.node_record()), 60)
    cp2.state_manager.replace_state(joined)
    newer = cp1.state_manager.build_next_state(
        leader_node_id="cp-1",
        leader_pubkey=cp1.identity.public_key,
        control_planes=joined.control_planes,
        runtimes=joined.runtimes,
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8736"),
        ],
        ttl_seconds=60,
        key_pair=cp1.key_pair,
    )
    cp1.state_manager.replace_state(newer)

    stale = cp2.state_manager.get_state()
    assert stale is not None
    assert stale.version < newer.version

    cp2.client.get = lambda url, path: encode_value(newer)  # type: ignore[method-assign]
    synced = cp2.sync_state_from_control_planes()
    assert synced is not None
    assert synced.version == newer.version
