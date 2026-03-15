from __future__ import annotations

from datetime import timedelta

from loguru import logger

from structures.resources.membership import GroupEndpoint, GroupState, NodeRecord, JoinRequest

from ..crypto import Ed25519KeyPair, normalize_public_key_b64, verify_signature
from ..serialization import encode_value
from ..persistence.storage_layer import StorageLayer
from .time_utils import format_timestamp, parse_timestamp, utc_now


class StateValidationError(RuntimeError):
    pass


class StateVersionRegressedError(StateValidationError):
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
            node_statuses=[],
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
            node_statuses=group_state.node_statuses,
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

    def _expected_signing_keys(self, new_state: GroupState, trusted_leader_pubkey: str | None) -> list[str]:
        trusted_leader_pubkey = normalize_public_key_b64(trusted_leader_pubkey)
        current_state = self.current_state
        if current_state is None:
            logger.debug(
                "validating first observed state version={} trusted_anchor_present={}",
                new_state.version,
                bool(trusted_leader_pubkey),
            )
            if not trusted_leader_pubkey:
                raise StateValidationError("trusted leader pubkey is required for initial state")
            return [trusted_leader_pubkey]

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
            raise StateVersionRegressedError("group_state version regressed")
        if new_state.leader_epoch < current_state.leader_epoch:
            raise StateVersionRegressedError("leader_epoch regressed")

        previous_control_plane_keys = {item.public_key for item in current_state.control_planes}

        if new_state.version == current_state.version:
            if (
                new_state.leader_node_id == current_state.leader_node_id
                and new_state.leader_pubkey == current_state.leader_pubkey
            ):
                return [current_state.leader_pubkey]
            
            if new_state.leader_epoch != current_state.leader_epoch:
                raise StateValidationError("version collision with different leader_epoch")
            
            if new_state.leader_pubkey not in previous_control_plane_keys:
                raise StateValidationError("new leader was not present in previous control-plane set")
            
            current_order = self._leader_order(current_state.leader_node_id, current_state.leader_pubkey)
            incoming_order = self._leader_order(new_state.leader_node_id, new_state.leader_pubkey)
            if incoming_order >= current_order:
                raise StateVersionRegressedError("group_state version is not newer")
            
            logger.warning(
                "resolving equal-version leader conflict version={} epoch={} from {} to {}",
                new_state.version,
                new_state.leader_epoch,
                current_state.leader_node_id,
                new_state.leader_node_id,
            )
            return [new_state.leader_pubkey]

        if new_state.leader_node_id == current_state.leader_node_id:
            if new_state.leader_pubkey != current_state.leader_pubkey:
                raise StateValidationError("leader pubkey changed without leader rotation")
            return [current_state.leader_pubkey]

        if new_state.leader_epoch == current_state.leader_epoch:
            if new_state.leader_pubkey not in previous_control_plane_keys:
                raise StateValidationError("new leader was not present in previous control-plane set")
            
            current_order = self._leader_order(current_state.leader_node_id, current_state.leader_pubkey)
            incoming_order = self._leader_order(new_state.leader_node_id, new_state.leader_pubkey)
            if incoming_order >= current_order:
                raise StateVersionRegressedError("leader rotation requires higher leader_epoch")
            
            logger.warning(
                "resolving equal-epoch leader conflict current_leader={} incoming_leader={} epoch={} versions {}->{}",
                current_state.leader_node_id,
                new_state.leader_node_id,
                new_state.leader_epoch,
                current_state.version,
                new_state.version,
            )
            return [new_state.leader_pubkey]

        # Leader rotation with epoch increment
        if new_state.leader_epoch > current_state.leader_epoch:
            if new_state.leader_pubkey not in previous_control_plane_keys:
                new_control_plane_keys = {cp.public_key for cp in new_state.control_planes}
                if new_state.leader_pubkey not in new_control_plane_keys:
                    raise StateValidationError(
                        f"new leader {new_state.leader_node_id} with pubkey {new_state.leader_pubkey} not present in new control-plane set"
                    )

                explicit_trust = trusted_leader_pubkey == new_state.leader_pubkey
                bootstrap_catchup = (
                    current_state.leader_epoch <= 1
                    and self._is_safe_membership_superset(current_state, new_state)
                )
                if not explicit_trust and not bootstrap_catchup:
                    raise StateValidationError("new leader was not present in previous control-plane set")

                logger.warning(
                    "accepting leader rotation with membership catch-up current_leader={} incoming_leader={} current_version={} incoming_version={} epoch={} trusted={} bootstrap_catchup={}",
                    current_state.leader_node_id,
                    new_state.leader_node_id,
                    current_state.version,
                    new_state.version,
                    new_state.leader_epoch,
                    explicit_trust,
                    bootstrap_catchup,
                )
            else:
                logger.debug(
                    "leader rotation detected previous_leader={} new_leader={}",
                    current_state.leader_node_id,
                    new_state.leader_node_id,
                )

            # If we don't know the new leader's pubkey, we MUST trust it now,
            # because it is a safe membership superset (or we have explicit trust) and they are promoting.
            # We can trust any known member from the previous control plane set to sign the new state.
            keys = list(previous_control_plane_keys) + [new_state.leader_pubkey]
            if trusted_leader_pubkey:
                keys.append(trusted_leader_pubkey)
            
            # Use stable unique list
            unique_keys = []
            for k in keys:
                if k and k not in unique_keys:
                    unique_keys.append(k)
            return unique_keys

    def validate_new_state(self, new_state: GroupState, trusted_leader_pubkey: str | None = None, verify_signature_required: bool = True) -> None:
        trusted_leader_pubkey = normalize_public_key_b64(trusted_leader_pubkey)
        expected_signing_keys = self._expected_signing_keys(new_state, trusted_leader_pubkey)
        if verify_signature_required:
            if not new_state.leader_signature:
                raise StateValidationError("leader signature is missing")
            
            valid = False
            for key in expected_signing_keys:
                if verify_signature(key, self.state_payload(new_state), new_state.leader_signature):
                    valid = True
                    break
            
            if not valid:
                raise StateValidationError("leader signature validation failed")
        logger.info(
            "validated group state version={} epoch={} leader={}",
            new_state.version,
            new_state.leader_epoch,
            new_state.leader_node_id,
        )

    def replace_state(self, new_state: GroupState, trusted_leader_pubkey: str | None = None, verify_signature_required: bool = True) -> GroupState:
        trusted_leader_pubkey = normalize_public_key_b64(trusted_leader_pubkey)
        logger.debug(
            "replacing state candidate_version={} candidate_leader={}",
            new_state.version,
            new_state.leader_node_id,
        )
        self.validate_new_state(new_state, trusted_leader_pubkey, verify_signature_required=verify_signature_required)
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
        increment_version: bool = True,
    ) -> GroupState:
        current_state = self.require_state()
        next_epoch = current_state.leader_epoch if leader_epoch is None else leader_epoch
        next_version = current_state.version + 1 if increment_version else current_state.version
        logger.debug(
            "building next state from version={} to version={} leader={} epoch={} cp_count={} rt_count={} endpoint_count={}",
            current_state.version,
            next_version,
            leader_node_id,
            next_epoch,
            len(control_planes),
            len(runtimes),
            len(endpoints),
        )
        candidate = GroupState(
            group_id=current_state.group_id,
            version=next_version,
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

    def is_expired(self, group_state: GroupState | None = None, margin_seconds: int = 0) -> bool:
        state = self.require_state() if group_state is None else group_state
        threshold = utc_now() + timedelta(seconds=margin_seconds)
        expired = parse_timestamp(state.expires_at) <= threshold
        logger.trace(
            "state expiry check version={} leader={} expired={} expires_at={} threshold={}",
            state.version,
            state.leader_node_id,
            expired,
            state.expires_at,
            format_timestamp(threshold),
        )
        return expired

    def build_join_request(self, bootstrap_token: str, node_id: str, endpoints: list[str]) -> JoinRequest:
        identity = self.storage.load_identity()
        return JoinRequest(
            bootstrap_token=bootstrap_token,
            node=NodeRecord(
                node_id=node_id,
                role=identity.role,
                public_key=identity.public_key,
                endpoints=endpoints,
            ),
        )
