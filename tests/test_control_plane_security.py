from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from structures.resources.events import GuiClusterSnapshotReadEvent
from structures.resources.membership import (
    EndpointUpdateRequest,
    JoinRequest,
    JoinResponse,
    NodeRecord,
    RequestAuth,
    RevokeNodeRequest,
    UserRecord,
    UserRoleBinding,
    UserState,
)
from xenage.crypto import Ed25519KeyPair
from xenage.network.http_transport import RequestVerifier, SignedTransportClient, TransportError
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.serialization import decode_value, encode_value


class MockAuth:
    def __init__(self, node_id: str, key_pair: Ed25519KeyPair):
        self.node_id = node_id
        self.key_pair = key_pair
        self.client = SignedTransportClient(node_id, key_pair.public_key_b64(), key_pair)

    def build_auth(self, method: str, path: str, body: bytes, timestamp: int | None = None, nonce: str | None = None) -> RequestAuth:
        ts = timestamp if timestamp is not None else int(time.time())
        n = nonce if nonce is not None else "nonce-123"
        payload = SignedTransportClient.signature_payload(method, path, ts, n, body)
        sig = self.key_pair.sign(payload)
        return RequestAuth(
            node_id=self.node_id,
            timestamp=ts,
            nonce=n,
            signature=sig,
        )


@pytest.fixture
def cp_node(tmp_path: Path) -> ControlPlaneNode:
    node = ControlPlaneNode("cp-1", tmp_path / "cp-1", ["http://localhost:8734"])
    node.initialize_group("test-group", 60)
    return node


@pytest.mark.asyncio
async def test_invalid_signature(cp_node: ControlPlaneNode):
    # Test for invalid signature
    auth = MockAuth("any-node", Ed25519KeyPair.generate())
    req_auth = auth.build_auth("GET", "/v1/heartbeat", b"")
    
    # Corrupt the signature - use a valid base64 but incorrect signature
    fake_sig = Ed25519KeyPair.generate().sign(b"garbage")
    req_auth = RequestAuth(
        node_id=req_auth.node_id,
        timestamp=req_auth.timestamp,
        nonce=req_auth.nonce,
        signature=fake_sig
    )
    
    with pytest.raises(TransportError, match="request signature validation failed"):
        # We call handle_request directly, but in reality NodeHTTPServer calls verifier.verify
        # For test purity, let's check the verifier by emulating a call like in NodeHTTPServer
        from xenage.network.http_transport import RequestVerifier
        verifier = RequestVerifier()
        verifier.verify("GET", "/v1/heartbeat", b"", req_auth, auth.key_pair.public_key_b64())


@pytest.mark.asyncio
async def test_expired_timestamp(cp_node: ControlPlaneNode):
    # Test for expired timestamp
    auth = MockAuth("any-node", Ed25519KeyPair.generate())
    old_ts = int(time.time()) - 1000  # Far in the past
    req_auth = auth.build_auth("GET", "/v1/heartbeat", b"", timestamp=old_ts)
    
    from xenage.network.http_transport import RequestVerifier
    verifier = RequestVerifier()
    with pytest.raises(TransportError, match="request timestamp is outside the allowed skew"):
        verifier.verify("GET", "/v1/heartbeat", b"", req_auth, auth.key_pair.public_key_b64())


@pytest.mark.asyncio
async def test_replay_attack_nonce(cp_node: ControlPlaneNode):
    # Test for nonce reuse
    auth = MockAuth("any-node", Ed25519KeyPair.generate())
    req_auth = auth.build_auth("GET", "/v1/heartbeat", b"", nonce="once")
    
    from xenage.network.http_transport import RequestVerifier
    verifier = RequestVerifier()
    verifier.verify("GET", "/v1/heartbeat", b"", req_auth, auth.key_pair.public_key_b64())
    
    # Repeated request with the same nonce
    with pytest.raises(TransportError, match="request nonce was already used"):
        verifier.verify("GET", "/v1/heartbeat", b"", req_auth, auth.key_pair.public_key_b64())


