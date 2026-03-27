from __future__ import annotations

import json
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .init_support import InitEnvironment


@dataclass(frozen=True)
class InitOption:
    key: str
    title: str
    description: str


class XenageInitCommand:
    GUI_MANIFEST_URL: Final[str] = "https://github.com/xenage/xenage/releases/latest/download/latest.json"
    GUI_NIGHTLY_MANIFEST_URL: Final[str] = "https://github.com/xenage/xenage/releases/download/nightly/latest.json"
    GUI_RELEASE_API_URL: Final[str] = "https://api.github.com/repos/xenage/xenage/releases/latest"
    GUI_NIGHTLY_RELEASE_API_URL: Final[str] = "https://api.github.com/repos/xenage/xenage/releases/tags/nightly"

    def __init__(self, env: InitEnvironment | None = None) -> None:
        self.env = env or InitEnvironment()
        self.options: tuple[InitOption, ...] = (
            InitOption(
                key="gui",
                title="Установить GUI",
                description="Определить текущую ОС и установить GUI из latest release",
            ),
            InitOption(
                key="control-plane-create",
                title="Установить control-plane и создать кластер",
                description="Инициализировать новый кластер, запустить ноду и создать ~/.xenage/config.yaml",
            ),
            InitOption(
                key="control-plane-join",
                title="Установить control-plane и подключиться к кластеру",
                description="Подключить control-plane ноду к уже существующему кластеру",
            ),
            InitOption(
                key="runtime-join",
                title="Установить runtime и подключиться к кластеру",
                description="Подключить runtime ноду к существующему control-plane",
            ),
        )

    def run(self, option: str | None = None) -> int:
        selected = option or self._select_option_interactive()
        if selected == "gui":
            self._install_gui_release()
            return 0
        if selected == "control-plane-create":
            self._setup_control_plane_and_create_cluster()
            return 0
        if selected == "control-plane-join":
            self._setup_control_plane_and_join_cluster()
            return 0
        if selected == "runtime-join":
            self._setup_runtime_and_join_cluster()
            return 0
        raise RuntimeError(f"unsupported init option: {selected}")

    def _select_option_interactive(self) -> str:
        self._print_tui_header()
        for index, option in enumerate(self.options, start=1):
            print(f"  {index}. {option.title}")
            print(f"     {option.description}")
        print()
        while True:
            answer = input("Выберите сценарий [1-4]: ").strip()
            if answer in {"1", "2", "3", "4"}:
                return self.options[int(answer) - 1].key
            print("Нужно ввести число от 1 до 4.")

    def _print_tui_header(self) -> None:
        print("\033[96m╔════════════════════════════════════════════════════╗\033[0m")
        print("\033[96m║                 Xenage Init Wizard                ║\033[0m")
        print("\033[96m╚════════════════════════════════════════════════════╝\033[0m")
        print("")
        print("Что вы хотите сделать?")

    def _prompt_text(self, label: str, default: str) -> str:
        raw = input(f"{label} [{default}]: ").strip()
        if raw:
            return raw
        return default

    def _prompt_int(self, label: str, default: int) -> int:
        while True:
            raw = input(f"{label} [{default}]: ").strip()
            if not raw:
                return default
            if raw.isdigit():
                return int(raw)
            print("Введите целое число.")

    def _setup_control_plane_and_create_cluster(self) -> None:
        print("\nНастройка control-plane ноды (создание нового кластера).")
        node_id = self._prompt_text("Node ID", "cp-1")
        default_data = str(Path.home() / ".xenage" / "nodes" / node_id)
        data_dir = self._prompt_text("Data dir", default_data)
        endpoint = self._prompt_text("Public endpoint", "http://127.0.0.1:8734")
        host = self._prompt_text("Bind host", "0.0.0.0")
        port = self._prompt_int("Bind port", 8734)
        group_id = self._prompt_text("Cluster group ID", "demo")

        Path(data_dir).mkdir(parents=True, exist_ok=True)
        init_output = self.env.run_cli([
            "control-plane",
            "--node-id",
            node_id,
            "--data-dir",
            data_dir,
            "--endpoint",
            endpoint,
            "init",
            "--group-id",
            group_id,
        ])

        state = json.loads(init_output)
        leader_pubkey = str(state.get("leader_pubkey", ""))
        if not leader_pubkey:
            raise RuntimeError("control-plane init did not return leader_pubkey")

        log_path = Path(data_dir) / "control-plane.log"
        pid_path = Path(data_dir) / "control-plane.pid"
        self.env.start_background_process(
            args=[
                "control-plane",
                "--node-id",
                node_id,
                "--data-dir",
                data_dir,
                "--endpoint",
                endpoint,
                "serve",
                "--host",
                host,
                "--port",
                str(port),
            ],
            log_path=log_path,
            pid_path=pid_path,
        )
        self.env.wait_for_heartbeat(f"{endpoint.rstrip('/')}/v1/heartbeat", timeout_seconds=20)

        gui_bootstrap_token = self.env.run_cli([
            "control-plane",
            "--node-id",
            node_id,
            "--data-dir",
            data_dir,
            "--endpoint",
            endpoint,
            "gui-bootstrap-token",
        ]).strip()

        config_path = Path.home() / ".xenage" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        self.env.run_cli([
            "control-plane",
            "--node-id",
            node_id,
            "--data-dir",
            data_dir,
            "--endpoint",
            endpoint,
            "gui-bootstrap-user",
            "--leader-url",
            endpoint,
            "--bootstrap-token",
            gui_bootstrap_token,
            "--control-plane-url",
            endpoint,
            "--user-id",
            "admin",
            "--out",
            str(config_path),
        ])

        print("\nГотово.")
        print(f"- Кластер: {group_id}")
        print(f"- Leader public key: {leader_pubkey}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")
        print(f"- CLI config: {config_path}")
        print("- Проверка: xenage get nodes")

    def _setup_control_plane_and_join_cluster(self) -> None:
        print("\nНастройка control-plane ноды (подключение к существующему кластеру).")
        node_id = self._prompt_text("Node ID", "cp-2")
        default_data = str(Path.home() / ".xenage" / "nodes" / node_id)
        data_dir = self._prompt_text("Data dir", default_data)
        endpoint = self._prompt_text("Public endpoint", "http://127.0.0.1:8736")
        host = self._prompt_text("Bind host", "0.0.0.0")
        port = self._prompt_int("Bind port", 8736)
        leader_host = self._prompt_text("Leader host URL", "http://127.0.0.1:8734")
        leader_pubkey = self._prompt_text("Leader public key", "")
        bootstrap_token = self._prompt_text("Bootstrap token", "")

        if not leader_pubkey:
            raise RuntimeError("Leader public key is required")
        if not bootstrap_token:
            raise RuntimeError("Bootstrap token is required")

        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.env.run_cli([
            "control-plane",
            "--node-id",
            node_id,
            "--data-dir",
            data_dir,
            "--endpoint",
            endpoint,
            "connect",
            "--leader-host",
            leader_host,
            "--leader-pubkey",
            leader_pubkey,
            "--bootstrap-token",
            bootstrap_token,
        ])

        log_path = Path(data_dir) / "control-plane.log"
        pid_path = Path(data_dir) / "control-plane.pid"
        self.env.start_background_process(
            args=[
                "control-plane",
                "--node-id",
                node_id,
                "--data-dir",
                data_dir,
                "--endpoint",
                endpoint,
                "serve",
                "--host",
                host,
                "--port",
                str(port),
            ],
            log_path=log_path,
            pid_path=pid_path,
        )
        self.env.wait_for_heartbeat(f"{endpoint.rstrip('/')}/v1/heartbeat", timeout_seconds=20)

        print("\nГотово.")
        print(f"- Нода {node_id} подключена к {leader_host}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")

    def _setup_runtime_and_join_cluster(self) -> None:
        print("\nНастройка runtime ноды (подключение к существующему кластеру).")
        node_id = self._prompt_text("Node ID", "rt-1")
        default_data = str(Path.home() / ".xenage" / "nodes" / node_id)
        data_dir = self._prompt_text("Data dir", default_data)
        leader_host = self._prompt_text("Leader host URL", "http://127.0.0.1:8734")
        leader_pubkey = self._prompt_text("Leader public key", "")
        bootstrap_token = self._prompt_text("Bootstrap token", "")

        if not leader_pubkey:
            raise RuntimeError("Leader public key is required")
        if not bootstrap_token:
            raise RuntimeError("Bootstrap token is required")

        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.env.run_cli([
            "runtime",
            "--node-id",
            node_id,
            "--data-dir",
            data_dir,
            "connect",
            "--leader-host",
            leader_host,
            "--leader-pubkey",
            leader_pubkey,
            "--bootstrap-token",
            bootstrap_token,
        ])

        log_path = Path(data_dir) / "runtime.log"
        pid_path = Path(data_dir) / "runtime.pid"
        self.env.start_background_process(
            args=[
                "runtime",
                "--node-id",
                node_id,
                "--data-dir",
                data_dir,
                "serve",
            ],
            log_path=log_path,
            pid_path=pid_path,
        )

        print("\nГотово.")
        print(f"- Нода {node_id} подключена к {leader_host}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")

    def _install_gui_release(self) -> None:
        target = self.env.release_target()
        print(f"\nУстанавливаю Xenage GUI (latest release) для {target}...")
        url = self._resolve_gui_asset_url(target)
        download_dir = Path.home() / ".xenage" / "gui" / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        archive_path = download_dir / Path(url).name
        try:
            self.env.download_to_path(url, archive_path)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            fallback_url = self._resolve_gui_asset_url_from_release_assets(target)
            print("Ссылка из latest.json недоступна, использую прямой asset из GitHub release.")
            archive_path = download_dir / Path(fallback_url).name
            self.env.download_to_path(fallback_url, archive_path)

        install_root = Path.home() / ".xenage" / "gui"
        install_root.mkdir(parents=True, exist_ok=True)
        installed = self.env.extract_gui_artifact(archive_path, install_root)

        print("\nGUI установлен.")
        print(f"- Файл: {archive_path}")
        print(f"- Результат: {installed}")

    def _resolve_gui_asset_url(self, target: str) -> str:
        try:
            return self._resolve_gui_asset_url_with_manifest(target, self.GUI_MANIFEST_URL)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            print("Latest release manifest not found, falling back to nightly release manifest.")
            return self._resolve_gui_asset_url_with_manifest(target, self.GUI_NIGHTLY_MANIFEST_URL)

    def _resolve_gui_asset_url_with_manifest(self, target: str, manifest_url: str) -> str:
        payload = self.env.fetch_json(manifest_url)
        platforms = payload.get("platforms")
        if not isinstance(platforms, dict):
            raise RuntimeError(f"invalid release manifest at {manifest_url}: missing platforms")

        candidates = [target]
        if target == "darwin-aarch64":
            candidates.append("darwin-x86_64")
        if target == "windows-aarch64":
            candidates.append("windows-x86_64")

        for candidate in candidates:
            target_payload = platforms.get(candidate)
            if not isinstance(target_payload, dict):
                continue
            url = target_payload.get("url")
            if isinstance(url, str) and url:
                if candidate != target:
                    print(f"Целевой артефакт {target} не найден, использую {candidate}.")
                return url

        raise RuntimeError(f"release manifest does not contain target: {target}")

    def _resolve_gui_asset_url_from_release_assets(self, target: str) -> str:
        try:
            payload = self.env.fetch_json(self.GUI_RELEASE_API_URL)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            print("Latest release API endpoint not found, falling back to nightly release API endpoint.")
            payload = self.env.fetch_json(self.GUI_NIGHTLY_RELEASE_API_URL)
        assets = payload.get("assets")
        if not isinstance(assets, list):
            raise RuntimeError("release API payload does not include assets")

        prefix_map = {
            "linux-x86_64": ["linux_x86_"],
            "linux-aarch64": ["linux_aarch_"],
            "darwin-x86_64": ["mac_x86_"],
            "darwin-aarch64": ["mac_aarch_", "mac_x86_"],
            "windows-x86_64": ["win_x86_"],
            "windows-aarch64": ["win_aarch_", "win_x86_"],
        }
        target_prefixes = prefix_map.get(target)
        if target_prefixes is None:
            raise RuntimeError(f"unsupported GUI target: {target}")
        if target.startswith("linux-"):
            preferred_suffixes = [".appimage", ".deb", ".rpm"]
        elif target.startswith("darwin-"):
            preferred_suffixes = [".app.tar.gz", ".dmg"]
        else:
            preferred_suffixes = [".msi", ".exe"]

        candidates: list[dict[str, str]] = []
        for item in assets:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            url = item.get("browser_download_url")
            if not isinstance(name, str) or not isinstance(url, str):
                continue
            lower = name.lower()
            if lower.endswith(".sig") or lower.endswith("control.tar.gz") or lower.endswith("data.tar.gz"):
                continue
            if any(lower.startswith(prefix) for prefix in target_prefixes):
                candidates.append({"name": name, "url": url})

        if not candidates:
            raise RuntimeError(f"no release assets match target {target}")

        for suffix in preferred_suffixes:
            for candidate in candidates:
                if candidate["name"].lower().endswith(suffix):
                    return candidate["url"]

        return candidates[0]["url"]
