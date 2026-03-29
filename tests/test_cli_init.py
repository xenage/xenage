from __future__ import annotations

import builtins
from typing import Any

import pytest

from xenage.cli_ultimate.init_flow import XenageInitCommand
from xenage.cli_ultimate.main import XenageCliApp


class FakeInitCommand:
    def __init__(self) -> None:
        self.called_with: str | None = None

    def run(self, option: str | None = None) -> int:
        self.called_with = option
        return 0


class FakeReleaseEnv:
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        self.payloads = payloads

    def fetch_json(self, url: str) -> dict[str, object]:
        payload = self.payloads.get(url)
        if payload is None:
            raise AssertionError(f"unexpected URL: {url}")
        return payload


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


def test_execute_init_interactive_retries_until_valid_selection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = XenageCliApp()

    called: list[bool] = []

    def fake_install_gui_release() -> None:
        called.append(True)

    monkeypatch.setattr(app.init_command, "_install_gui_release", fake_install_gui_release)
    answers = iter(["", "abc", "5", "1"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))

    code = app.execute(["init"])

    assert code == 0
    assert called == [True]
    out = capsys.readouterr().out
    assert "What would you like to do?" in out
    assert out.count("Please enter a number from 1 to 4.") == 3


def test_execute_init_handles_eof_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    app = XenageCliApp()
    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)

    code = app.execute(["init"])

    assert code == 1
    out = capsys.readouterr().out
    assert "Input stream closed. Exiting init wizard." in out


def test_gui_release_asset_resolution_prefers_app_artifacts() -> None:
    env = FakeReleaseEnv(
        {
            XenageInitCommand.GUI_RELEASE_API_URL: {
                "assets": [
                    {"name": "linux_x86_xenage_gui_1.2.3.rpm", "browser_download_url": "https://example/rpm"},
                    {"name": "linux_x86_xenage_gui_1.2.3.deb", "browser_download_url": "https://example/deb"},
                    {
                        "name": "linux_x86_xenage_gui_1.2.3.AppImage",
                        "browser_download_url": "https://example/appimage",
                    },
                ]
            }
        }
    )
    command = XenageInitCommand(env=env)

    url = command._resolve_gui_asset_url_from_release_assets("linux-x86_64")

    assert url == "https://example/appimage"


def test_gui_release_asset_resolution_prefers_macos_app_bundle_not_dmg() -> None:
    env = FakeReleaseEnv(
        {
            XenageInitCommand.GUI_RELEASE_API_URL: {
                "assets": [
                    {"name": "mac_x86_Xenage_GUI.dmg", "browser_download_url": "https://example/dmg"},
                    {
                        "name": "mac_x86_xenage_gui_1.2.3.app.tar.gz",
                        "browser_download_url": "https://example/app-tar",
                    },
                ]
            }
        }
    )
    command = XenageInitCommand(env=env)

    url = command._resolve_gui_asset_url_from_release_assets("darwin-x86_64")

    assert url == "https://example/app-tar"


def test_gui_release_asset_resolution_prefers_windows_exe_installer() -> None:
    env = FakeReleaseEnv(
        {
            XenageInitCommand.GUI_RELEASE_API_URL: {
                "assets": [
                    {"name": "win_x86_Xenage_GUI_1.2.3_en-US.msi", "browser_download_url": "https://example/msi"},
                    {"name": "win_x86_Xenage_GUI_1.2.3.msi.zip", "browser_download_url": "https://example/msi-zip"},
                    {
                        "name": "win_x86_Xenage_GUI_1.2.3-setup.exe",
                        "browser_download_url": "https://example/setup-exe",
                    },
                ]
            }
        }
    )
    command = XenageInitCommand(env=env)

    url = command._resolve_gui_asset_url_from_release_assets("windows-x86_64")

    assert url == "https://example/setup-exe"


def test_gui_release_asset_resolution_falls_back_to_compatible_arch() -> None:
    env = FakeReleaseEnv(
        {
            XenageInitCommand.GUI_RELEASE_API_URL: {
                "assets": [
                    {
                        "name": "mac_x86_xenage_gui_1.2.3.app.tar.gz",
                        "browser_download_url": "https://example/mac-x86",
                    }
                ]
            }
        }
    )
    command = XenageInitCommand(env=env)

    url = command._resolve_gui_asset_url_from_release_assets("darwin-aarch64")

    assert url == "https://example/mac-x86"


def test_gui_manifest_installer_url_falls_back_to_release_app_artifact() -> None:
    env = FakeReleaseEnv(
        {
            XenageInitCommand.GUI_MANIFEST_URL: {
                "platforms": {
                    "darwin-x86_64": {"url": "https://example.com/xenage-gui.dmg"},
                }
            },
            XenageInitCommand.GUI_RELEASE_API_URL: {
                "assets": [
                    {
                        "name": "mac_x86_xenage_gui_1.2.3.app.tar.gz",
                        "browser_download_url": "https://example.com/xenage-gui.app.tar.gz",
                    }
                ]
            },
        }
    )
    command = XenageInitCommand(env=env)

    url = command._resolve_gui_asset_url("darwin-x86_64")

    assert url == "https://example.com/xenage-gui.app.tar.gz"
