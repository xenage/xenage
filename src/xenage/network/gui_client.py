from __future__ import annotations

import urllib.error
import urllib.request

from structures.resources.membership import GuiClusterSnapshot, GuiConnectionConfig

from ..crypto import Ed25519KeyPair, make_nonce
from ..serialization import decode_value
from ..cluster.time_utils import utc_now
from .http_transport import SignedTransportClient, TransportError


class GuiSignedClient:
    def __init__(self, config: GuiConnectionConfig, timeout_seconds: float = 4.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.key_pair = Ed25519KeyPair.from_private_key_b64(config.private_key)

    @classmethod
    def from_yaml(cls, path: str) -> "GuiSignedClient":
        raw = open(path, encoding="utf-8").read()
        fields: dict[str, str] = {}
        control_plane_urls: list[str] = []
        in_control_plane_urls = False
        for line in raw.splitlines():
            leading = len(line) - len(line.lstrip(" "))
            stripped = line.strip()
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
        return cls(
            GuiConnectionConfig(
                cluster_name=cluster_name,
                control_plane_urls=control_plane_urls,
                user_id=user_id,
                public_key=public_key,
                private_key=private_key,
                role=role,
            ),
        )

    def fetch_cluster_snapshot(self) -> GuiClusterSnapshot:
        path = "/v1/gui/cluster"
        timestamp = int(utc_now().timestamp())
        nonce = make_nonce()
        payload = SignedTransportClient.signature_payload("GET", path, timestamp, nonce, b"")
        signature = self.key_pair.sign(payload)
        last_error: Exception | None = None
        for base_url in self.config.control_plane_urls:
            request = urllib.request.Request(
                f"{base_url.rstrip('/')}{path}",
                method="GET",
                headers={
                    "x-node-id": self.config.user_id,
                    "x-timestamp": str(timestamp),
                    "x-nonce": nonce,
                    "x-signature": signature,
                    "x-public-key": self.config.public_key,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read()
                    return decode_value(body, GuiClusterSnapshot)
            except urllib.error.URLError as exc:
                last_error = exc
                continue
        raise TransportError(str(last_error) if last_error else "no control-plane urls configured")
