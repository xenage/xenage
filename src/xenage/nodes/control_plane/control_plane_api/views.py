from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from loguru import logger
from structures.resources.membership import (
    GroupState,
    RequestAuth,
    JoinRequest,
    JoinResponse,
    RevokeNodeRequest,
    EndpointUpdateRequest,
    GuiUserBootstrapRequest,
    ControlPlaneSyncStatusRequest,
)
from structures.resources.events.cluster import GuiClusterSnapshotReadEvent
from ....cluster.time_utils import utc_now
from ....network.http_transport import TransportError
from ....serialization import decode_value
from ....tokens import TokenValidationError

if TYPE_CHECKING:
    from .urls_logic import ControlPlaneUrlsLogic


def _optional_int(raw_value: str) -> int | None:
    if raw_value == "":
        return None
    try:
        return int(raw_value)
    except ValueError as exc:
        raise TransportError("query parameter must be an integer") from exc


def _parse_query_int(
    query: dict[str, list[str]],
    key: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw_value = query.get(key, [str(default)])[0]
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise TransportError(f"query parameter '{key}' must be an integer") from exc
    if minimum is not None and value < minimum:
        raise TransportError(f"query parameter '{key}' must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise TransportError(f"query parameter '{key}' must be <= {maximum}")
    return value


def _require_control_plane_requester(logic: ControlPlaneUrlsLogic, auth: RequestAuth, public_key: str) -> GroupState:
    logic.node.verify_known_signer(auth, public_key)
    logic.node.require_leader()
    state = logic.node.state_manager.require_state()
    if auth.node_id not in {item.node_id for item in state.control_planes}:
        raise TransportError("requester is not a control-plane node")
    return state


async def handle_join(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_join requester={} body_bytes={}", auth.node_id, len(body))
    join_request = decode_value(body, JoinRequest)
    if join_request.node.node_id != auth.node_id:
        raise TransportError("join request node_id does not match signed node_id")
    if join_request.node.public_key != public_key:
        raise TransportError("join request public key does not match signer public key")
    try:
        group_state = logic.node.state_logic.apply_join(join_request, ttl_seconds=logic.node.state_ttl_seconds)
        return JoinResponse(accepted=True, group_state=group_state)
    except TokenValidationError as exc:
        return JoinResponse(accepted=False, reason=str(exc))

async def handle_revoke(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_revoke requester={} body_bytes={}", auth.node_id, len(body))
    _require_control_plane_requester(logic, auth, public_key)
    revoke_request = decode_value(body, RevokeNodeRequest)
    return logic.node.state_logic.revoke_node(revoke_request.node_id, ttl_seconds=logic.node.state_ttl_seconds)

async def handle_endpoints(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_endpoints requester={} body_bytes={}", auth.node_id, len(body))
    _require_control_plane_requester(logic, auth, public_key)
    update_request = decode_value(body, EndpointUpdateRequest)
    return logic.node.state_logic.update_node_endpoints(update_request.node_id, update_request.endpoints, ttl_seconds=logic.node.state_ttl_seconds)

async def handle_sync_status(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_sync_status requester={} body_bytes={}", auth.node_id, len(body))
    _require_control_plane_requester(logic, auth, public_key)
    update = decode_value(body, ControlPlaneSyncStatusRequest)
    status = logic.node.upsert_sync_status(auth.node_id, update.status, update.reason)
    return {
        "status": "ok",
        "node_id": status.node_id,
        "sync_status": status.status,
    }

async def handle_events(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_events requester={} path={}", auth.node_id, path)
    _require_control_plane_requester(logic, auth, public_key)
    _, _, raw_query = path.partition("?")
    query = urllib.parse.parse_qs(raw_query) if raw_query else {}
    after_event_id = _parse_query_int(query, "after_event_id", 0, minimum=0)
    limit = _parse_query_int(query, "limit", 100, minimum=1, maximum=500)
    return logic.node.event_manager.event_page(logic.node.identity.node_id, after_event_id, limit)


async def handle_gui_cluster(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_gui_cluster requester={}", auth.node_id)
    logic.node.require_leader()
    logic.verify_admin_user(auth, public_key)
    logic.node.append_cluster_event(GuiClusterSnapshotReadEvent(user_id=auth.node_id))
    return await logic.build_gui_snapshot()

async def handle_gui_events(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.debug("api_handle_gui_events requester={} path={}", auth.node_id, path)
    logic.node.require_leader()
    logic.verify_admin_user(auth, public_key)
    _, _, raw_query = path.partition("?")
    query = urllib.parse.parse_qs(raw_query) if raw_query else {}
    limit = _parse_query_int(query, "limit", 10, minimum=1, maximum=200)
    before_raw = query.get("before_sequence", [""])[0]
    before_sequence = _optional_int(before_raw)
    if before_sequence is not None and before_sequence <= 0:
        raise TransportError("query parameter 'before_sequence' must be >= 1")
    return logic.build_gui_event_page(limit=limit, before_sequence=before_sequence)


async def handle_gui_bootstrap_user(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.info("api_handle_gui_bootstrap_user requester={} body_bytes={}", auth.node_id, len(body))
    logic.node.require_leader()
    request = decode_value(body, GuiUserBootstrapRequest)
    if not request.bootstrap_token:
        raise TransportError("bootstrap token is required")
    if not request.user_id:
        raise TransportError("user_id is required")
    if not request.public_key:
        raise TransportError("public_key is required")
    logic.node.state_logic.ensure_admin_user_with_bootstrap_token(
        request.bootstrap_token,
        request.user_id,
        request.public_key,
    )
    return logic.build_bootstrap_user_response(
        request.user_id,
        request.public_key,
        request.control_plane_urls,
    )

async def handle_state_current(logic: ControlPlaneUrlsLogic, path: str, body: bytes, auth: RequestAuth, public_key: str) -> object:
    logger.trace("api_handle_state_current requester={} path={}", auth.node_id, path)
    logic.node.verify_known_signer(auth, public_key)
    state = logic.node.state_manager.require_state()
    known_node_ids = {item.node_id for item in [*state.control_planes, *state.runtimes]}
    if auth.node_id not in known_node_ids:
        allowed = logic.node.rbac_state_manager.can_i(auth.node_id, public_key, "get", "state", "cluster")
        if not allowed:
            raise TransportError("requester is not a cluster node")
    runtime_ids = {item.node_id for item in state.runtimes}
    if auth.node_id in runtime_ids:
        logic.node.last_poll_success_by_node[auth.node_id] = utc_now().isoformat().replace("+00:00", "Z")
    return logic.node.state_with_sync_statuses(state)


async def handle_resources_apply(
    logic: ControlPlaneUrlsLogic,
    path: str,
    body: bytes,
    auth: RequestAuth,
    public_key: str,
) -> object:
    logger.info("api_handle_resources_apply requester={} body_bytes={}", auth.node_id, len(body))
    return logic.handle_resources_apply(body, auth, public_key)


async def handle_auth_can_i(
    logic: ControlPlaneUrlsLogic,
    path: str,
    body: bytes,
    auth: RequestAuth,
    public_key: str,
) -> object:
    logger.debug("api_handle_auth_can_i requester={} body_bytes={}", auth.node_id, len(body))
    return logic.handle_auth_can_i(body, auth, public_key)


async def handle_resources_list(
    logic: ControlPlaneUrlsLogic,
    path: str,
    body: bytes,
    auth: RequestAuth,
    public_key: str,
) -> object:
    logger.debug("api_handle_resources_list requester={} path={}", auth.node_id, path)
    return logic.handle_resources_list(path, auth, public_key)
