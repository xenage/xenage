from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Awaitable

from loguru import logger
from structures.resources.membership import RequestAuth
from ....network.http_transport import TransportError

if TYPE_CHECKING:
    from .urls_logic import ControlPlaneUrlsLogic

HandlerT = Callable[["ControlPlaneUrlsLogic", str, bytes, RequestAuth, str], Awaitable[object]]

@dataclass(frozen=True)
class Route:
    path: str
    method: str
    handler: HandlerT
    require_signature: bool = False
    is_prefix: bool = False

class Router:
    def __init__(self) -> None:
        self._routes_by_key: dict[tuple[str, str], Route] = {}
        self._prefix_routes: list[Route] = []

    def add_route(
        self,
        path: str,
        method: str,
        handler: HandlerT,
        require_signature: bool = False,
        is_prefix: bool = False,
    ) -> None:
        key = (method, path)
        if is_prefix:
            exists = any(
                item.method == method and item.path == path and item.is_prefix
                for item in self._prefix_routes
            )
            if exists:
                raise RuntimeError(f"prefix route already registered: {method} {path}")
            self._prefix_routes.append(
                Route(
                    path=path,
                    method=method,
                    handler=handler,
                    require_signature=require_signature,
                    is_prefix=True,
                ),
            )
            return

        if key in self._routes_by_key:
            raise RuntimeError(f"route already registered: {method} {path}")
        self._routes_by_key[key] = Route(
            path=path,
            method=method,
            handler=handler,
            require_signature=require_signature,
            is_prefix=False,
        )

    async def dispatch(
        self,
        logic: ControlPlaneUrlsLogic,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> object | None:
        base_path = path.partition("?")[0]

        route = self._routes_by_key.get((method, base_path))
        if route is None:
            matched_prefix: Route | None = None
            for candidate in self._prefix_routes:
                if candidate.method != method:
                    continue
                if not base_path.startswith(candidate.path):
                    continue
                if matched_prefix is None or len(candidate.path) > len(matched_prefix.path):
                    matched_prefix = candidate
            route = matched_prefix
        if route is None:
            logger.trace("router_miss method={} path={}", method, base_path)
            return None
        logger.debug(
            "router_match method={} path={} matched_path={} prefix={} require_signature={}",
            method,
            base_path,
            route.path,
            route.is_prefix,
            route.require_signature,
        )
        if route.require_signature and not public_key:
            raise TransportError(f"route {method} {base_path} requires a signed request")
        return await route.handler(logic, path, body, auth, public_key)

router = Router()

def url(path: str, method: str, handler: HandlerT) -> None:
    router.add_route(path, method, handler, require_signature=False, is_prefix=False)

def url_signed(path: str, method: str, handler: HandlerT) -> None:
    router.add_route(path, method, handler, require_signature=True, is_prefix=False)

def url_prefix(path_prefix: str, method: str, handler: HandlerT) -> None:
    router.add_route(path_prefix, method, handler, require_signature=False, is_prefix=True)

def url_prefix_signed(path_prefix: str, method: str, handler: HandlerT) -> None:
    router.add_route(path_prefix, method, handler, require_signature=True, is_prefix=True)

# Routes registration
from . import views

url_signed("/v1/join", "POST", views.handle_join)
url_signed("/v1/revoke", "POST", views.handle_revoke)
url_signed("/v1/endpoints", "POST", views.handle_endpoints)
url_signed("/v1/control-plane/sync-status", "POST", views.handle_sync_status)
url_signed("/v1/control-plane/events", "GET", views.handle_events)
url_signed("/v1/gui/cluster", "GET", views.handle_gui_cluster)
url_signed("/v1/gui/events", "GET", views.handle_gui_events)
url("/v1/gui/bootstrap-user", "POST", views.handle_gui_bootstrap_user)
url_signed("/v1/state/current", "GET", views.handle_state_current)
url_signed("/v1/resources/apply", "POST", views.handle_resources_apply)
url_signed("/v1/auth/can-i", "POST", views.handle_auth_can_i)
url_prefix_signed("/v1/resources/", "GET", views.handle_resources_list)
