from __future__ import annotations

from pathlib import Path
from loguru import logger

from structures.resources.events import (
    ClusterAuditEventBase,
    ControlPlaneEventPage,
)
from structures.resources.membership import (
    GroupNodeSyncStatus,
    GroupState,
    GuiClusterSnapshot,
    GuiEventPage,
    JoinRequest,
    JoinResponse,
    NodeRecord,
    RequestAuth,
    NodeSyncPhase,
    UserRecord,
)

from ...cluster.control_plane_event_manager import ControlPlaneEventManager
from ...cluster.user_state_compat import UserStateCompat
from ...cluster.time_utils import format_timestamp, utc_now
from ...network.http_transport import TransportError
from ...tokens import BootstrapTokenManager
from ..base import BaseNode

from .utils import sort_control_planes
from .sync_logic import ControlPlaneSyncLogic
from .state_logic import ControlPlaneStateLogic
from .control_plane_api.urls_logic import ControlPlaneUrlsLogic


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
        self.gui_tokens = BootstrapTokenManager(self.storage, "gui_bootstrap_tokens")
        self.state_ttl_seconds = state_ttl_seconds
        self.failover_escalation_seconds = failover_escalation_seconds
        self.last_poll_success_by_node: dict[str, str] = {}
        self.sync_status_by_node: dict[str, GroupNodeSyncStatus] = {}
        self.broken_sync_reason = ""
        
        self.event_manager = ControlPlaneEventManager(self.storage, self.state_manager, self.rbac_state_manager)
        self.user_state_manager = UserStateCompat(self)
        
        self.sync_logic = ControlPlaneSyncLogic(self)
        self.state_logic = ControlPlaneStateLogic(self)
        self.api_logic = ControlPlaneUrlsLogic(self)
        
        self.set_local_sync_status("synced")
        
        logger.debug(
            "control-plane node ready node_id={} state_ttl_seconds={} failover_escalation_seconds={} event_head={}",
            self.identity.node_id,
            self.state_ttl_seconds,
            self.failover_escalation_seconds,
            self.event_manager.get_last_event_id(),
        )

    def set_local_sync_status(self, status: NodeSyncPhase, reason: str = "") -> None:
        self.sync_status_by_node[self.identity.node_id] = GroupNodeSyncStatus(
            node_id=self.identity.node_id,
            status=status,
            reason=reason,
            updated_at=format_timestamp(utc_now()),
        )

    def upsert_sync_status(self, node_id: str, status: NodeSyncPhase, reason: str = "") -> GroupNodeSyncStatus:
        item = GroupNodeSyncStatus(
            node_id=node_id,
            status=status,
            reason=reason,
            updated_at=format_timestamp(utc_now()),
        )
        self.sync_status_by_node[node_id] = item
        return item

    def state_with_sync_statuses(self, state: GroupState) -> GroupState:
        status_by_node = {item.node_id: item for item in state.node_statuses}
        if self.is_leader():
            status_by_node.update(self.sync_status_by_node)

        known_nodes = [*state.control_planes, *state.runtimes]
        for node in known_nodes:
            if node.node_id in status_by_node:
                continue
            default = "synced" if node.node_id == state.leader_node_id and node.role == "control-plane" else "unknown"
            status_by_node[node.node_id] = GroupNodeSyncStatus(
                node_id=node.node_id,
                status=default,
                updated_at="",
            )

        statuses = sorted(status_by_node.values(), key=lambda item: item.node_id)
        return GroupState(
            group_id=state.group_id,
            version=state.version,
            leader_epoch=state.leader_epoch,
            leader_node_id=state.leader_node_id,
            leader_pubkey=state.leader_pubkey,
            control_planes=state.control_planes,
            runtimes=state.runtimes,
            endpoints=state.endpoints,
            node_statuses=statuses,
            expires_at=state.expires_at,
            leader_signature=state.leader_signature,
        )

    async def mark_broken(self, reason: str, leader_urls: list[str]) -> None:
        if self.broken_sync_reason:
            return
        self.broken_sync_reason = reason
        self.set_local_sync_status("broken", reason)
        logger.error("node marked broken node_id={} reason={}", self.identity.node_id, reason)
        for url in leader_urls:
            await self.sync_logic.publish_sync_status(url, "broken", reason)

    def is_leader(self) -> bool:
        state = self.state_manager.get_state()
        return state is not None and state.leader_node_id == self.identity.node_id

    def require_leader(self) -> GroupState:
        state = self.state_manager.require_state()
        if state.leader_node_id != self.identity.node_id:
            raise TransportError("node is not the active leader")
        return state

    def current_failover_candidate(self, state: GroupState) -> NodeRecord | None:
        ordered = sort_control_planes(state.control_planes)
        if not ordered:
            return None
        node_ids = [item.node_id for item in ordered]
        if state.leader_node_id not in node_ids:
            return ordered[0]

        leader_index = node_ids.index(state.leader_node_id)
        # Simple strict order: the next one in the sorted list after the current leader
        candidate_index = (leader_index + 1) % len(ordered)
        candidate = ordered[candidate_index]
        
        logger.trace(
            "failover candidate evaluated leader={} candidate={}",
            state.leader_node_id,
            candidate.node_id,
        )
        return candidate

    # Delegate methods
    async def sync_control_plane_events(self, preferred_leader_url: str | None = None) -> GroupState | None:
        return await self.sync_logic.sync_control_plane_events(preferred_leader_url)

    def append_cluster_event(self, event: ClusterAuditEventBase) -> None:
        self.state_logic.append_cluster_event(event)

    def ensure_admin_user(self, user_id: str, public_key: str) -> UserRecord:
        return self.state_logic.ensure_admin_user(user_id, public_key)

    async def check_failover(self, ttl_seconds: int) -> GroupState | None:
        return await self.state_logic.check_failover(ttl_seconds)

    def initialize_group(self, group_id: str, ttl_seconds: int) -> GroupState:
        return self.state_logic.initialize_group(group_id, ttl_seconds)

    def apply_join(self, join_request: JoinRequest, ttl_seconds: int) -> GroupState:
        return self.state_logic.apply_join(join_request, ttl_seconds)

    def revoke_node(self, node_id: str, ttl_seconds: int) -> GroupState:
        return self.state_logic.revoke_node(node_id, ttl_seconds)

    def update_node_endpoints(self, node_id: str, endpoints: list[str], ttl_seconds: int) -> GroupState:
        return self.state_logic.update_node_endpoints(node_id, endpoints, ttl_seconds)

    def issue_bootstrap_token(self, ttl_seconds: int) -> str:
        return self.tokens.issue_token(ttl_seconds).token

    def issue_gui_bootstrap_token(self, ttl_seconds: int) -> str:
        self.require_leader()
        return self.gui_tokens.issue_token(ttl_seconds).token

    async def join_peer(self, leader_url: str, leader_pubkey: str, bootstrap_token: str) -> GroupState:
        return await self.sync_logic.join_peer(leader_url, leader_pubkey, bootstrap_token)

    def build_gui_snapshot(self) -> GuiClusterSnapshot:
        return self.api_logic.build_gui_snapshot()

    def build_gui_event_page(self, limit: int, before_sequence: int | None = None) -> GuiEventPage:
        return self.api_logic.build_gui_event_page(limit, before_sequence)

    @property
    def endpoints(self) -> list[str]:
        return list(self.identity.endpoints)

    async def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> GroupState | JoinResponse | GuiClusterSnapshot | GuiEventPage | ControlPlaneEventPage | dict[str, str]:
        if self.broken_sync_reason:
            raise TransportError(f"node is broken: {self.broken_sync_reason}")

        base_path = path.partition("?")[0]
        logger.info("control_plane_request_dispatch method={} path={} auth_node_id={}", method, base_path, auth.node_id)
        
        result = await self.api_logic.handle_request(method, path, body, auth, public_key)
        if result is not None:
            return result

        return await super().handle_request(method, base_path, body, auth, public_key)
