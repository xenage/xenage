from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from structures.resources.membership import GuiUserBootstrapRequest
from xenage.cli_ultimate.main import XenageCliApp
from xenage.crypto import Ed25519KeyPair
from xenage.network.http_transport import SignedTransportClient, TransportError
from xenage.nodes.control_plane import ControlPlaneNode
from xenage.serialization import encode_value


class FakeCliClient:
    def __init__(self) -> None:
        self.apply_calls: list[dict[str, object]] = []

    def fetch_cluster_snapshot(self) -> object:
        class Snapshot:
            nodes = []
        return Snapshot()

    def fetch_cluster_events(self, limit: int = 10) -> object:
        class Page:
            items = []
        return Page()

    def fetch_current_state(self) -> object:
        return {"state": "ok"}

    def fetch_resources(self, resource: str, namespace: str) -> list[dict[str, object]]:
        return [{"kind": "ServiceAccount", "metadata": {"name": "agent", "namespace": namespace}}]

    def apply_manifest(self, manifest: dict[str, object]) -> dict[str, object]:
        self.apply_calls.append(manifest)
        metadata = manifest.get("metadata", {})
        if isinstance(metadata, dict):
            name = str(metadata.get("name", ""))
            namespace = str(metadata.get("namespace", "default"))
        else:
            name = ""
            namespace = "default"
        return {
            "kind": str(manifest.get("kind", "")),
            "name": name,
            "namespace": namespace,
            "status": "applied",
        }

    def can_i(self, verb: str, resource: str, namespace: str) -> dict[str, object]:
        allowed = verb == "get" and resource == "nodes" and namespace == "ai"
        return {"allowed": allowed}


class FakeFromYaml:
    def __init__(self, client: FakeCliClient) -> None:
        self.client = client

    def __call__(self, path: str) -> FakeCliClient:
        return self.client


def _bootstrap_admin(node: ControlPlaneNode, user_id: str = "admin") -> tuple[str, Ed25519KeyPair]:
    key_pair = Ed25519KeyPair.generate()
    token = node.issue_gui_bootstrap_token(60)
    request = GuiUserBootstrapRequest(
        bootstrap_token=token,
        user_id=user_id,
        public_key=key_pair.public_key_b64(),
        control_plane_urls=["http://127.0.0.1:8734"],
    )
    asyncio.run(node.handle_request("POST", "/v1/gui/bootstrap-user", encode_value(request), request_auth_empty(), ""))
    return user_id, key_pair


def request_auth_empty() -> object:
    class EmptyAuth:
        node_id = ""
        timestamp = 0
        nonce = ""
        signature = ""
    return EmptyAuth()


def _auth_for(user_id: str, key_pair: Ed25519KeyPair, method: str, path: str, body: bytes) -> object:
    signer = SignedTransportClient(user_id, key_pair.public_key_b64(), key_pair)
    return signer.build_auth(method, path, body)


def _apply(node: ControlPlaneNode, user_id: str, key_pair: Ed25519KeyPair, manifest: dict[str, object]) -> object:
    body = encode_value(manifest)
    auth = _auth_for(user_id, key_pair, "POST", "/v1/resources/apply", body)
    return asyncio.run(node.handle_request("POST", "/v1/resources/apply", body, auth, key_pair.public_key_b64()))


def _can_i(node: ControlPlaneNode, user_id: str, key_pair: Ed25519KeyPair, verb: str, resource: str, namespace: str) -> dict[str, object]:
    payload = {"verb": verb, "resource": resource, "namespace": namespace}
    body = encode_value(payload)
    auth = _auth_for(user_id, key_pair, "POST", "/v1/auth/can-i", body)
    response = asyncio.run(node.handle_request("POST", "/v1/auth/can-i", body, auth, key_pair.public_key_b64()))
    assert isinstance(response, dict)
    return response


@pytest.fixture
def node(tmp_path: Path) -> ControlPlaneNode:
    cp_node = ControlPlaneNode("cp-1", tmp_path / "cp-1", ["http://127.0.0.1:8734"])
    cp_node.initialize_group("rbac", 60)
    return cp_node