@pytest.mark.asyncio
async def test_unauthorized_gui_user(cp_node: ControlPlaneNode):
    # Test for non-existent user connecting to GUI
    attacker_key = Ed25519KeyPair.generate()
    auth = MockAuth("attacker", attacker_key)
    req_auth = auth.build_auth("GET", "/v1/gui/cluster", b"")
    
    # ControlPlaneNode.handle_request calls gui_logic.verify_admin_user
    with pytest.raises(TransportError, match="unknown user id"):
        await cp_node.handle_request("GET", "/v1/gui/cluster", b"", req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_disabled_gui_user(cp_node: ControlPlaneNode):
    # Test for disabled user connection
    user_key = Ed25519KeyPair.generate()
    user_id = "disabled-user"
    user = UserRecord(
        user_id=user_id,
        public_key=user_key.public_key_b64(),
        enabled=False,
        roles=[UserRoleBinding(role="admin")]
    )
    current_state = cp_node.user_state_manager.get_state()
    next_state = UserState(
        version=current_state.version + 1,
        users=[*current_state.users, user],
        event_log=current_state.event_log
    )
    cp_node.user_state_manager.replace_state(next_state)
    
    auth = MockAuth(user_id, user_key)
    req_auth = auth.build_auth("GET", "/v1/gui/cluster", b"")
    
    with pytest.raises(TransportError, match="user is disabled"):
        await cp_node.handle_request("GET", "/v1/gui/cluster", b"", req_auth, user_key.public_key_b64())


@pytest.mark.asyncio
async def test_non_admin_gui_access(cp_node: ControlPlaneNode):
    # Test for user access without admin role
    user_key = Ed25519KeyPair.generate()
    user_id = "regular-user"
    user = UserRecord(
        user_id=user_id,
        public_key=user_key.public_key_b64(),
        enabled=True,
        roles=[UserRoleBinding(role="viewer")]
    )
    current_state = cp_node.user_state_manager.get_state()
    next_state = UserState(
        version=current_state.version + 1,
        users=[*current_state.users, user],
        event_log=current_state.event_log
    )
    cp_node.user_state_manager.replace_state(next_state)
    
    auth = MockAuth(user_id, user_key)
    req_auth = auth.build_auth("GET", "/v1/gui/cluster", b"")
    
    with pytest.raises(TransportError, match="user is not authorized"):
        await cp_node.handle_request("GET", "/v1/gui/cluster", b"", req_auth, user_key.public_key_b64())


@pytest.mark.asyncio
async def test_gui_user_wrong_key(cp_node: ControlPlaneNode):
    # Test for key substitution for an existing user
    user_key = Ed25519KeyPair.generate()
    user_id = "admin-user"
    user = UserRecord(
        user_id=user_id,
        public_key=user_key.public_key_b64(),
        enabled=True,
        roles=[UserRoleBinding(role="admin")]
    )
    current_state = cp_node.user_state_manager.get_state()
    next_state = UserState(
        version=current_state.version + 1,
        users=[*current_state.users, user],
        event_log=current_state.event_log
    )
    cp_node.user_state_manager.replace_state(next_state)
    
    attacker_key = Ed25519KeyPair.generate()
    auth = MockAuth(user_id, attacker_key)
    # Attacker signs the request with their own key but impersonates admin-user
    req_auth = auth.build_auth("GET", "/v1/gui/cluster", b"")
    
    with pytest.raises(TransportError, match="request signer public key does not match stored user key"):
        await cp_node.handle_request("GET", "/v1/gui/cluster", b"", req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_join_invalid_token(cp_node: ControlPlaneNode):
    # Test for joining with an incorrect token
    new_node_key = Ed25519KeyPair.generate()
    auth = MockAuth("new-node", new_node_key)
    
    join_req = JoinRequest(
        node=NodeRecord(node_id="new-node", role="runtime", public_key=new_node_key.public_key_b64(), endpoints=[]),
        bootstrap_token="invalid-token"
    )
    from xenage.serialization import encode_value
    body = encode_value(join_req)
    req_auth = auth.build_auth("POST", "/v1/join", body)
    
    # We expect a JoinResponse with accepted=False
    from structures.resources.membership import JoinResponse
    response = await cp_node.handle_request("POST", "/v1/join", body, req_auth, new_node_key.public_key_b64())
    assert isinstance(response, JoinResponse)
    assert response.accepted is False
    assert "token" in response.reason.lower()


@pytest.mark.asyncio
async def test_join_node_id_mismatch(cp_node: ControlPlaneNode):
    # Test for node_id mismatch between request and headers
    new_node_key = Ed25519KeyPair.generate()
    auth = MockAuth("real-node-id", new_node_key)
    
    join_req = JoinRequest(
        node=NodeRecord(node_id="fake-node-id", role="runtime", public_key=new_node_key.public_key_b64(), endpoints=[]),
        bootstrap_token="some-token"
    )
    from xenage.serialization import encode_value
    body = encode_value(join_req)
    req_auth = auth.build_auth("POST", "/v1/join", body)
    
    with pytest.raises(TransportError, match="node_id does not match signed node_id"):
        await cp_node.handle_request("POST", "/v1/join", body, req_auth, new_node_key.public_key_b64())


@pytest.mark.asyncio
async def test_join_public_key_mismatch(cp_node: ControlPlaneNode):
    # Test for public key mismatch between request and headers
    new_node_key = Ed25519KeyPair.generate()
    other_key = Ed25519KeyPair.generate()
    auth = MockAuth("new-node", new_node_key)
    
    join_req = JoinRequest(
        node=NodeRecord(node_id="new-node", role="runtime", public_key=other_key.public_key_b64(), endpoints=[]),
        bootstrap_token="some-token"
    )
    from xenage.serialization import encode_value
    body = encode_value(join_req)
    req_auth = auth.build_auth("POST", "/v1/join", body)
    
    with pytest.raises(TransportError, match="public key does not match signer public key"):
        await cp_node.handle_request("POST", "/v1/join", body, req_auth, new_node_key.public_key_b64())


@pytest.mark.asyncio
async def test_known_signer_violation(cp_node: ControlPlaneNode):
    # Test for key substitution of an existing cluster node
    # 1. Add node to cluster legally
    node_a_key = Ed25519KeyPair.generate()
    token = cp_node.issue_bootstrap_token(60)
    
    join_req = JoinRequest(
        node=NodeRecord(node_id="node-a", role="control-plane", public_key=node_a_key.public_key_b64(), endpoints=[]),
        bootstrap_token=token
    )
    from xenage.serialization import encode_value
    body = encode_value(join_req)
    auth_a = MockAuth("node-a", node_a_key)
    req_auth_a = auth_a.build_auth("POST", "/v1/join", body)
    await cp_node.handle_request("POST", "/v1/join", body, req_auth_a, node_a_key.public_key_b64())
    
    # 2. Now attacker tries to send a request on behalf of node-a but with their own key
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("node-a", attacker_key)
    req_auth_attacker = auth_attacker.build_auth("GET", "/v1/heartbeat", b"")
    
    # handle_request calls verify_known_signer from BaseNode
    with pytest.raises(TransportError, match="request signer public key does not match group state"):
        await cp_node.handle_request("GET", "/v1/heartbeat", b"", req_auth_attacker, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_control_plane_events_unauthorized_node(cp_node: ControlPlaneNode):
    # Test for access to Control Plane events from an unauthorized node
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("attacker-node", attacker_key)
    req_auth = auth_attacker.build_auth("GET", "/v1/control-plane/events", b"")
    
    with pytest.raises(TransportError, match="requester is not a control-plane node"):
        await cp_node.handle_request("GET", "/v1/control-plane/events", b"", req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_control_plane_sync_status_unauthorized_node(cp_node: ControlPlaneNode):
    # Test for trying to update sync status on behalf of another node
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("attacker-node", attacker_key)
    req_auth = auth_attacker.build_auth("POST", "/v1/control-plane/sync-status", b"{}")
    
    with pytest.raises(TransportError, match="requester is not a control-plane node"):
        await cp_node.handle_request("POST", "/v1/control-plane/sync-status", b"{}", req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_revoke_requires_control_plane_requester(cp_node: ControlPlaneNode):
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("attacker-node", attacker_key)
    payload = encode_value(RevokeNodeRequest(node_id="cp-1"))
    req_auth = auth_attacker.build_auth("POST", "/v1/revoke", payload)

    with pytest.raises(TransportError, match="requester is not a control-plane node"):
        await cp_node.handle_request("POST", "/v1/revoke", payload, req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_endpoints_requires_control_plane_requester(cp_node: ControlPlaneNode):
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("attacker-node", attacker_key)
    payload = encode_value(EndpointUpdateRequest(node_id="cp-1", endpoints=["http://127.0.0.1:9999"]))
    req_auth = auth_attacker.build_auth("POST", "/v1/endpoints", payload)

    with pytest.raises(TransportError, match="requester is not a control-plane node"):
        await cp_node.handle_request("POST", "/v1/endpoints", payload, req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_state_current_requires_known_cluster_node(cp_node: ControlPlaneNode):
    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("attacker-node", attacker_key)
    req_auth = auth_attacker.build_auth("GET", "/v1/state/current", b"")

    with pytest.raises(TransportError, match="requester is not a cluster node"):
        await cp_node.handle_request("GET", "/v1/state/current", b"", req_auth, attacker_key.public_key_b64())


@pytest.mark.asyncio
async def test_state_current_rejects_known_node_key_substitution(cp_node: ControlPlaneNode):
    node_key = Ed25519KeyPair.generate()
    token = cp_node.issue_bootstrap_token(60)
    join_req = JoinRequest(
        node=NodeRecord(node_id="node-a", role="control-plane", public_key=node_key.public_key_b64(), endpoints=[]),
        bootstrap_token=token,
    )
    body = encode_value(join_req)
    auth_node = MockAuth("node-a", node_key)
    req_auth_node = auth_node.build_auth("POST", "/v1/join", body)
    await cp_node.handle_request("POST", "/v1/join", body, req_auth_node, node_key.public_key_b64())

    attacker_key = Ed25519KeyPair.generate()
    auth_attacker = MockAuth("node-a", attacker_key)
    req_auth_attacker = auth_attacker.build_auth("GET", "/v1/state/current", b"")
    with pytest.raises(TransportError, match="request signer public key does not match group state"):
        await cp_node.handle_request("GET", "/v1/state/current", b"", req_auth_attacker, attacker_key.public_key_b64())
