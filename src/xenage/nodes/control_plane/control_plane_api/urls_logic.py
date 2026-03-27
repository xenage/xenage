from __future__ import annotations

import asyncio
import urllib.parse
from typing import TYPE_CHECKING

import aiohttp
import msgspec
from loguru import logger

from structures.resources.membership import (
    ClusterNodeTableRow,
    EventLogEntry,
    GroupConfigKeyTableRow,
    GroupNodeSyncStatus,
    GroupState,
    GuiClusterSnapshot,
    UserRecord,
    UserRoleBinding,
    GuiUserBootstrapResponse,
    GuiEventPage,
    NodeRecord,
    RequestAuth,
)

from ....cluster.time_utils import parse_timestamp, utc_now
from .urls import router
from ....network.http_transport import TransportError

if TYPE_CHECKING:
    from ..main import ControlPlaneNode


class ControlPlaneUrlsLogic:
    def __init__(self, node: ControlPlaneNode) -> None:
        self.node = node

    async def probe_node_health(self, node: NodeRecord) -> tuple[str, str]:
        urls = list(node.endpoints)
        last_poll_at = self.node.last_poll_success_by_node.get(node.node_id, "")
        timeout = aiohttp.ClientTimeout(total=0.8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in urls:
                try:
                    async with session.get(f"{url.rstrip('/')}/v1/heartbeat"):
                        now = utc_now()
                        last_poll_at = now.isoformat().replace("+00:00", "Z")
                        self.node.last_poll_success_by_node[node.node_id] = last_poll_at
                        return "ready", last_poll_at
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    continue
        return "unavailable", last_poll_at

    def runtime_poll_health(self, node: NodeRecord) -> tuple[str, str]:
        last_poll_at = self.node.last_poll_success_by_node.get(node.node_id, "")
        if not last_poll_at:
            return "unavailable", ""
        try:
            age_seconds = max(0.0, (utc_now() - parse_timestamp(last_poll_at)).total_seconds())
        except Exception:
            return "unavailable", last_poll_at
        threshold_seconds = max(5, self.node.state_ttl_seconds * 2)
        if age_seconds <= threshold_seconds:
            return "ready", last_poll_at
        return "unavailable", last_poll_at

    @staticmethod
    def node_creation_timestamps_from_events(state: GroupState, event_log: list[EventLogEntry]) -> dict[str, str]:
        created_at_by_node: dict[str, str] = {}
        for entry in event_log:
            if entry.action == "cluster.bootstrap":
                node_id = entry.details.get("leader_node_id", "")
            elif entry.action == "cluster.node.joined":
                node_id = entry.details.get("node_id", "")
            else:
                continue
            if node_id and node_id not in created_at_by_node:
                created_at_by_node[node_id] = entry.happened_at
        for node in [*state.control_planes, *state.runtimes]:
            created_at_by_node.setdefault(node.node_id, "")
        return created_at_by_node

    async def build_gui_snapshot(self) -> GuiClusterSnapshot:
        base_state = self.node.state_manager.require_state()
        state = self.node.state_with_sync_statuses(base_state)
        audit_log = self.node.event_manager.cluster_audit_events()
        created_at_by_node = self.node_creation_timestamps_from_events(state, audit_log)
        sync_status_map = {item.node_id: item for item in state.node_statuses}
        control_plane_ids = {item.node_id for item in state.control_planes}
        rows: list[ClusterNodeTableRow] = []
        status_rows: list[GroupConfigKeyTableRow] = []

        for node in [*state.control_planes, *state.runtimes]:
            created_at = created_at_by_node.get(node.node_id, "")
            endpoint_hostname = "-"
            if node.endpoints:
                try:
                    endpoint_hostname = urllib.parse.urlparse(node.endpoints[0]).hostname or node.node_id
                except ValueError:
                    endpoint_hostname = node.node_id

            if node.role == "runtime":
                health_status, last_poll_at = self.runtime_poll_health(node)
            else:
                health_status, last_poll_at = await self.probe_node_health(node)
            sync_state = sync_status_map.get(node.node_id)
            if sync_state is None:
                sync_state = GroupNodeSyncStatus(node_id=node.node_id)
            sync_status = sync_state.status
            sync_reason = sync_state.reason

            if node.role == "control-plane":
                if sync_status == "broken":
                    status = "broken"
                elif sync_status == "syncing":
                    status = "syncing"
                elif node.node_id == state.leader_node_id:
                    status = "leader" if health_status != "unavailable" else "unavailable"
                elif health_status == "unavailable":
                    status = "unavailable"
                elif sync_status == "synced":
                    status = "synced"
                else:
                    status = "unknown"
            else:
                status = health_status

            status_rows.extend(
                [
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.status", value=status),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.sync_status", value=sync_status),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.sync_reason", value=sync_reason or "-"),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.name", value=endpoint_hostname),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.last_poll_at", value=last_poll_at or "-"),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.age", value=created_at or "-"),
                    GroupConfigKeyTableRow(key=f"node.{node.node_id}.version", value="unknown"),
                ],
            )
            rows.append(
                ClusterNodeTableRow(
                    node_id=node.node_id,
                    role=node.role,
                    leader=node.node_id == state.leader_node_id and node.node_id in control_plane_ids,
                    public_key=node.public_key,
                    endpoints=node.endpoints,
                    status=status,
                    name=endpoint_hostname,
                    version="unknown",
                    age=created_at or "",
                    last_poll_at=last_poll_at or "",
                ),
            )

        local_sync = sync_status_map.get(self.node.identity.node_id, GroupNodeSyncStatus(node_id=self.node.identity.node_id))
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
            GroupConfigKeyTableRow(key="control_plane_event_id", value=str(self.node.event_manager.get_last_event_id())),
            GroupConfigKeyTableRow(key="control_plane_sync_status", value=local_sync.status),
            GroupConfigKeyTableRow(key="control_plane_sync_reason", value=local_sync.reason or "-"),
        ]
        config_rows.extend(status_rows)
        return GuiClusterSnapshot(
            group_id=state.group_id,
            state_version=state.version,
            leader_epoch=state.leader_epoch,
            nodes=sorted(rows, key=lambda item: (item.role, item.node_id)),
            group_config=config_rows,
            users=self._users_from_rbac(),
        )

    def build_gui_event_page(self, limit: int, before_sequence: int | None = None) -> GuiEventPage:
        safe_limit = max(1, min(limit, 200))
        entries = self.node.event_manager.cluster_audit_events()
        if before_sequence is None:
            end_index = len(entries)
        else:
            left = 0
            right = len(entries)
            while left < right:
                middle = (left + right) // 2
                if entries[middle].sequence < before_sequence:
                    left = middle + 1
                else:
                    right = middle
            end_index = left
        start_index = max(0, end_index - safe_limit)
        items = list(reversed(entries[start_index:end_index]))
        has_more = start_index > 0
        next_before_sequence = items[-1].sequence if items else 0
        return GuiEventPage(
            items=items,
            has_more=has_more,
            next_before_sequence=next_before_sequence,
        )

    def _users_from_rbac(self) -> list[UserRecord]:
        state = self.node.rbac_state_manager.get_state()
        users: list[UserRecord] = []
        index = 0
        while index < len(state.serviceAccounts):
            account = state.serviceAccounts[index]
            users.append(
                UserRecord(
                    user_id=account.metadata.name,
                    public_key=account.spec.publicKey,
                    roles=[UserRoleBinding(role="admin")],
                    enabled=account.spec.enabled,
                    created_at="",
                ),
            )
            index += 1
        return users

    def build_bootstrap_user_response(
        self,
        user_id: str,
        public_key: str,
        control_plane_urls: list[str] | str | None = None,
    ) -> GuiUserBootstrapResponse:
        state = self.node.state_manager.require_state()
        derived_urls: list[str] = []
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
        return GuiUserBootstrapResponse(
            cluster_name=state.group_id,
            control_plane_urls=urls,
            user_id=user_id,
            role="admin",
            public_key=public_key,
        )

    def verify_admin_user(self, auth: RequestAuth, public_key: str) -> None:
        service_account = self.node.rbac_state_manager.find_service_account(auth.node_id)
        if service_account is None:
            raise TransportError("unknown user id")

        if not service_account.spec.enabled:
            raise TransportError("user is disabled")
        if service_account.spec.publicKey != public_key:
            raise TransportError("request signer public key does not match stored user key")
        allowed = self.node.rbac_state_manager.can_i(auth.node_id, public_key, "get", "nodes", "cluster")
        if not allowed:
            raise TransportError("user is not authorized")

    def _resource_kind_to_name(self, kind: str) -> str:
        if kind == "ServiceAccount":
            return "serviceaccounts"
        if kind == "Role":
            return "roles"
        if kind == "RoleBinding":
            return "rolebindings"
        raise TransportError("unsupported resource kind")

    def _namespace_from_manifest(self, manifest: dict[str, object]) -> str:
        _ = manifest
        return "cluster"

    def _authorize_apply(self, auth: RequestAuth, public_key: str, manifest: dict[str, object]) -> None:
        resource = self._resource_kind_to_name(str(manifest.get("kind", "")))
        namespace = self._namespace_from_manifest(manifest)
        allowed = self.node.rbac_state_manager.can_i(auth.node_id, public_key, "apply", resource, namespace)
        logger.debug(
            "rbac_authorize_apply requester={} resource={} namespace={} allowed={}",
            auth.node_id,
            resource,
            namespace,
            allowed,
        )
        if not allowed:
            raise TransportError("user is not authorized")

    def handle_resources_apply(self, body: bytes, auth: RequestAuth, public_key: str) -> dict[str, object]:
        manifest = msgspec.json.decode(body, type=dict[str, object])
        logger.trace(
            "resources_apply_decoded requester={} kind={} api_version={}",
            auth.node_id,
            manifest.get("kind", ""),
            manifest.get("apiVersion", ""),
        )
        self._authorize_apply(auth, public_key, manifest)
        result = self.node.rbac_state_manager.apply_manifest(manifest)
        self.node.event_manager.record_rbac_state(self.node.identity.node_id, self.node.rbac_state_manager.get_state())
        logger.info(
            "resources_apply_success requester={} kind={} namespace={} name={}",
            auth.node_id,
            result.get("kind", ""),
            result.get("namespace", ""),
            result.get("name", ""),
        )
        return result

    def handle_auth_can_i(self, body: bytes, auth: RequestAuth, public_key: str) -> dict[str, object]:
        request = msgspec.json.decode(body, type=dict[str, object])
        verb = str(request.get("verb", ""))
        resource = str(request.get("resource", ""))
        namespace = str(request.get("namespace", "default"))
        allowed = self.node.rbac_state_manager.can_i(auth.node_id, public_key, verb, resource, namespace)
        logger.debug(
            "auth_can_i requester={} verb={} resource={} namespace={} allowed={}",
            auth.node_id,
            verb,
            resource,
            namespace,
            allowed,
        )
        return {"allowed": allowed, "verb": verb, "resource": resource, "namespace": namespace}

    def handle_resources_list(self, path: str, auth: RequestAuth, public_key: str) -> dict[str, object]:
        base_path = path.partition("?")[0]
        resource = base_path.removeprefix("/v1/resources/")
        namespace = "cluster"
        allowed = self.node.rbac_state_manager.can_i(auth.node_id, public_key, "list", resource, namespace)
        logger.debug(
            "resources_list_authorize requester={} resource={} namespace={} allowed={}",
            auth.node_id,
            resource,
            namespace,
            allowed,
        )
        if not allowed:
            raise TransportError("user is not authorized")
        items = self.node.rbac_state_manager.list_resources(resource, namespace)
        logger.trace(
            "resources_list_success requester={} resource={} namespace={} item_count={}",
            auth.node_id,
            resource,
            namespace,
            len(items),
        )
        return {"items": items}

    async def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> object | None:
        return await router.dispatch(self, method, path, body, auth, public_key)