def test_cli_apply_passes_all_documents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_client = FakeCliClient()
    monkeypatch.setattr("xenage.cli_ultimate.main.ControlPlaneClient.from_yaml", FakeFromYaml(fake_client))

    manifest_path = tmp_path / "rbac.yaml"
    manifest_path.write_text(
        """
apiVersion: xenage.dev/v1
kind: ServiceAccount
metadata:
  name: agent-runner
spec:
  engine: runtime/v1
  publicKey: pk
---
apiVersion: rbac.authorization.xenage.dev/v1
kind: Role
metadata:
  name: runner
rules:
  - apiGroups: [\"\"]
    namespaces: [\"ai\"]
    resources: [\"nodes\"]
    verbs: [\"get\", \"list\"]
""".strip()
    )

    app = XenageCliApp()
    code = app.execute(["--config", "/tmp/fake.yaml", "apply", "-f", str(manifest_path)])
    assert code == 0
    assert len(fake_client.apply_calls) == 2


def test_cli_auth_can_i_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeCliClient()
    monkeypatch.setattr("xenage.cli_ultimate.main.ControlPlaneClient.from_yaml", FakeFromYaml(fake_client))

    app = XenageCliApp()
    code = app.execute(["--config", "/tmp/fake.yaml", "can-i", "get", "nodes", "--namespace", "ai"])
    assert code == 0


def test_api_apply_role_and_binding_then_can_i(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    runner_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "agent-runner"},
            "spec": {"engine": "runtime/v1", "publicKey": runner_key.public_key_b64()},
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "Role",
            "metadata": {"name": "agent-runner-role"},
            "rules": [{"apiGroups": [""], "namespaces": ["ai"], "resources": ["nodes"], "verbs": ["get", "list"]}],
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "RoleBinding",
            "metadata": {"name": "agent-runner-binding"},
            "subjects": [{"kind": "ServiceAccount", "name": "agent-runner"}],
            "roleRef": {"apiGroup": "rbac.authorization.xenage.dev", "kind": "Role", "name": "agent-runner-role"},
        },
    )

    result = _can_i(node, "agent-runner", runner_key, "get", "nodes", "ai")
    assert result["allowed"] is True


def test_api_can_i_denies_verb_without_rule(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    viewer_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "viewer"},
            "spec": {"engine": "runtime/v1", "publicKey": viewer_key.public_key_b64()},
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "Role",
            "metadata": {"name": "viewer-role"},
            "rules": [{"apiGroups": [""], "namespaces": ["ai"], "resources": ["nodes"], "verbs": ["get"]}],
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "RoleBinding",
            "metadata": {"name": "viewer-binding"},
            "subjects": [{"kind": "ServiceAccount", "name": "viewer"}],
            "roleRef": {"apiGroup": "rbac.authorization.xenage.dev", "kind": "Role", "name": "viewer-role"},
        },
    )

    result = _can_i(node, "viewer", viewer_key, "delete", "nodes", "ai")
    assert result["allowed"] is False


def test_api_rejects_unknown_api_version(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    with pytest.raises(TransportError):
        _apply(
            node,
            admin_id,
            admin_key,
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "oops"},
                "spec": {"engine": "runtime/v1", "publicKey": "pk"},
            },
        )


def test_api_rejects_rolebinding_with_missing_role(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    with pytest.raises(TransportError):
        _apply(
            node,
            admin_id,
            admin_key,
            {
                "apiVersion": "rbac.authorization.xenage.dev/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "broken"},
                "subjects": [{"kind": "ServiceAccount", "name": "agent-runner"}],
                "roleRef": {"apiGroup": "rbac.authorization.xenage.dev", "kind": "Role", "name": "missing"},
            },
        )


def test_api_rejects_serviceaccount_key_substitution_attack(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "secured"},
            "spec": {"engine": "runtime/v1", "publicKey": "pk-1"},
        },
    )
    with pytest.raises(TransportError):
        _apply(
            node,
            admin_id,
            admin_key,
            {
                "apiVersion": "xenage.dev/v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "secured"},
                "spec": {"engine": "runtime/v1", "publicKey": "pk-2"},
            },
        )


