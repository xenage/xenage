from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from structures.resources.events import ControlPlaneEventPage, GuiClusterSnapshotReadEvent
from structures.resources.membership import (
    GroupEndpoint,
    GroupState,
    GuiUserBootstrapRequest,
    JoinRequest,
    NodeRecord,
    RequestAuth,
    UserState,
)
from xenage.crypto import Ed25519KeyPair
from xenage.network.http_transport import TransportError
from xenage.nodes.control_plane import ControlPlaneNode, sort_control_planes
from xenage.serialization import encode_value


def make_control_plane(node_id: str, storage_path: Path, endpoints: list[str]) -> ControlPlaneNode:
    node = ControlPlaneNode(node_id, storage_path, endpoints)
    node.client.timeout_seconds = 0.05
    return node


def test_sort_control_planes_is_stable_by_node_id() -> None:
    a = NodeRecord(node_id="cp-b", role="control-plane", public_key="b", endpoints=[])
    b = NodeRecord(node_id="cp-a", role="control-plane", public_key="a", endpoints=[])
    ordered = sort_control_planes([a, b])
    assert [item.node_id for item in ordered] == ["cp-a", "cp-b"]


def test_control_plane_join_revoke_and_failover(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    state = leader.initialize_group("group-1", 1)
    token = leader.issue_bootstrap_token(60)

    follower = make_control_plane("cp-b", tmp_path / "follower", ["http://cp-b:8734"])
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
        endpoints=[],
    )
    token_runtime = leader.issue_bootstrap_token(60)
    state_with_runtime = leader.apply_join(
        JoinRequest(bootstrap_token=token_runtime, node=runtime_record),
        60,
    )
    assert len(state_with_runtime.runtimes) == 1

    promoted = asyncio.run(follower.check_failover(60))
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
    promoted = asyncio.run(follower.check_failover(60))
    assert promoted is not None
    assert promoted.leader_node_id == "cp-b"
    assert promoted.leader_epoch == state_with_runtime.leader_epoch + 1

    revoked = follower.revoke_node("rt-a", 60)
    assert revoked.runtimes == []


def test_only_deterministic_failover_candidate_promotes(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "cp-a", ["http://cp-a:8734"])
    bootstrap = leader.initialize_group("group-1", 1)
    token_b = leader.issue_bootstrap_token(60)
    token_c = leader.issue_bootstrap_token(60)

    cp_b = make_control_plane("cp-b", tmp_path / "cp-b", ["http://cp-b:8734"])
    cp_c = make_control_plane("cp-c", tmp_path / "cp-c", ["http://cp-c:8734"])
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

    promoted_b = asyncio.run(cp_b.check_failover(60))
    # In my new logic, if cp-b sees cp-c is alive, it should STILL promote if it's the next candidate.
    # The previous test might have assumed both check_failover calls are independent.
    # Actually, cp_c should NOT promote because cp_b is the next candidate and cp_b is ALIVE.
    # Wait, in the test, cp_b and cp_c are independent objects.
    
    # Let's check why it failed.
    # It might be because my changes to check_failover made it return something different or behave differently.
    
    # If cp_b is next candidate, it should promote.
    # If cp_c is NOT next candidate, and it sees cp_b is alive, it should NOT promote.
    
    # My new code:
    # candidate = self.node.current_failover_candidate(state)
    # if candidate.node_id != self.node.identity.node_id:
    #    ... check if candidate is reachable ...
    #    if candidate_reachable:
    #        return None
    
    # In the test, when running for cp_c:
    # candidate is cp_b.
    # To make cp_b "reachable" for cp_c, we need to mock cp_c's client.
    
    async def cp_c_fake_get(url, path):
        if "cp-b" in url and path == "/v1/heartbeat":
            return encode_value({"status": "ok", "node_id": "cp-b"})
        raise Exception("offline")
    cp_c.client.get = cp_c_fake_get
    
    promoted_c = asyncio.run(cp_c.check_failover(60))
    
    assert promoted_b is not None
    assert promoted_b.leader_node_id == "cp-b"
    assert promoted_c is None


