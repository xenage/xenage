from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from structures.resources.membership import (
    ClusterNodeTableRow,
    EndpointUpdateRequest,
    GroupConfigKeyTableRow,
    GroupEndpoint,
    GroupState,
    GuiClusterSnapshot,
    GuiConnectionConfig,
    JoinRequest,
    JoinResponse,
    NodeRecord,
    RequestAuth,
    RevokeNodeRequest,
    UserRecord,
    UserState,
    UserStatePublishRequest,
)

from ..cluster.time_utils import parse_timestamp, utc_now
from ..serialization import decode_value
from ..crypto import Ed25519KeyPair
from ..tokens import BootstrapTokenManager, TokenValidationError
from ..network.http_transport import TransportError
from .base import BaseNode


def sort_control_planes(control_planes: list[NodeRecord]) -> list[NodeRecord]:
    return sorted(control_planes, key=lambda item: (item.node_id, item.public_key))


class ControlPlaneNode(BaseNode):
    def __init__(
        self,
        node_id: str,
        storage_path: Path,
        endpoints: list[str],
        log_level: str = "INFO",
        state_ttl_seconds: int = 60,
        failover_escalation_seconds: int = 60,
    ) -> None:
        super().__init__(node_id, "control-plane", storage_path, endpoints, log_level)
        self.tokens = BootstrapTokenManager()
        self.state_ttl_seconds = state_ttl_seconds
        self.failover_escalation_seconds = failover_escalation_seconds
        logger.debug(
            "control-plane node ready node_id={} state_ttl_seconds={} failover_escalation_seconds={}",
            self.identity.node_id,
            self.state_ttl_seconds,
            self.failover_escalation_seconds,
        )

    def publish_user_state_to_control_planes(self, user_state: UserState) -> dict[str, bool]:
        state = self.state_manager.get_state()
        if state is None:
            return {}
        endpoint_map: dict[str, list[str]] = {}
        control_plane_ids = {item.node_id for item in state.control_planes if item.node_id != self.identity.node_id}
        for endpoint in state.endpoints:
            if endpoint.node_id not in control_plane_ids:
                continue
            endpoint_map.setdefault(endpoint.node_id, []).append(endpoint.url)
        results: dict[str, bool] = {}
        for node_id, urls in endpoint_map.items():
            delivered = False
            for url in urls:
                try:
                    self.client.post_json(
                        url,
                        "/v1/users/publish",
                        UserStatePublishRequest(user_state=user_state),
                        UserState,
                    )
                    delivered = True
                    break
                except TransportError as exc:
                    logger.error("failed to publish user state to {} ({}): {}", node_id, url, exc)
            results[node_id] = delivered
        logger.trace("user state publish results version={} delivered={}", user_state.version, results)
        return results

    def append_cluster_event(self, action: str, details: dict[str, str]) -> UserState:
        updated = self.user_state_manager.append_event(self.identity.node_id, "node", action, details)
        if self.is_leader():
            self.publish_user_state_to_control_planes(updated)
        return updated

    def ensure_admin_user(self, user_id: str, public_key: str) -> UserRecord:
        user = self.user_state_manager.ensure_admin(user_id, public_key)
        self.append_cluster_event("rbac.admin.user.upsert", {"user_id": user_id})
        return user

    def issue_gui_connection_config(self, control_plane_urls: list[str] | str | None = None, user_id: str = "admin") -> GuiConnectionConfig:
        self.require_leader()
        user_key = Ed25519KeyPair.generate()
        self.ensure_admin_user(user_id, user_key.public_key_b64())
        state = self.state_manager.require_state()
        derived_urls = []
        control_plane_ids = {item.node_id for item in state.control_planes}
        for endpoint in state.endpoints:
            if endpoint.node_id in control_plane_ids:
                derived_urls.append(endpoint.url)
        if isinstance(control_plane_urls, str):
            normalized_urls = [control_plane_urls]
        else:
            normalized_urls = control_plane_urls
        urls = normalized_urls if normalized_urls else sorted(set(derived_urls))
        if not urls:
            raise TransportError("no control-plane urls available for gui config")
        return GuiConnectionConfig(
            cluster_name=state.group_id,
            control_plane_urls=urls,
            user_id=user_id,
            role="admin",
            public_key=user_key.public_key_b64(),
            private_key=user_key.private_key_b64(),
        )

    def verify_admin_user(self, auth: RequestAuth, public_key: str) -> None:
        self.user_state_manager.refresh_from_storage()
        user = self.user_state_manager.find_user(auth.node_id)
        if user is None:
            raise TransportError("unknown user id")
        if not user.enabled:
            raise TransportError("user is disabled")
        if user.public_key != public_key:
            raise TransportError("request signer public key does not match stored user key")
        roles = {binding.role for binding in user.roles}
        if "admin" not in roles:
            raise TransportError("user is not authorized")

    def build_gui_snapshot(self) -> GuiClusterSnapshot:
        state = self.state_manager.require_state()
        user_state = self.user_state_manager.get_state()
        control_plane_ids = {item.node_id for item in state.control_planes}
        rows: list[ClusterNodeTableRow] = []
        for node in [*state.control_planes, *state.runtimes]:
            rows.append(
                ClusterNodeTableRow(
                    node_id=node.node_id,
                    role=node.role,
                    leader=node.node_id == state.leader_node_id and node.node_id in control_plane_ids,
                    public_key=node.public_key,
                    endpoints=node.endpoints,
                ),
            )
        config_rows = [
            GroupConfigKeyTableRow(key="group_id", value=state.group_id),
            GroupConfigKeyTableRow(key="version", value=str(state.version)),
            GroupConfigKeyTableRow(key="leader_epoch", value=str(state.leader_epoch)),
            GroupConfigKeyTableRow(key="leader_node_id", value=state.leader_node_id),
            GroupConfigKeyTableRow(key="leader_pubkey", value=state.leader_pubkey),
            GroupConfigKeyTableRow(key="expires_at", value=state.expires_at),
            GroupConfigKeyTableRow(key="control_plane_count", value=str(len(state.control_planes))),
            GroupConfigKeyTableRow(key="runtime_count", value=str(len(state.runtimes))),
            GroupConfigKeyTableRow(key="endpoint_count", value=str(len(state.endpoints))),
        ]
        return GuiClusterSnapshot(
            group_id=state.group_id,
            state_version=state.version,
            leader_epoch=state.leader_epoch,
            nodes=sorted(rows, key=lambda item: (item.role, item.node_id)),
            group_config=config_rows,
            event_log=list(reversed(user_state.event_log[-200:])),
            users=user_state.users,
        )

    def initialize_group(self, group_id: str, ttl_seconds: int) -> GroupState:
        logger.info("bootstrapping self-managed group group_id={}", group_id)
        state = self.state_manager.bootstrap_state(
            group_id,
            self.node_record(),
            [GroupEndpoint(node_id=self.identity.node_id, url=url) for url in self.identity.endpoints],
            ttl_seconds,
            self.key_pair,
        )
        self.append_cluster_event("cluster.bootstrap", {"group_id": group_id, "leader_node_id": self.identity.node_id})
        return state

    def sync_state_from_leader(self) -> GroupState | None:
        state = self.state_manager.get_state()
        if state is None or state.leader_node_id == self.identity.node_id:
            return None
        leader_urls = [item.url for item in state.endpoints if item.node_id == state.leader_node_id]
        for leader_url in leader_urls:
            try:
                payload = self.client.get(leader_url, "/v1/state/current")
                incoming = decode_value(payload, GroupState)
                current = self.state_manager.get_state()
                if current is None:
                    return self.state_manager.replace_state(incoming, trusted_leader_pubkey=incoming.leader_pubkey)
                if incoming.version > current.version:
                    logger.info(
                        "synchronized state from leader leader={} previous_version={} incoming_version={}",
                        state.leader_node_id,
                        current.version,
                        incoming.version,
                    )
                    return self.state_manager.replace_state(incoming)
                return current
            except Exception as exc:
                logger.debug("failed to synchronize state from leader url={} reason={}", leader_url, exc)
        return None

    @staticmethod
    def _state_rank(state: GroupState) -> tuple[int, int, str]:
        return (state.version, state.leader_epoch, state.leader_node_id)

    def sync_state_from_control_planes(self) -> GroupState | None:
        current = self.state_manager.get_state()
        if current is None:
            return None
        control_plane_ids = {item.node_id for item in current.control_planes if item.node_id != self.identity.node_id}
        candidate_urls = [item.url for item in current.endpoints if item.node_id in control_plane_ids]
        best_state = current
        for url in candidate_urls:
            try:
                payload = self.client.get(url, "/v1/state/current")
                incoming = decode_value(payload, GroupState)
                if self._state_rank(incoming) > self._state_rank(best_state):
                    best_state = incoming
            except Exception as exc:
                logger.debug("control-plane sync probe failed url={} reason={}", url, exc)
        if best_state is current:
            logger.trace(
                "control-plane sync no newer peer state local_node_id={} local_leader={} local_version={}",
                self.identity.node_id,
                current.leader_node_id,
                current.version,
            )
            return current
        try:
            applied = self.state_manager.replace_state(best_state)
            logger.info(
                "control-plane synchronized from peers node_id={} previous_version={} new_version={} leader={}",
                self.identity.node_id,
                current.version,
                applied.version,
                applied.leader_node_id,
            )
            return applied
        except Exception as exc:
            logger.warning(
                "control-plane sync rejected newer peer state node_id={} candidate_version={} reason={}",
                self.identity.node_id,
                best_state.version,
                exc,
            )
            return current

    def is_leader(self) -> bool:
        state = self.state_manager.get_state()
        return state is not None and state.leader_node_id == self.identity.node_id

    def require_leader(self) -> GroupState:
        state = self.state_manager.require_state()
        if state.leader_node_id != self.identity.node_id:
            raise TransportError("node is not the active leader")
        return state

    def issue_bootstrap_token(self, ttl_seconds: int) -> str:
        self.require_leader()
        token = self.tokens.issue_token(ttl_seconds).token
        logger.debug("issued bootstrap token leader={} ttl_seconds={}", self.identity.node_id, ttl_seconds)
        return token

    def join_peer(self, leader_host: str, leader_pubkey: str, bootstrap_token: str) -> GroupState:
        logger.info("joining control-plane node_id={} via leader={}", self.identity.node_id, leader_host)
        response = self.client.post_json(
            leader_host,
            "/v1/join",
            JoinRequest(bootstrap_token=bootstrap_token, node=self.node_record()),
            JoinResponse,
        )
        if not isinstance(response, JoinResponse) or not response.accepted or response.group_state is None:
            raise TransportError(response.reason or "leader rejected join request")
        if response.group_state.leader_pubkey != leader_pubkey:
            raise TransportError("leader pubkey mismatch in group state")
        current_state = self.state_manager.get_state()
        if current_state is not None and current_state.version >= response.group_state.version:
            return current_state
        trust_anchor = leader_pubkey if current_state is None else None
        return self.state_manager.replace_state(response.group_state, trusted_leader_pubkey=trust_anchor)

    def revoke_node(self, node_id: str, ttl_seconds: int) -> GroupState:
        self.require_leader()
        logger.debug("revoking node node_id={} ttl_seconds={}", node_id, ttl_seconds)
        state = self.state_manager.require_state()
        control_planes = [item for item in state.control_planes if item.node_id != node_id]
        runtimes = [item for item in state.runtimes if item.node_id != node_id]
        endpoints = [item for item in state.endpoints if item.node_id != node_id]
        next_state = self.state_manager.build_next_state(
            self.identity.node_id,
            self.identity.public_key,
            sort_control_planes(control_planes),
            runtimes,
            endpoints,
            ttl_seconds,
            self.key_pair,
        )
        applied = self.state_manager.replace_state(next_state)
        self.publish_state_to_members(applied, target_roles={"control-plane"})
        self.append_cluster_event("cluster.node.revoked", {"node_id": node_id, "state_version": str(applied.version)})
        logger.info("revoked node node_id={} version={}", node_id, applied.version)
        return applied

    def update_node_endpoints(self, node_id: str, endpoints: list[str], ttl_seconds: int) -> GroupState:
        self.require_leader()
        logger.debug(
            "updating node endpoints node_id={} endpoint_count={} ttl_seconds={}",
            node_id,
            len(endpoints),
            ttl_seconds,
        )
        state = self.state_manager.require_state()
        control_planes = [
            NodeRecord(node_id=item.node_id, role=item.role, public_key=item.public_key, endpoints=endpoints if item.node_id == node_id else item.endpoints)
            for item in state.control_planes
        ]
        runtimes = [
            NodeRecord(node_id=item.node_id, role=item.role, public_key=item.public_key, endpoints=endpoints if item.node_id == node_id else item.endpoints)
            for item in state.runtimes
        ]
        merged_endpoints = [item for item in state.endpoints if item.node_id != node_id]
        merged_endpoints.extend(GroupEndpoint(node_id=node_id, url=url) for url in endpoints)
        next_state = self.state_manager.build_next_state(
            self.identity.node_id,
            self.identity.public_key,
            sort_control_planes(control_planes),
            runtimes,
            sorted(merged_endpoints, key=lambda item: (item.node_id, item.url)),
            ttl_seconds,
            self.key_pair,
        )
        applied = self.state_manager.replace_state(next_state)
        self.publish_state_to_members(applied, target_roles={"control-plane"})
        self.append_cluster_event("cluster.node.endpoints.updated", {"node_id": node_id, "state_version": str(applied.version)})
        logger.info("updated endpoints node_id={} version={}", node_id, applied.version)
        return applied

    def apply_join(self, join_request: JoinRequest, ttl_seconds: int) -> GroupState:
        state = self.require_leader()
        logger.debug(
            "applying join request node_id={} role={} ttl_seconds={}",
            join_request.node.node_id,
            join_request.node.role,
            ttl_seconds,
        )
        self.tokens.validate(join_request.bootstrap_token)
        self.tokens.mark_used(join_request.bootstrap_token)
        new_node = join_request.node
        control_planes = [item for item in state.control_planes if item.node_id != new_node.node_id]
        runtimes = [item for item in state.runtimes if item.node_id != new_node.node_id]
        if new_node.role == "control-plane":
            control_planes.append(new_node)
        else:
            runtimes.append(new_node)
        endpoints = [item for item in state.endpoints if item.node_id != new_node.node_id]
        endpoints.extend(GroupEndpoint(node_id=new_node.node_id, url=url) for url in new_node.endpoints)
        next_state = self.state_manager.build_next_state(
            self.identity.node_id,
            self.identity.public_key,
            sort_control_planes(control_planes),
            sorted(runtimes, key=lambda item: (item.node_id, item.public_key)),
            sorted(endpoints, key=lambda item: (item.node_id, item.url)),
            ttl_seconds,
            self.key_pair,
        )
        applied = self.state_manager.replace_state(next_state)
        self.publish_state_to_members(applied, target_roles={"control-plane"})
        self.append_cluster_event(
            "cluster.node.joined",
            {
                "node_id": new_node.node_id,
                "role": new_node.role,
                "state_version": str(applied.version),
            },
        )
        logger.info("accepted join node_id={} role={} version={}", new_node.node_id, new_node.role, applied.version)
        return applied

    def current_failover_candidate(self, state: GroupState) -> NodeRecord | None:
        ordered = sort_control_planes(state.control_planes)
        node_ids = [item.node_id for item in ordered]
        if state.leader_node_id not in node_ids:
            return None
        leader_index = node_ids.index(state.leader_node_id)
        elapsed_seconds = max(0, int((utc_now() - parse_timestamp(state.expires_at)).total_seconds()))
        minute_slot = elapsed_seconds // self.failover_escalation_seconds
        candidate_index = (leader_index + 1 + minute_slot) % len(ordered)
        candidate = ordered[candidate_index]
        logger.trace(
            "failover candidate evaluated leader={} candidate={} elapsed_seconds={} minute_slot={}",
            state.leader_node_id,
            candidate.node_id,
            elapsed_seconds,
            minute_slot,
        )
        return candidate

    def publish_failover_state(self, promoted_state: GroupState, previous_leader_node_id: str) -> bool:
        control_plane_ids = {
            item.node_id
            for item in promoted_state.control_planes
            if item.node_id not in {self.identity.node_id, previous_leader_node_id}
        }
        if not control_plane_ids:
            self.publish_state_to_members(promoted_state, target_roles={"control-plane"})
            return True
        logger.debug(
            "publishing failover state version={} previous_leader={} target_control_planes={}",
            promoted_state.version,
            previous_leader_node_id,
            sorted(control_plane_ids),
        )
        deadline = time.monotonic() + self.failover_escalation_seconds
        while True:
            results = self.publish_state_to_members(promoted_state, target_roles={"control-plane"})
            pending = [node_id for node_id in control_plane_ids if not results.get(node_id, False)]
            if not pending:
                return True
            if time.monotonic() >= deadline:
                logger.warning("failover publish timeout pending_control_planes={}", pending)
                return False
            time.sleep(2)

    def check_failover(self, ttl_seconds: int) -> GroupState | None:
        state = self.state_manager.get_state()
        if state is None:
            logger.trace("failover check skipped state_missing node_id={}", self.identity.node_id)
            return None
        self.sync_state_from_control_planes()
        state = self.state_manager.get_state()
        if state is None or state.leader_node_id == self.identity.node_id:
            return None
        logger.debug(
            "running failover check node_id={} leader_node_id={} ttl_seconds={} endpoint_count={}",
            self.identity.node_id,
            state.leader_node_id,
            ttl_seconds,
            len(state.endpoints),
        )
        leader_urls = [item.url for item in state.endpoints if item.node_id == state.leader_node_id]
        for leader_url in leader_urls:
            try:
                self.client.get(leader_url, "/v1/heartbeat")
                logger.info(
                    "leader heartbeat succeeded; failover not needed local_node_id={} current_leader={}",
                    self.identity.node_id,
                    state.leader_node_id,
                )
                return None
            except TransportError:
                logger.warning("leader heartbeat failed url={}", leader_url)
        expires_at = parse_timestamp(state.expires_at)
        seconds_until_update = max(0, int((expires_at - utc_now()).total_seconds()))
        logger.warning(
            "leader-heartbeat-failed node_id={} leader={} seconds_until_control_plane_update={}",
            self.identity.node_id,
            state.leader_node_id,
            seconds_until_update,
        )
        if not self.state_manager.is_expired(state):
            return None
        candidate = self.current_failover_candidate(state)
        if candidate is None:
            return None
        if candidate.node_id != self.identity.node_id:
            logger.info("leader expired but current failover candidate is {}", candidate.node_id)
            return None
        ordered = sort_control_planes(state.control_planes)
        previous_leader_node_id = state.leader_node_id
        next_state = self.state_manager.build_next_state(
            self.identity.node_id,
            self.identity.public_key,
            ordered,
            state.runtimes,
            state.endpoints,
            ttl_seconds,
            self.key_pair,
            leader_epoch=state.leader_epoch + 1,
        )
        applied = self.state_manager.replace_state(next_state)
        published = self.publish_failover_state(applied, previous_leader_node_id)
        if published:
            logger.warning("failover promoted node_id={} epoch={}", self.identity.node_id, applied.leader_epoch)
            self.append_cluster_event(
                "cluster.failover.promoted",
                {
                    "leader_node_id": self.identity.node_id,
                    "previous_leader_node_id": previous_leader_node_id,
                    "leader_epoch": str(applied.leader_epoch),
                },
            )
            return applied
        logger.warning("failover publish did not reach all control-planes in {} seconds", self.failover_escalation_seconds)
        return None

    def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> GroupState | JoinResponse | UserState | GuiClusterSnapshot | dict[str, str]:
        logger.debug("control-plane route dispatch method={} path={} auth_node_id={}", method, path, auth.node_id)
        if method == "POST" and path == "/v1/join":
            join_request = decode_value(body, JoinRequest)
            if join_request.node.node_id != auth.node_id:
                raise TransportError("join request node_id does not match signed node_id")
            if join_request.node.public_key != public_key:
                raise TransportError("join request public key does not match signer public key")
            try:
                group_state = self.apply_join(join_request, ttl_seconds=self.state_ttl_seconds)
                return JoinResponse(accepted=True, group_state=group_state)
            except TokenValidationError as exc:
                return JoinResponse(accepted=False, reason=str(exc))
        if method == "POST" and path == "/v1/revoke":
            revoke_request = decode_value(body, RevokeNodeRequest)
            return self.revoke_node(revoke_request.node_id, ttl_seconds=self.state_ttl_seconds)
        if method == "POST" and path == "/v1/endpoints":
            update_request = decode_value(body, EndpointUpdateRequest)
            return self.update_node_endpoints(update_request.node_id, update_request.endpoints, ttl_seconds=self.state_ttl_seconds)
        if method == "GET" and path == "/v1/gui/cluster":
            self.require_leader()
            self.verify_admin_user(auth, public_key)
            self.append_cluster_event("gui.cluster.snapshot.read", {"user_id": auth.node_id})
            return self.build_gui_snapshot()
        if method == "GET" and path == "/v1/state/current":
            return self.state_manager.require_state()
        return super().handle_request(method, path, body, auth, public_key)
