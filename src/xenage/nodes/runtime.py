from __future__ import annotations

from pathlib import Path

from loguru import logger

from structures.resources.membership import GroupState, JoinRequest, JoinResponse, RequestAuth, StoredNodeIdentity

from ..serialization import decode_value
from ..network.http_transport import TransportError
from .base import BaseNode


class RuntimeNode(BaseNode):
    def __init__(self, node_id: str, storage_path: Path, log_level: str = "INFO") -> None:
        super().__init__(node_id, "runtime", storage_path, [], log_level)
        if self.identity.endpoints:
            logger.warning(
                "runtime identity contained endpoints; clearing for poll-only mode node_id={} endpoint_count={}",
                self.identity.node_id,
                len(self.identity.endpoints),
            )
            self.identity = StoredNodeIdentity(
                node_id=self.identity.node_id,
                role=self.identity.role,
                public_key=self.identity.public_key,
                private_key=self.identity.private_key,
                endpoints=[],
            )
            self.storage.save_identity(self.identity)
        logger.debug("runtime node ready node_id={} endpoint_count={}", self.identity.node_id, len(self.identity.endpoints))

    async def connect(self, leader_host: str, leader_pubkey: str, bootstrap_token: str) -> GroupState:
        logger.info("joining runtime node_id={} via leader={}", self.identity.node_id, leader_host)
        response = await self.client.post_json(
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
        trust_anchor: str | None = None
        if current_state is None:
            trust_anchor = leader_pubkey
        return self.state_manager.replace_state(response.group_state, trusted_leader_pubkey=trust_anchor)

    async def pull_group_state(self) -> GroupState | None:
        current = self.state_manager.get_state()
        if current is None:
            return None
        control_plane_ids = [item.node_id for item in current.control_planes]
        ordered_ids = [current.leader_node_id, *[node_id for node_id in control_plane_ids if node_id != current.leader_node_id]]
        urls: list[str] = []
        seen_urls: set[str] = set()
        for node_id in ordered_ids:
            for endpoint in current.endpoints:
                if endpoint.node_id != node_id:
                    continue
                if endpoint.url in seen_urls:
                    continue
                seen_urls.add(endpoint.url)
                urls.append(endpoint.url)
        for url in urls:
            try:
                payload = await self.client.get(url, "/v1/state/current")
                incoming = decode_value(payload, GroupState)
                latest = self.state_manager.get_state()
                if latest is not None and incoming.version <= latest.version:
                    return latest
                return self.state_manager.replace_state(incoming)
            except Exception as exc:
                logger.debug("runtime state pull failed url={} reason={}", url, exc)
                continue
        return current

    async def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> GroupState | JoinResponse | dict[str, str]:
        logger.trace("runtime route dispatch method={} path={} auth_node_id={}", method, path, auth.node_id)
        return await super().handle_request(method, path, body, auth, public_key)