def test_control_plane_sync_from_peers_updates_state_on_restart(tmp_path: Path) -> None:
    cp1 = make_control_plane("cp-1", tmp_path / "cp-1", ["http://cp-1:8734"])
    cp2 = make_control_plane("cp-2", tmp_path / "cp-2", ["http://cp-2:8736"])
    initial = cp1.initialize_group("group-1", 60)
    cp2.state_manager.replace_state(initial, trusted_leader_pubkey=initial.leader_pubkey)

    token = cp1.issue_bootstrap_token(60)
    joined = cp1.apply_join(JoinRequest(bootstrap_token=token, node=cp2.node_record()), 60)
    cp2.state_manager.replace_state(joined)
    cp2.event_manager.current = cp1.event_manager.current
    cp2.storage.save_control_plane_event_log(cp2.event_manager.current)
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
    cp1.event_manager.record_group_state("cp-1", newer)

    stale = cp2.state_manager.get_state()
    assert stale is not None
    assert stale.version < newer.version

    async def fake_get(url: str, path: str) -> bytes:
        parsed = urlparse(path)
        query = parse_qs(parsed.query)
        after_event_id = int(query.get("after_event_id", ["0"])[0])
        limit = int(query.get("limit", ["250"])[0])
        return encode_value(cp1.event_manager.event_page("cp-1", after_event_id, limit))

    cp2.client.get = fake_get  # type: ignore[method-assign]
    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    cp2.client.post_json = fake_post  # type: ignore[method-assign]
    synced = asyncio.run(cp2.sync_control_plane_events())
    assert synced is not None
    assert synced.version == newer.version


def test_control_plane_syncs_user_state_from_leader_and_marks_broken_when_local_ahead(tmp_path: Path) -> None:
    cp1 = make_control_plane("cp-1", tmp_path / "cp-1", ["http://cp-1:8734"])
    cp2 = make_control_plane("cp-2", tmp_path / "cp-2", ["http://cp-2:8736"])
    initial = cp1.initialize_group("group-1", 60)
    cp2.state_manager.replace_state(initial, trusted_leader_pubkey=initial.leader_pubkey)

    token = cp1.issue_bootstrap_token(60)
    joined = cp1.apply_join(JoinRequest(bootstrap_token=token, node=cp2.node_record()), 60)
    cp2.state_manager.replace_state(joined)
    cp2.event_manager.current = cp1.event_manager.current
    cp2.storage.save_control_plane_event_log(cp2.event_manager.current)

    cp1.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="leader"))

    async def fake_get(url: str, path: str) -> bytes:
        parsed = urlparse(path)
        query = parse_qs(parsed.query)
        after_event_id = int(query.get("after_event_id", ["0"])[0])
        limit = int(query.get("limit", ["250"])[0])
        return encode_value(cp1.event_manager.event_page("cp-1", after_event_id, limit))

    cp2.client.get = fake_get  # type: ignore[method-assign]
    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    cp2.client.post_json = fake_post  # type: ignore[method-assign]
    synced = asyncio.run(cp2.sync_control_plane_events())
    assert synced is not None
    assert cp2.user_state_manager.get_state().version == cp1.user_state_manager.get_state().version
    assert cp2.broken_sync_reason == ""

    # To simulate local ahead, we need to temporarily make cp2 believe it is a leader
    # or just manually inject an event. Since we want to test sync_control_plane_events detection,
    # let's manually record an event in cp2.
    cp2.event_manager.record_leader_promoted("cp-2", cp2.state_manager.get_state())
    assert cp2.event_manager.get_last_event_id() > cp1.event_manager.get_last_event_id()

    asyncio.run(cp2.sync_control_plane_events())
    assert cp2.broken_sync_reason != ""


