from __future__ import annotations

from datetime import timedelta

from loguru import logger

from structures.resources.membership import GroupEndpoint, GroupState, NodeRecord

from ..crypto import Ed25519KeyPair, verify_signature
from ..serialization import encode_value
from ..persistence.storage_layer import StorageLayer
from .time_utils import format_timestamp, parse_timestamp, utc_now


class StateValidationError(RuntimeError):
    pass


class StateManager:
    def __init__(self, storage: StorageLayer) -> None:
        self.storage = storage
        self.current_state: GroupState | None = storage.load_group_state()
        if self.current_state is None:
            logger.debug("state manager initialized without an existing state")
        else:
            logger.debug(
                "state manager initialized version={} leader={} epoch={}",
                self.current_state.version,
                self.current_state.leader_node_id,
                self.current_state.leader_epoch,
            )

    def get_state(self) -> GroupState | None:
        return self.current_state

    def state_payload(self, group_state: GroupState) -> bytes:
        logger.trace(
            "building unsigned state payload version={} leader={} epoch={}",
            group_state.version,
            group_state.leader_node_id,
            group_state.leader_epoch,
        )
        unsigned_state = GroupState(
            group_id=group_state.group_id,
            version=group_state.version,
            leader_epoch=group_state.leader_epoch,
            leader_node_id=group_state.leader_node_id,
            leader_pubkey=group_state.leader_pubkey,
            control_planes=group_state.control_planes,
            runtimes=group_state.runtimes,
            endpoints=group_state.endpoints,
            expires_at=group_state.expires_at,
            leader_signature="",
        )
        payload = encode_value(unsigned_state)
        logger.trace("unsigned state payload bytes={}", len(payload))
        return payload

    def sign_state(self, group_state: GroupState, key_pair: Ed25519KeyPair) -> GroupState:
        logger.debug(
            "signing state version={} leader={} epoch={}",
            group_state.version,
            group_state.leader_node_id,
            group_state.leader_epoch,
        )
        signature = key_pair.sign(self.state_payload(group_state))
        signed = GroupState(
            group_id=group_state.group_id,
            version=group_state.version,
            leader_epoch=group_state.leader_epoch,
            leader_node_id=group_state.leader_node_id,
            leader_pubkey=group_state.leader_pubkey,
            control_planes=group_state.control_planes,
            runtimes=group_state.runtimes,
            endpoints=group_state.endpoints,
            expires_at=group_state.expires_at,
            leader_signature=signature,
        )
        logger.trace("state signature length={} chars", len(signature))
        return signed

    @staticmethod
    def _leader_order(node_id: str, pubkey: str) -> tuple[str, str]:
        return (node_id, pubkey)

    @staticmethod
    def _control_plane_keyset(state: GroupState) -> set[tuple[str, str]]:
        return {(item.node_id, item.public_key) for item in state.control_planes}

    @staticmethod
    def _is_safe_membership_superset(current_state: GroupState, new_state: GroupState) -> bool:
        current_keys = StateManager._control_plane_keyset(current_state)
        new_keys = StateManager._control_plane_keyset(new_state)
        return current_keys.issubset(new_keys)

    def _expected_signing_key(self, new_state: GroupState, trusted_leader_pubkey: str | None) -> str:
        current_state = self.current_state
        if current_state is None:
            logger.debug(
                "validating first observed state version={} trusted_anchor_present={}",
                new_state.version,
                bool(trusted_leader_pubkey),
            )
            if not trusted_leader_pubkey:
                raise StateValidationError("trusted leader pubkey is required for initial state")
            return trusted_leader_pubkey

        logger.trace(
            "comparing state transition current_version={} new_version={} current_epoch={} new_epoch={}",
            current_state.version,
            new_state.version,
            current_state.leader_epoch,
            new_state.leader_epoch,
        )
        if new_state.group_id != current_state.group_id:
            raise StateValidationError("group_id mismatch")
        if new_state.version < current_state.version:
            raise StateValidationError("group_state version regressed")
        if new_state.leader_epoch < current_state.leader_epoch:
            raise StateValidationError("leader_epoch regressed")

        if new_state.version == current_state.version:
            if (
                new_state.leader_node_id == current_state.leader_node_id
                and new_state.leader_pubkey == current_state.leader_pubkey
            ):
                raise StateValidationError("group_state version is not newer")
            if new_state.leader_epoch != current_state.leader_epoch:
                raise StateValidationError("version collision with different leader_epoch")
            previous_control_plane_keys = {
                (item.node_id, item.public_key) for item in current_state.control_planes
            }
            if (new_state.leader_node_id, new_state.leader_pubkey) not in previous_control_plane_keys:
                raise StateValidationError("new leader was not present in previous control-plane set")
            current_order = self._leader_order(current_state.leader_node_id, current_state.leader_pubkey)
            incoming_order = self._leader_order(new_state.leader_node_id, new_state.leader_pubkey)
            if incoming_order >= current_order:
                raise StateValidationError("group_state version is not newer")
            logger.warning(
                "resolving equal-version leader conflict version={} epoch={} from {} to {}",
                new_state.version,
                new_state.leader_epoch,
                current_state.leader_node_id,
                new_state.leader_node_id,
            )
            return new_state.leader_pubkey

        if new_state.leader_node_id == current_state.leader_node_id:
            if new_state.leader_pubkey != current_state.leader_pubkey:
                raise StateValidationError("leader pubkey changed without leader rotation")
            return current_state.leader_pubkey

        if new_state.leader_epoch == current_state.leader_epoch:
            previous_control_plane_keys = {
                (item.node_id, item.public_key) for item in current_state.control_planes
            }
            if (new_state.leader_node_id, new_state.leader_pubkey) not in previous_control_plane_keys:
                raise StateValidationError("new leader was not present in previous control-plane set")
            current_order = self._leader_order(current_state.leader_node_id, current_state.leader_pubkey)
            incoming_order = self._leader_order(new_state.leader_node_id, new_state.leader_pubkey)
            if incoming_order >= current_order:
                raise StateValidationError("leader rotation requires higher leader_epoch")
            logger.warning(
                "resolving equal-epoch leader conflict current_leader={} incoming_leader={} epoch={} versions {}->{}",
                current_state.leader_node_id,
                new_state.leader_node_id,
                new_state.leader_epoch,
                current_state.version,
                new_state.version,
            )
            return new_state.leader_pubkey

        if new_state.leader_epoch < current_state.leader_epoch:
            raise StateValidationError("leader_epoch regressed")
        previous_control_plane_keys = self._control_plane_keyset(current_state)
        if (new_state.leader_node_id, new_state.leader_pubkey) not in previous_control_plane_keys:
            if not self._is_safe_membership_superset(current_state, new_state):
                raise StateValidationError("new leader was not present in previous control-plane set")
            logger.warning(
                "accepting leader rotation with membership catch-up current_leader={} incoming_leader={} current_version={} incoming_version={}",
                current_state.leader_node_id,
                new_state.leader_node_id,
                current_state.version,
                new_state.version,
            )
        logger.debug(
            "leader rotation detected previous_leader={} new_leader={}",
            current_state.leader_node_id,
            new_state.leader_node_id,
        )
        return new_state.leader_pubkey

    def validate_new_state(self, new_state: GroupState, trusted_leader_pubkey: str | None = None) -> None:
        expected_signing_key = self._expected_signing_key(new_state, trusted_leader_pubkey)
        if not verify_signature(expected_signing_key, self.state_payload(new_state), new_state.leader_signature):
            raise StateValidationError("leader signature validation failed")
        logger.info(
            "validated group state version={} epoch={} leader={}",
            new_state.version,
            new_state.leader_epoch,
            new_state.leader_node_id,
        )

    def replace_state(self, new_state: GroupState, trusted_leader_pubkey: str | None = None) -> GroupState:
        logger.debug(
            "replacing state candidate_version={} candidate_leader={}",
            new_state.version,
            new_state.leader_node_id,
        )
        self.validate_new_state(new_state, trusted_leader_pubkey)
        self.current_state = new_state
        self.storage.save_group_state(new_state)
        logger.trace("state replacement complete version={}", new_state.version)
        return new_state

    def bootstrap_state(
        self,
        group_id: str,
        leader: NodeRecord,
        endpoints: list[GroupEndpoint],
        ttl_seconds: int,
        key_pair: Ed25519KeyPair,
    ) -> GroupState:
        logger.debug(
            "bootstrapping state group_id={} leader={} ttl={} endpoint_count={}",
            group_id,
            leader.node_id,
            ttl_seconds,
            len(endpoints),
        )
        state = GroupState(
            group_id=group_id,
            version=1,
            leader_epoch=1,
            leader_node_id=leader.node_id,
            leader_pubkey=leader.public_key,
            control_planes=[leader],
            runtimes=[],
            endpoints=endpoints,
            expires_at=format_timestamp(utc_now() + timedelta(seconds=ttl_seconds)),
        )
        signed_state = self.sign_state(state, key_pair)
        self.current_state = signed_state
        self.storage.save_group_state(signed_state)
        logger.info("bootstrap state created group_id={} leader={} version=1", group_id, leader.node_id)
        return signed_state

    def build_next_state(
        self,
        leader_node_id: str,
        leader_pubkey: str,
        control_planes: list[NodeRecord],
        runtimes: list[NodeRecord],
        endpoints: list[GroupEndpoint],
        ttl_seconds: int,
        key_pair: Ed25519KeyPair,
        leader_epoch: int | None = None,
    ) -> GroupState:
        current_state = self.require_state()
        next_epoch = current_state.leader_epoch if leader_epoch is None else leader_epoch
        logger.debug(
            "building next state from version={} to version={} leader={} epoch={} cp_count={} rt_count={} endpoint_count={}",
            current_state.version,
            current_state.version + 1,
            leader_node_id,
            next_epoch,
            len(control_planes),
            len(runtimes),
            len(endpoints),
        )
        candidate = GroupState(
            group_id=current_state.group_id,
            version=current_state.version + 1,
            leader_epoch=next_epoch,
            leader_node_id=leader_node_id,
            leader_pubkey=leader_pubkey,
            control_planes=control_planes,
            runtimes=runtimes,
            endpoints=endpoints,
            expires_at=format_timestamp(utc_now() + timedelta(seconds=ttl_seconds)),
        )
        return self.sign_state(candidate, key_pair)

    def require_state(self) -> GroupState:
        if self.current_state is None:
            logger.debug("state is required but not initialized")
            raise StateValidationError("group state is not initialized")
        return self.current_state

    def is_expired(self, group_state: GroupState | None = None) -> bool:
        state = self.require_state() if group_state is None else group_state
        expired = parse_timestamp(state.expires_at) <= utc_now()
        logger.trace(
            "state expiry check version={} leader={} expired={} expires_at={}",
            state.version,
            state.leader_node_id,
            expired,
            state.expires_at,
        )
        return expired
