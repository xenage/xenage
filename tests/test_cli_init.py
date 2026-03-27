from __future__ import annotations

from typing import Any

import pytest

from xenage.cli_ultimate.main import XenageCliApp


class FakeInitCommand:
    def __init__(self) -> None:
        self.called_with: str | None = None

    def run(self, option: str | None = None) -> int:
        self.called_with = option
        return 0


def test_execute_init_runs_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    app = XenageCliApp()
    fake_init = FakeInitCommand()
    app.init_command = fake_init

    def fail_from_yaml(cls: type[Any], path: str) -> Any:
        _ = cls
        _ = path
        raise AssertionError("from_yaml must not be called for init")

    monkeypatch.setattr("xenage.cli_ultimate.main.ControlPlaneClient.from_yaml", classmethod(fail_from_yaml))

    code = app.execute(["init", "--option", "runtime-join"])

    assert code == 0
    assert fake_init.called_with == "runtime-join"


def test_execute_init_defaults_to_interactive_option() -> None:
    app = XenageCliApp()
    fake_init = FakeInitCommand()
    app.init_command = fake_init

    code = app.execute(["init"])

    assert code == 0
    assert fake_init.called_with is None