def test_failover_does_not_self_promote_when_peer_history_diverges(tmp_path: Path) -> None:
    cp1_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    cp2 = make_control_plane("cp-2", tmp_path / "cp-2", ["http://cp-2:8736"])

    cp1_record = NodeRecord(
        node_id="cp-1",
        role="control-plane",
        public_key=cp1_key.public_key_b64(),
        endpoints=["http://cp-1:8734"],
    )
    cp2_record = cp2.node_record()
    cp3_record = NodeRecord(
        node_id="cp-3",
        role="control-plane",
        public_key=cp3_key.public_key_b64(),
        endpoints=["http://cp-3:8737"],
    )

    stale_state = GroupState(
        group_id="group-1",
        version=5,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=cp1_key.public_key_b64(),
        control_planes=[cp1_record, cp2_record, cp3_record],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8736"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8737"),
        ],
        expires_at="2020-01-01T00:00:00Z",
    )
    signed_stale_state = cp2.state_manager.sign_state(stale_state, cp1_key)
    cp2.state_manager.replace_state(signed_stale_state, trusted_leader_pubkey=cp1_key.public_key_b64())

    # Simulate cp-2 having extra local history while cp-3 has a shorter log.
    cp2.event_manager.record_group_state("cp-1", signed_stale_state)
    cp2.event_manager.record_group_state("cp-1", signed_stale_state)

    remote_page = ControlPlaneEventPage(
        leader_node_id="cp-3",
        leader_pubkey=cp3_key.public_key_b64(),
        leader_epoch=2,
        items=[],
        has_more=False,
        last_event_id=1,
    )

    async def fake_get(url: str, path: str) -> bytes:
        base_path = path.partition("?")[0]
        if base_path == "/v1/heartbeat":
            if "cp-1" in url:
                raise Exception("connection refused")
            return encode_value({"status": "ok", "node_id": "cp-3"})
        if base_path == "/v1/control-plane/events":
            if "cp-3" in url:
                return encode_value(remote_page)
            raise Exception("connection refused")
        raise Exception(f"unexpected path {base_path}")

    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    cp2.client.get = fake_get  # type: ignore[method-assign]
    cp2.client.post_json = fake_post  # type: ignore[method-assign]

    promoted = asyncio.run(cp2.check_failover(60))
    assert promoted is None
    assert cp2.is_leader() is False
    assert "local event history" in cp2.broken_sync_reason

def test_control_plane_gui_events_are_batched(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    leader.initialize_group("group-1", 60)
    for index in range(25):
        leader.append_cluster_event(GuiClusterSnapshotReadEvent(user_id=f"batch-{index}"))

    first_page = leader.build_gui_event_page(limit=10)
    first_sequences = [item.sequence for item in first_page.items]
    assert len(first_sequences) == 10
    assert first_sequences == sorted(first_sequences, reverse=True)
    assert first_page.has_more is True

    second_page = leader.build_gui_event_page(limit=10, before_sequence=first_page.next_before_sequence)
    second_sequences = [item.sequence for item in second_page.items]
    assert len(second_sequences) == 10
    assert second_sequences == sorted(second_sequences, reverse=True)
    assert second_sequences[0] < first_page.next_before_sequence
    assert set(first_sequences).isdisjoint(set(second_sequences))


def test_control_plane_gui_events_pagination_reads_full_history(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    leader.initialize_group("group-1", 60)
    for index in range(450):
        leader.append_cluster_event(GuiClusterSnapshotReadEvent(user_id=f"page-{index}"))

    seen_sequences: list[int] = []
    before_sequence: int | None = None
    while True:
        page = leader.build_gui_event_page(limit=50, before_sequence=before_sequence)
        page_sequences = [item.sequence for item in page.items]
        assert page_sequences == sorted(page_sequences, reverse=True)
        seen_sequences.extend(page_sequences)
        if not page.has_more:
            break
        before_sequence = page.next_before_sequence

    assert len(seen_sequences) >= 451
    assert len(seen_sequences) == len(set(seen_sequences))
    assert min(seen_sequences) == 1
    assert max(seen_sequences) == len(seen_sequences)


def test_control_plane_events_have_nonce_and_page_tracks_last_nonce(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader", ["http://cp-a:8734"])
    leader.initialize_group("group-1", 60)
    leader.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="nonce-a"))
    leader.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="nonce-b"))

    page = leader.event_manager.event_page("cp-a", after_event_id=0, limit=100)
    assert page.items
    assert all(item.nonce for item in page.items)
    assert page.last_event_nonce == page.items[-1].nonce

    previous_nonce = leader.event_manager.get_last_event_nonce()
    leader.append_cluster_event(GuiClusterSnapshotReadEvent(user_id="nonce-c"))
    assert leader.event_manager.get_last_event_nonce()
    assert leader.event_manager.get_last_event_nonce() != previous_nonce


