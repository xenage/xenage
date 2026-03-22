from __future__ import annotations

from pathlib import Path

import pytest

from structures.resources.membership import (
    ClusterNodeTableRow,
    EventLogEntry,
    GroupState,
    GuiClusterSnapshot,
    GuiEventPage,
    NodeRecord,
)
from xenage.cli_ultimate.main import XenageCliApp


class FakeClient:
    def __init__(self) -> None:
        self.events_limit: int | None = None
        self.resources_call: tuple[str, str] | None = None
        self.can_i_calls: list[tuple[str, str, str]] = []
        self.applied_docs: list[dict[str, object]] = []

    def fetch_cluster_snapshot(self) -> GuiClusterSnapshot:
        return GuiClusterSnapshot(
            group_id="g-1",
            state_version=4,
            leader_epoch=2,
            nodes=[
                ClusterNodeTableRow(
                    node_id="cp-1",
                    role="control-plane",
                    leader=True,
                    public_key="pk",
                    endpoints=["http://cp-1:8734"],
                    status="ready",
                ),
                ClusterNodeTableRow(
                    node_id="rt-1",
                    role="runtime",
                    leader=False,
                    public_key="pk-rt",
                    endpoints=[],
                    status="ready",
                ),
            ],
        )

    def fetch_cluster_events(self, limit: int = 50) -> GuiEventPage:
        self.events_limit = limit
        return GuiEventPage(
            items=[
                EventLogEntry(
                    sequence=11,
                    happened_at="2026-03-21T12:00:00Z",
                    actor_id="cp-1",
                    actor_type="node",
                    action="group.updated",
                )
            ],
            has_more=False,
            next_before_sequence=0,
        )

    def fetch_current_state(self) -> GroupState:
        return GroupState(
            group_id="g-1",
            version=4,
            leader_epoch=2,
            leader_node_id="cp-1",
            leader_pubkey="leader-pk",
            control_planes=[NodeRecord(node_id="cp-1", role="control-plane", public_key="pk")],
            runtimes=[NodeRecord(node_id="rt-1", role="runtime", public_key="pk-rt")],
            endpoints=[],
            expires_at="2026-03-22T00:00:00Z",
        )

    def fetch_resources(self, resource: str, namespace: str = "default") -> list[dict[str, object]]:
        self.resources_call = (resource, namespace)
        return [
            {"kind": "ServiceAccount", "metadata": {"name": "svc-a", "namespace": "ops"}},
            {"kind": "ServiceAccount", "metadata": {"name": "svc-b"}},
        ]

    def apply_manifest(self, doc: dict[str, object]) -> dict[str, object]:
        self.applied_docs.append(doc)
        metadata = doc.get("metadata", {})
        namespace = "default"
        name = ""
        if isinstance(metadata, dict):
            namespace = str(metadata.get("namespace", "default"))
            name = str(metadata.get("name", ""))
        return {
            "kind": str(doc.get("kind", "")),
            "namespace": namespace,
            "name": name,
            "status": "applied",
        }

    def can_i(self, verb: str, resource: str, namespace: str = "default") -> dict[str, object]:
        self.can_i_calls.append((verb, resource, namespace))
        return {"allowed": namespace == "default"}


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    monkeypatch.setattr(
        "xenage.cli_ultimate.main.ControlPlaneClient.from_yaml",
        classmethod(lambda cls, path: client),
    )


def test_execute_get_nodes_renders_table(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()

    code = app.execute(["--config", "/tmp/config.yaml", "get", "nodes"])

    assert code == 0
    out = capsys.readouterr().out
    assert "NODE" in out
    assert "cp-1" in out
    assert "ready (leader)" in out
    assert "http://cp-1:8734" in out
    assert "rt-1" in out
    assert " -" in out


def test_execute_get_events_json_forwards_limit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()

    code = app.execute(["--config", "/tmp/config.yaml", "get", "events", "--limit", "7", "-o", "json"])

    assert code == 0
    assert client.events_limit == 7
    out = capsys.readouterr().out
    assert '"items": [' in out
    assert '"sequence": 11' in out


def test_execute_get_state_with_table_output_falls_back_to_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()

    code = app.execute(["--config", "/tmp/config.yaml", "get", "state", "-o", "table"])

    assert code == 0
    out = capsys.readouterr().out
    assert '"leader_node_id": "cp-1"' in out
    assert '"group_id": "g-1"' in out


def test_execute_get_resources_table_passes_namespace(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()

    code = app.execute(
        ["--config", "/tmp/config.yaml", "get", "serviceaccounts", "--namespace", "ops", "-o", "table"]
    )

    assert code == 0
    assert client.resources_call == ("serviceaccounts", "ops")
    out = capsys.readouterr().out
    assert "KIND" in out
    assert "NAMESPACE" in out
    assert "svc-a" in out
    assert "svc-b" in out
    assert "ops" in out
    assert "default" in out


def test_execute_apply_reads_multi_doc_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        (
            "kind: ServiceAccount\n"
            "metadata:\n"
            "  name: svc-a\n"
            "  namespace: ops\n"
            "---\n"
            "kind: RoleBinding\n"
            "metadata:\n"
            "  name: rb-a\n"
        ),
        encoding="utf-8",
    )

    code = app.execute(["--config", "/tmp/config.yaml", "apply", "-f", str(manifest_path)])

    assert code == 0
    assert len(client.applied_docs) == 2
    out = capsys.readouterr().out
    assert "STATUS" in out
    assert "svc-a" in out
    assert "rb-a" in out
    assert "applied" in out


def test_execute_auth_can_i_and_top_level_can_i(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    _patch_client(monkeypatch, client)
    app = XenageCliApp()

    code_auth = app.execute(["--config", "/tmp/config.yaml", "auth", "can-i", "get", "nodes"])
    out_auth = capsys.readouterr().out
    code_top = app.execute(
        ["--config", "/tmp/config.yaml", "can-i", "get", "nodes", "--namespace", "ops"]
    )
    out_top = capsys.readouterr().out

    assert code_auth == 0
    assert out_auth == "yes\n"
    assert code_top == 0
    assert out_top == "no\n"
    assert client.can_i_calls == [("get", "nodes", "default"), ("get", "nodes", "ops")]


def test_resolve_config_path_prefers_explicit_path() -> None:
    app = XenageCliApp()
    assert app._resolve_config_path("/tmp/config.yaml") == "/tmp/config.yaml"


def test_resolve_config_path_uses_default_in_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = XenageCliApp()
    config = tmp_path / ".xenage" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("cluster_name: demo\n", encoding="utf-8")
    monkeypatch.setattr("xenage.cli_ultimate.main.Path.home", staticmethod(lambda: tmp_path))

    resolved = app._resolve_config_path(None)

    assert resolved == str(config)


def test_resolve_config_path_raises_without_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = XenageCliApp()
    monkeypatch.setattr("xenage.cli_ultimate.main.Path.home", staticmethod(lambda: tmp_path))

    with pytest.raises(RuntimeError, match="--config not provided"):
        app._resolve_config_path(None)
