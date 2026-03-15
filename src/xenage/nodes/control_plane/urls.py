from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Awaitable

from structures.resources.membership import RequestAuth
from ...network.http_transport import TransportError

if TYPE_CHECKING:
    from .urls_logic import ControlPlaneUrlsLogic

HandlerT = Callable[["ControlPlaneUrlsLogic", str, bytes, RequestAuth, str], Awaitable[object]]

@dataclass(frozen=True)
class Route:
    path: str
    method: str
    handler: HandlerT
    require_signature: bool = False

class Router:
    def __init__(self) -> None:
        self._routes_by_key: dict[tuple[str, str], Route] = {}

    def add_route(self, path: str, method: str, handler: HandlerT, require_signature: bool = False) -> None:
        key = (method, path)
        if key in self._routes_by_key:
            raise RuntimeError(f"route already registered: {method} {path}")
        self._routes_by_key[key] = Route(path=path, method=method, handler=handler, require_signature=require_signature)

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
            return None
        if route.require_signature and not public_key:
            raise TransportError(f"route {method} {base_path} requires a signed request")
        return await route.handler(logic, path, body, auth, public_key)

router = Router()

def url(path: str, method: str, handler: HandlerT) -> None:
    router.add_route(path, method, handler, require_signature=False)

def url_signed(path: str, method: str, handler: HandlerT) -> None:
    router.add_route(path, method, handler, require_signature=True)

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
