from __future__ import annotations

import sys
from typing import Any

import pytest

from xenage import cli


def test_dispatch_mode_uses_executable_aliases() -> None:
    mode, remaining = cli._dispatch_mode("xenage-control-plane", ["--node-id", "cp-1"])
    assert mode == "control-plane"
    assert remaining == ["--node-id", "cp-1"]

    mode, remaining = cli._dispatch_mode("xenage-runtime.exe", ["--node-id", "rt-1"])
    assert mode == "runtime"
    assert remaining == ["--node-id", "rt-1"]


def test_dispatch_mode_uses_explicit_subcommand() -> None:
    mode, remaining = cli._dispatch_mode("xenage", ["control-plane", "--node-id", "cp-1"])
    assert mode == "control-plane"
    assert remaining == ["--node-id", "cp-1"]

    mode, remaining = cli._dispatch_mode("xenage", ["runtime", "--node-id", "rt-1"])
    assert mode == "runtime"
    assert remaining == ["--node-id", "rt-1"]

    mode, remaining = cli._dispatch_mode("xenage", ["get", "nodes"])
    assert mode == "cli"
    assert remaining == ["get", "nodes"]


def test_xenage_cli_main_routes_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_control_plane_main(argv: list[str] | None = None, program_name: str = "xenage-control-plane") -> None:
        calls["argv"] = list(argv or [])
        calls["program_name"] = program_name

    monkeypatch.setattr(cli, "control_plane_main", fake_control_plane_main)
    monkeypatch.setattr(sys, "argv", ["xenage", "control-plane", "--node-id", "cp-1"])

    cli.xenage_cli_main()

    assert calls["argv"] == ["--node-id", "cp-1"]
    assert calls["program_name"] == "xenage control-plane"


def test_xenage_cli_main_routes_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_runtime_main(argv: list[str] | None = None, program_name: str = "xenage-runtime") -> None:
        calls["argv"] = list(argv or [])
        calls["program_name"] = program_name

    monkeypatch.setattr(cli, "runtime_main", fake_runtime_main)
    monkeypatch.setattr(sys, "argv", ["xenage", "runtime", "--node-id", "rt-1"])

    cli.xenage_cli_main()

    assert calls["argv"] == ["--node-id", "rt-1"]
    assert calls["program_name"] == "xenage runtime"


def test_xenage_cli_main_routes_default_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class FakeCliApp:
        def execute(self, argv: list[str]) -> int:
            calls["argv"] = list(argv)
            return 0

    monkeypatch.setattr(cli, "XenageCliApp", FakeCliApp)
    monkeypatch.setattr(sys, "argv", ["xenage", "get", "nodes"])

    cli.xenage_cli_main()

    assert calls["argv"] == ["get", "nodes"]


def test_xenage_cli_main_raises_on_non_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCliApp:
        def execute(self, argv: list[str]) -> int:
            _ = argv
            return 2

    monkeypatch.setattr(cli, "XenageCliApp", FakeCliApp)
    monkeypatch.setattr(sys, "argv", ["xenage", "get", "nodes"])

    with pytest.raises(SystemExit) as error:
        cli.xenage_cli_main()
    assert error.value.code == 2