def test_sync_marks_broken_when_event_id_matches_but_nonce_differs(tmp_path: Path) -> None:
    cp1 = make_control_plane("cp-1", tmp_path / "cp-1", ["http://cp-1:8734"])
    cp2 = make_control_plane("cp-2", tmp_path / "cp-2", ["http://cp-2:8736"])
    initial = cp1.initialize_group("group-1", 60)
    cp2.state_manager.replace_state(initial, trusted_leader_pubkey=initial.leader_pubkey)

    token = cp1.issue_bootstrap_token(60)
    joined = cp1.apply_join(JoinRequest(bootstrap_token=token, node=cp2.node_record()), 60)
    cp2.state_manager.replace_state(joined)
    cp2.event_manager.current = cp1.event_manager.current
    cp2.storage.save_control_plane_event_log(cp2.event_manager.current)

    local_last_event_id = cp2.event_manager.get_last_event_id()
    local_nonce = cp2.event_manager.get_last_event_nonce()
    assert local_last_event_id > 0
    assert local_nonce

    state = cp1.state_manager.require_state()
    forged_page = ControlPlaneEventPage(
        leader_node_id=state.leader_node_id,
        leader_pubkey=state.leader_pubkey,
        leader_epoch=state.leader_epoch,
        last_event_id=local_last_event_id,
        last_event_nonce="different-nonce",
        items=[],
        has_more=False,
    )

    async def fake_get(url: str, path: str) -> bytes:
        return encode_value(forged_page)

    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    cp2.client.get = fake_get  # type: ignore[method-assign]
    cp2.client.post_json = fake_post  # type: ignore[method-assign]
    asyncio.run(cp2.sync_control_plane_events())
    assert "nonce" in cp2.broken_sync_reason


def test_sync_does_not_rebuild_user_projection_when_state_hash_mismatch(tmp_path: Path) -> None:
    cp1 = make_control_plane("cp-1", tmp_path / "cp-1-hash", ["http://cp-1:8734"])
    cp2 = make_control_plane("cp-2", tmp_path / "cp-2-hash", ["http://cp-2:8736"])
    initial = cp1.initialize_group("group-hash", 60)
    cp2.state_manager.replace_state(initial, trusted_leader_pubkey=initial.leader_pubkey)

    token = cp1.issue_bootstrap_token(60)
    joined = cp1.apply_join(JoinRequest(bootstrap_token=token, node=cp2.node_record()), 60)
    cp2.state_manager.replace_state(joined)
    cp2.event_manager.current = cp1.event_manager.current
    cp2.storage.save_control_plane_event_log(cp2.event_manager.current)
    cp2.user_state_manager.replace_state(cp1.user_state_manager.get_state())

    admin_key = Ed25519KeyPair.generate()
    bootstrap_request = GuiUserBootstrapRequest(
        bootstrap_token=cp1.issue_gui_bootstrap_token(60),
        user_id="admin",
        public_key=admin_key.public_key_b64(),
        control_plane_urls=["http://cp-1:8734"],
    )
    asyncio.run(
        cp1.handle_request(
            "POST",
            "/v1/gui/bootstrap-user",
            encode_value(bootstrap_request),
            RequestAuth(node_id="", timestamp=0, nonce="", signature=""),
            "",
        )
    )
    assert cp2.user_state_manager.find_user("admin") is None

    # Corrupt local projection intentionally while keeping event log intact.
    current_user_state = cp2.user_state_manager.get_state()
    cp2.user_state_manager.replace_state(
        UserState(version=current_user_state.version, users=[], event_log=[]),
    )
    assert cp2.user_state_manager.find_user("admin") is None

    async def fake_get(url: str, path: str) -> bytes:
        parsed = urlparse(path)
        query = parse_qs(parsed.query)
        after_event_id = int(query.get("after_event_id", ["0"])[0])
        limit = int(query.get("limit", ["250"])[0])
        return encode_value(cp1.event_manager.event_page("cp-1", after_event_id, limit))

    async def fake_post(*args: object, **kwargs: object) -> dict[str, str]:
        return {"status": "ok"}

    cp2.client.get = fake_get  # type: ignore[method-assign]
    cp2.client.post_json = fake_post  # type: ignore[method-assign]
    synced = asyncio.run(cp2.sync_logic.sync_events_from_urls(["http://cp-1:8734"], report_sync_status=False))
    assert synced is None
    assert cp2.user_state_manager.find_user("admin") is not None
    assert cp2.user_state_manager.get_state().event_log != cp1.user_state_manager.get_state().event_log


def test_revoke_unknown_node_is_rejected(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader-revoke", ["http://cp-a:8734"])
    leader.initialize_group("group-1", 60)

    with pytest.raises(TransportError, match="node not found"):
        leader.revoke_node("missing-node", 60)


def test_cannot_revoke_active_leader(tmp_path: Path) -> None:
    leader = make_control_plane("cp-a", tmp_path / "leader-self-revoke", ["http://cp-a:8734"])
    leader.initialize_group("group-1", 60)

    with pytest.raises(TransportError, match="cannot revoke active leader"):
        leader.revoke_node("cp-a", 60)