def test_api_denies_cross_namespace_permission(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    viewer_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "viewer"},
            "spec": {"engine": "runtime/v1", "publicKey": viewer_key.public_key_b64()},
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "Role",
            "metadata": {"name": "viewer"},
            "rules": [{"apiGroups": [""], "namespaces": ["ai"], "resources": ["nodes"], "verbs": ["get"]}],
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "RoleBinding",
            "metadata": {"name": "viewer"},
            "subjects": [{"kind": "ServiceAccount", "name": "viewer"}],
            "roleRef": {"apiGroup": "rbac.authorization.xenage.dev", "kind": "Role", "name": "viewer"},
        },
    )

    result = _can_i(node, "viewer", viewer_key, "get", "nodes", "prod")
    assert result["allowed"] is False


def test_gui_forbidden_without_get_nodes_permission(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    limited_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "limited"},
            "spec": {"engine": "runtime/v1", "publicKey": limited_key.public_key_b64()},
        },
    )
    auth = _auth_for("limited", limited_key, "GET", "/v1/gui/cluster", b"")
    with pytest.raises(TransportError):
        asyncio.run(node.handle_request("GET", "/v1/gui/cluster", b"", auth, limited_key.public_key_b64()))


def test_gui_allowed_with_get_nodes_permission(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    limited_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "viewer"},
            "spec": {"engine": "runtime/v1", "publicKey": limited_key.public_key_b64()},
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "Role",
            "metadata": {"name": "viewer"},
            "rules": [{"apiGroups": [""], "namespaces": ["cluster"], "resources": ["nodes", "events"], "verbs": ["get", "list"]}],
        },
    )
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "RoleBinding",
            "metadata": {"name": "viewer"},
            "subjects": [{"kind": "ServiceAccount", "name": "viewer"}],
            "roleRef": {"apiGroup": "rbac.authorization.xenage.dev", "kind": "Role", "name": "viewer"},
        },
    )

    auth = _auth_for("viewer", limited_key, "GET", "/v1/gui/cluster", b"")
    snapshot = asyncio.run(node.handle_request("GET", "/v1/gui/cluster", b"", auth, limited_key.public_key_b64()))
    assert snapshot.group_id == "rbac"


def test_api_rejects_privilege_escalation_apply_without_permission(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    attacker_key = Ed25519KeyPair.generate()
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "attacker"},
            "spec": {"engine": "runtime/v1", "publicKey": attacker_key.public_key_b64()},
        },
    )
    body = encode_value(
        {
            "apiVersion": "rbac.authorization.xenage.dev/v1",
            "kind": "Role",
            "metadata": {"name": "escalate"},
            "rules": [{"apiGroups": [""], "resources": ["*"], "verbs": ["*"]}],
        },
    )
    auth = _auth_for("attacker", attacker_key, "POST", "/v1/resources/apply", body)
    with pytest.raises(TransportError):
        asyncio.run(node.handle_request("POST", "/v1/resources/apply", body, auth, attacker_key.public_key_b64()))


def test_api_lists_resources_for_authorized_subject(node: ControlPlaneNode) -> None:
    admin_id, admin_key = _bootstrap_admin(node)
    _apply(
        node,
        admin_id,
        admin_key,
        {
            "apiVersion": "xenage.dev/v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "auditor"},
            "spec": {"engine": "runtime/v1", "publicKey": "pk-auditor"},
        },
    )
    body = b""
    auth = _auth_for(admin_id, admin_key, "GET", "/v1/resources/serviceaccounts?namespace=ai", body)
    response = asyncio.run(
        node.handle_request(
            "GET",
            "/v1/resources/serviceaccounts?namespace=ai",
            body,
            auth,
            admin_key.public_key_b64(),
        )
    )
    assert isinstance(response, dict)
    assert isinstance(response.get("items"), list)
