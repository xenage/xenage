
from __future__ import annotations

from pathlib import Path

import pytest

from structures.resources.membership import GroupEndpoint, GroupState, NodeRecord
from xenage.cluster.state_manager import StateManager, StateValidationError
from xenage.crypto import Ed25519KeyPair
from xenage.persistence.storage_layer import StorageLayer


def test_state_manager_bootstrap_and_persist(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    key_pair = Ed25519KeyPair.generate()
    leader = NodeRecord(node_id="cp-1", role="control-plane", public_key=key_pair.public_key_b64(), endpoints=["http://cp-1:8734"])
    state = manager.bootstrap_state("group-1", leader, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, key_pair)
    reloaded = StorageLayer(tmp_path).load_group_state()
    assert reloaded is not None
    assert reloaded.version == 1
    assert state.leader_signature


def test_state_manager_rejects_regressing_epoch(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    key_pair = Ed25519KeyPair.generate()
    leader = NodeRecord(node_id="cp-1", role="control-plane", public_key=key_pair.public_key_b64(), endpoints=["http://cp-1:8734"])
    manager.bootstrap_state("group-1", leader, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, key_pair)
    lower_epoch = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=0,
        leader_node_id="cp-1",
        leader_pubkey=key_pair.public_key_b64(),
        control_planes=[leader],
        runtimes=[],
        endpoints=[GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")],
        expires_at="2030-01-01T00:00:00Z",
    )
    signed = manager.sign_state(lower_epoch, key_pair)
    with pytest.raises(StateValidationError):
        manager.replace_state(signed)


def test_initial_state_must_validate_against_trusted_cli_key(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    trusted = Ed25519KeyPair.generate()
    attacker = Ed25519KeyPair.generate()
    attacker_leader = NodeRecord(
        node_id="cp-evil",
        role="control-plane",
        public_key=attacker.public_key_b64(),
        endpoints=["http://cp-evil:8734"],
    )
    unsigned = GroupState(
        group_id="group-1",
        version=1,
        leader_epoch=1,
        leader_node_id="cp-evil",
        leader_pubkey=attacker.public_key_b64(),
        control_planes=[attacker_leader],
        runtimes=[],
        endpoints=[GroupEndpoint(node_id="cp-evil", url="http://cp-evil:8734")],
        expires_at="2030-01-01T00:00:00Z",
    )
    attacker_state = manager.sign_state(unsigned, attacker)
    with pytest.raises(StateValidationError, match="leader signature validation failed"):
        manager.replace_state(attacker_state, trusted_leader_pubkey=trusted.public_key_b64())


def test_rejects_signature_from_new_key_without_leader_rotation(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    leader = Ed25519KeyPair.generate()
    attacker = Ed25519KeyPair.generate()
    leader_record = NodeRecord(node_id="cp-1", role="control-plane", public_key=leader.public_key_b64(), endpoints=["http://cp-1:8734"])
    manager.bootstrap_state("group-1", leader_record, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, leader)

    forged = GroupState(
        group_id="group-1",
        version=2,
        leader_epoch=1,
        leader_node_id="cp-1",
        leader_pubkey=attacker.public_key_b64(),
        control_planes=[leader_record],
        runtimes=[],
        endpoints=[GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")],
        expires_at="2030-01-01T00:00:00Z",
    )
    signed_by_attacker = manager.sign_state(forged, attacker)
    with pytest.raises(StateValidationError, match="leader pubkey changed without leader rotation"):
        manager.replace_state(signed_by_attacker)


def test_leader_rotation_requires_previous_control_plane_membership(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    cp1 = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8734"])
    cp2 = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://cp-2:8734"])
    manager.bootstrap_state("group-1", cp1, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, cp1_key)

    state_with_cp2 = manager.build_next_state(
        leader_node_id="cp-1",
        leader_pubkey=cp1.public_key,
        control_planes=[cp1, cp2],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8734"),
        ],
        ttl_seconds=60,
        key_pair=cp1_key,
    )
    manager.replace_state(state_with_cp2)

    rotated_to_cp2 = manager.build_next_state(
        leader_node_id="cp-2",
        leader_pubkey=cp2.public_key,
        control_planes=[cp1, cp2],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8734"),
        ],
        ttl_seconds=60,
        key_pair=cp2_key,
        leader_epoch=state_with_cp2.leader_epoch + 1,
    )
    applied = manager.replace_state(rotated_to_cp2)
    assert applied.leader_node_id == "cp-2"

    cp3 = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8734"])
    invalid_rotation = manager.build_next_state(
        leader_node_id="cp-3",
        leader_pubkey=cp3.public_key,
        control_planes=[cp1, cp2, cp3],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8734"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8734"),
        ],
        ttl_seconds=60,
        key_pair=cp3_key,
        leader_epoch=applied.leader_epoch + 1,
    )
    with pytest.raises(StateValidationError, match="new leader was not present in previous control-plane set"):
        manager.replace_state(invalid_rotation)


def test_equal_epoch_conflict_converges_to_deterministic_leader(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    cp1 = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8734"])
    cp2 = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://cp-2:8734"])
    cp3 = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8734"])
    manager.bootstrap_state("group-1", cp1, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, cp1_key)
    with_members = manager.build_next_state(
        leader_node_id="cp-1",
        leader_pubkey=cp1.public_key,
        control_planes=[cp1, cp2, cp3],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8734"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8734"),
        ],
        ttl_seconds=60,
        key_pair=cp1_key,
    )
    manager.replace_state(with_members)

    current_as_cp3 = manager.build_next_state(
        leader_node_id="cp-3",
        leader_pubkey=cp3.public_key,
        control_planes=[cp1, cp2, cp3],
        runtimes=[],
        endpoints=with_members.endpoints,
        ttl_seconds=60,
        key_pair=cp3_key,
        leader_epoch=with_members.leader_epoch + 1,
    )
    manager.replace_state(current_as_cp3)

    competing_cp2_same_epoch = GroupState(
        group_id=current_as_cp3.group_id,
        version=current_as_cp3.version,
        leader_epoch=current_as_cp3.leader_epoch,
        leader_node_id="cp-2",
        leader_pubkey=cp2.public_key,
        control_planes=current_as_cp3.control_planes,
        runtimes=current_as_cp3.runtimes,
        endpoints=current_as_cp3.endpoints,
        expires_at=current_as_cp3.expires_at,
    )
    signed_competing = manager.sign_state(competing_cp2_same_epoch, cp2_key)
    resolved = manager.replace_state(signed_competing)
    assert resolved.leader_node_id == "cp-2"


def test_leader_rotation_allows_membership_catchup_superset(tmp_path: Path) -> None:
    storage = StorageLayer(tmp_path)
    manager = StateManager(storage)
    cp1_key = Ed25519KeyPair.generate()
    cp2_key = Ed25519KeyPair.generate()
    cp3_key = Ed25519KeyPair.generate()
    cp1 = NodeRecord(node_id="cp-1", role="control-plane", public_key=cp1_key.public_key_b64(), endpoints=["http://cp-1:8734"])
    cp2 = NodeRecord(node_id="cp-2", role="control-plane", public_key=cp2_key.public_key_b64(), endpoints=["http://cp-2:8734"])
    cp3 = NodeRecord(node_id="cp-3", role="control-plane", public_key=cp3_key.public_key_b64(), endpoints=["http://cp-3:8734"])
    manager.bootstrap_state("group-1", cp1, [GroupEndpoint(node_id="cp-1", url="http://cp-1:8734")], 60, cp1_key)

    # Simulate a stale follower that only knows cp-1 and cp-3.
    stale_with_cp3 = manager.build_next_state(
        leader_node_id="cp-1",
        leader_pubkey=cp1.public_key,
        control_planes=[cp1, cp3],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8734"),
        ],
        ttl_seconds=60,
        key_pair=cp1_key,
    )
    manager.replace_state(stale_with_cp3)

    # Incoming failover state from cp-2 includes previous members plus cp-2 (safe superset).
    promoted = GroupState(
        group_id=stale_with_cp3.group_id,
        version=stale_with_cp3.version + 1,
        leader_epoch=stale_with_cp3.leader_epoch + 1,
        leader_node_id="cp-2",
        leader_pubkey=cp2.public_key,
        control_planes=[cp1, cp2, cp3],
        runtimes=[],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://cp-1:8734"),
            GroupEndpoint(node_id="cp-2", url="http://cp-2:8734"),
            GroupEndpoint(node_id="cp-3", url="http://cp-3:8734"),
        ],
        expires_at="2030-01-01T00:00:00Z",
    )
    signed = manager.sign_state(promoted, cp2_key)
    applied = manager.replace_state(signed)
    assert applied.leader_node_id == "cp-2"
