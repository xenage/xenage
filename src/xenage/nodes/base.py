from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from structures.resources.membership import GroupEndpoint, GroupState, JoinResponse, NodeRecord, PublishStateRequest, RequestAuth, StoredNodeIdentity, UserState, UserStatePublishRequest

from ..crypto import Ed25519KeyPair
from ..serialization import decode_value
from ..cluster.state_manager import StateManager, StateValidationError
from ..cluster.user_state_manager import UserStateManager
from ..network.http_transport import HTTPNodeProtocol, SignedTransportClient, TransportError
from ..persistence.storage_layer import StorageLayer


class BaseNode(HTTPNodeProtocol):
    def __init__(self, node_id: str, role: str, storage_path: Path, endpoints: list[str], log_level: str = "INFO") -> None:
        logger.debug(
            "initializing base node node_id={} role={} storage_path={} endpoint_count={} log_level={}",
            node_id,
            role,
            storage_path,
            len(endpoints),
            log_level,
        )
        self.node_id = node_id
        self.role = role
        self.storage = StorageLayer(storage_path)
        self.state_manager = StateManager(self.storage)
        self.user_state_manager = UserStateManager(self.storage)
        existing_identity = self.storage.load_identity()
        if existing_identity is None:
            key_pair = Ed25519KeyPair.generate()
            identity = StoredNodeIdentity(
                node_id=node_id,
                role=role,
                public_key=key_pair.public_key_b64(),
                private_key=key_pair.private_key_b64(),
                endpoints=endpoints,
            )
            self.storage.save_identity(identity)
            self.identity = identity
            self.key_pair = key_pair
            logger.info("generated node identity node_id={} role={}", node_id, role)
        else:
            self.identity = existing_identity
            self.key_pair = Ed25519KeyPair.from_private_key_b64(existing_identity.private_key)
            logger.info("loaded node identity node_id={} role={}", node_id, role)
        logger.trace("node endpoints node_id={} endpoints={}", self.identity.node_id, self.identity.endpoints)
        self.client = SignedTransportClient(self.identity.node_id, self.identity.public_key, self.key_pair)

    def node_record(self) -> NodeRecord:
        return NodeRecord(
            node_id=self.identity.node_id,
            role=self.identity.role,
            public_key=self.identity.public_key,
            endpoints=list(self.identity.endpoints),
        )

    def publish_state_to_members(
        self,
        group_state: GroupState,
        target_roles: set[Literal["control-plane", "runtime"]] | None = None,
    ) -> dict[str, bool]:
        roles = target_roles or {"control-plane", "runtime"}
        node_roles: dict[str, Literal["control-plane", "runtime"]] = {
            item.node_id: item.role for item in [*group_state.control_planes, *group_state.runtimes]
        }
        endpoint_map: dict[str, list[str]] = {}
        for endpoint in group_state.endpoints:
            if endpoint.node_id == self.identity.node_id:
                continue
            node_role = node_roles.get(endpoint.node_id)
            if node_role is None or node_role not in roles:
                continue
            endpoint_map.setdefault(endpoint.node_id, []).append(endpoint.url)

        results: dict[str, bool] = {}
        logger.debug(
            "publishing state to members version={} epoch={} target_nodes={}",
            group_state.version,
            group_state.leader_epoch,
            len(endpoint_map),
        )
        for node_id, urls in endpoint_map.items():
            delivered = False
            for url in urls:
                try:
                    response = self.client.post_json(
                        url,
                        "/v1/state/publish",
                        PublishStateRequest(group_state=group_state),
                        GroupState,
                    )
                    logger.info("published group state version={} to {} ({})", response.version, node_id, url)
                    delivered = True
                    break
                except TransportError as exc:
                    logger.error("failed to publish state to {} ({}): {}", node_id, url, exc)
            results[node_id] = delivered
        logger.trace("state publish result version={} delivered={}", group_state.version, results)
        return results

    def verify_known_signer(self, auth: RequestAuth, public_key: str) -> None:
        state = self.state_manager.get_state()
        if state is None:
            logger.trace("known signer check skipped because state is not initialized")
            return
        known_nodes = {item.node_id: item.public_key for item in state.control_planes}
        known_nodes.update({item.node_id: item.public_key for item in state.runtimes})
        expected = known_nodes.get(auth.node_id)
        if expected is not None and expected != public_key:
            raise TransportError("request signer public key does not match group state")
        logger.trace("known signer verified node_id={} expected_key_present={}", auth.node_id, expected is not None)

    def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> GroupState | JoinResponse | UserState | dict[str, str]:
        logger.debug("handling node request method={} path={} node_id={}", method, path, self.identity.node_id)
        if public_key:
            self.verify_known_signer(auth, public_key)
        if method == "GET" and path == "/v1/heartbeat":
            return {"status": "ok", "node_id": self.identity.node_id}
        if method == "POST" and path == "/v1/state/publish":
            request = decode_value(body, PublishStateRequest)
            try:
                group_state = self.state_manager.replace_state(request.group_state)
            except StateValidationError as exc:
                raise TransportError(str(exc)) from exc
            logger.info("accepted published group state version={}", group_state.version)
            return group_state
        if method == "POST" and path == "/v1/users/publish":
            request = decode_value(body, UserStatePublishRequest)
            user_state = self.user_state_manager.replace_state(request.user_state)
            logger.info("accepted published user state version={}", user_state.version)
            return user_state
        raise TransportError(f"unsupported route {method} {path}")
