from __future__ import annotations

import asyncio
from typing import TypeVar, TYPE_CHECKING

import aiohttp

from structures.resources.membership import (
    GuiClusterSnapshot, 
    GuiConnectionConfig, 
    GuiEventPage,
    GroupState,
)

from ..cluster.time_utils import utc_now
from ..crypto import Ed25519KeyPair, make_nonce
from ..serialization import decode_value
from .http_transport import SignedTransportClient, TransportError

if TYPE_CHECKING:
    pass

StructureT = TypeVar("StructureT")

class ControlPlaneClient:
    def __init__(self, config: GuiConnectionConfig, timeout_seconds: float = 4.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.key_pair = Ed25519KeyPair.from_private_key_b64(config.private_key)

    @classmethod
    def from_yaml(cls, path: str) -> "ControlPlaneClient":
        raw = open(path, encoding="utf-8").read()
        fields: dict[str, str] = {}
        control_plane_urls: list[str] = []
        in_control_plane_urls = False
        for line in raw.splitlines():
            normalized_line = line.rstrip("\n")
            compact = normalized_line.lstrip(" ")
            if " " in compact:
                first_token, rest = compact.split(" ", 1)
                looks_like_rfc3339 = (
                    len(first_token) >= 20
                    and "T" in first_token
                    and first_token.endswith("Z")
                    and all(ch.isdigit() or ch in "-:.TZ" for ch in first_token)
                )
                if looks_like_rfc3339:
                    normalized_line = rest
            leading = len(normalized_line) - len(normalized_line.lstrip(" "))
            stripped = normalized_line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                if in_control_plane_urls and stripped and not stripped.startswith("-"):
                    in_control_plane_urls = False
                elif in_control_plane_urls and stripped.startswith("-"):
                    control_plane_urls.append(stripped[1:].strip().strip('"').strip("'"))
                continue
            if stripped == "controlPlaneUrls:" or stripped == "control_plane_urls:":
                in_control_plane_urls = True
                continue
            if in_control_plane_urls and stripped.startswith("-"):
                control_plane_urls.append(stripped[1:].strip().strip('"').strip("'"))
                continue
            if in_control_plane_urls and leading <= 2:
                in_control_plane_urls = False
            key, value = stripped.split(":", 1)
            fields[key.strip()] = value.strip().strip('"').strip("'")
        cluster_name = fields.get("clusterName", fields.get("cluster_name", "demo"))
        if not control_plane_urls:
            single = fields.get("controlPlaneUrl", fields.get("control_plane_url", ""))
            if single:
                control_plane_urls = [single]
        user_id = fields.get("id", fields.get("user_id", "admin"))
        public_key = fields.get("publicKey", fields.get("public_key", ""))
        private_key = fields.get("privateKey", fields.get("private_key", ""))
        role = fields.get("role", "admin")
        if not control_plane_urls or not public_key or not private_key:
            raise TransportError("invalid cluster connection yaml: missing required keys")
        
        config = GuiConnectionConfig(
            cluster_name=cluster_name,
            control_plane_urls=control_plane_urls,
            user_id=user_id,
            public_key=public_key,
            private_key=private_key,
            role=role,
        )
        return cls(config)

    def fetch_cluster_snapshot(self) -> GuiClusterSnapshot:
        return asyncio.run(self.get_cluster_snapshot())

    def fetch_cluster_events(self, limit: int = 10, before_sequence: int | None = None) -> GuiEventPage:
        return asyncio.run(self.get_events(limit=limit, before_sequence=before_sequence))

    async def _signed_request(
        self, 
        method: str, 
        path: str, 
        response_type: type[StructureT],
        body: bytes = b"",
    ) -> StructureT:
        timestamp = int(utc_now().timestamp())
        nonce = make_nonce()
        payload = SignedTransportClient.signature_payload(method, path, timestamp, nonce, body)
        signature = self.key_pair.sign(payload)
        headers = {
            "x-node-id": self.config.user_id,
            "x-timestamp": str(timestamp),
            "x-nonce": nonce,
            "x-signature": signature,
            "x-public-key": self.config.public_key,
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        last_error: Exception | None = None
        for base_url in self.config.control_plane_urls:
            url = f"{base_url.rstrip('/')}{path}"
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(method, url, headers=headers, data=body) as response:
                        response_body = await response.read()
                        if response.status == 200:
                            return decode_value(response_body, response_type)
                        raise TransportError(SignedTransportClient._extract_error(response_body, response.reason))
            except Exception as exc:
                last_error = exc
                continue

        raise TransportError(str(last_error) if last_error else "no control-plane urls configured")

    async def get_cluster_snapshot(self) -> GuiClusterSnapshot:
        return await self._signed_request("GET", "/v1/gui/cluster", GuiClusterSnapshot)

    async def get_events(self, limit: int = 10, before_sequence: int | None = None) -> GuiEventPage:
        query = f"?limit={max(1, min(limit, 200))}"
        if before_sequence is not None:
            query = f"{query}&before_sequence={before_sequence}"
        return await self._signed_request("GET", f"/v1/gui/events{query}", GuiEventPage)

    async def get_current_state(self) -> GroupState:
        return await self._signed_request("GET", "/v1/state/current", GroupState)
