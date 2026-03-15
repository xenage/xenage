from __future__ import annotations

from pathlib import Path

from loguru import logger

from structures.resources.membership import NodeRecord, RequestAuth, StoredNodeIdentity

from ..crypto import Ed25519KeyPair
from ..cluster.state_manager import StateManager
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
            if existing_identity.node_id != node_id:
                raise RuntimeError(
                    f"stored node identity mismatch: expected node_id={node_id}, got node_id={existing_identity.node_id}"
                )
            if existing_identity.role != role:
                raise RuntimeError(
                    f"stored node role mismatch: expected role={role}, got role={existing_identity.role}"
                )
            self.identity = existing_identity
            self.key_pair = Ed25519KeyPair.from_private_key_b64(existing_identity.private_key)
            logger.info("loaded node identity node_id={} role={}", self.identity.node_id, self.identity.role)
        logger.trace("node endpoints node_id={} endpoints={}", self.identity.node_id, self.identity.endpoints)
        self.client = SignedTransportClient(self.identity.node_id, self.identity.public_key, self.key_pair)

    def node_record(self) -> NodeRecord:
        return NodeRecord(
            node_id=self.identity.node_id,
            role=self.identity.role,
            public_key=self.identity.public_key,
            endpoints=list(self.identity.endpoints),
        )

    def verify_known_signer(self, auth: RequestAuth, public_key: str) -> None:
        state = self.state_manager.get_state()
        if state is None:
            logger.trace("known signer check skipped because state is not initialized")
            return
        known_nodes = {item.node_id: item.public_key for item in state.control_planes}
        known_nodes.update({item.node_id: item.public_key for item in state.runtimes})
        expected = known_nodes.get(auth.node_id)
        if expected is not None:
            if expected != public_key:
                logger.warning("request_signer_key_mismatch node_id={} expected_key={} actual_key={}", 
                               auth.node_id, expected, public_key)
                raise TransportError("request signer public key does not match group state")
            logger.info("request_signer_verified node_id={} public_key={} role=known_node", auth.node_id, public_key)
        else:
            logger.debug("request_signer_not_in_group node_id={} public_key={}", auth.node_id, public_key)

    async def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> dict[str, str]:
        logger.debug("handling node request method={} path={} node_id={}", method, path, self.identity.node_id)
        if public_key:
            self.verify_known_signer(auth, public_key)
        if method == "GET" and path == "/v1/heartbeat":
            return {"status": "ok", "node_id": self.identity.node_id}
        raise TransportError(f"unsupported route {method} {path}")
