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
    _FALLBACK_TARGETS: Final[dict[str, tuple[str, ...]]] = {
        "darwin-aarch64": ("darwin-aarch64", "darwin-x86_64"),
        "windows-aarch64": ("windows-aarch64", "windows-x86_64"),
    }

    def __init__(self, env: InitEnvironment | None = None) -> None:
        self.env = env or InitEnvironment()
        self.options: tuple[InitOption, ...] = (
            InitOption(
                key="gui",
                title="Install GUI",
                description="Detect the current OS and install GUI from the latest release",
            ),
            InitOption(
                key="control-plane-create",
                title="Install control-plane and create a cluster",
                description="Initialize a new cluster, start the node, and create ~/.xenage/config.yaml",
            ),
            InitOption(
                key="control-plane-join",
                title="Install control-plane and join a cluster",
                description="Connect a control-plane node to an existing cluster",
            ),
            InitOption(
                key="runtime-join",
                title="Install runtime and join a cluster",
                description="Connect a runtime node to an existing control-plane",
            ),
        )

    def run(self, option: str | None = None) -> int:
        try:
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
        except EOFError:
            print("\nInput stream closed. Exiting init wizard.")
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting init wizard.")
            return 130

    def _select_option_interactive(self) -> str:
        self._print_tui_header()
        for index, option in enumerate(self.options, start=1):
            print(f"  {index}. {option.title}")
            print(f"     {option.description}")
        print()
        while True:
            answer = input("Choose a scenario [1-4]: ").strip()
            if answer in {"1", "2", "3", "4"}:
                return self.options[int(answer) - 1].key
            print("Please enter a number from 1 to 4.")

    def _print_tui_header(self) -> None:
        print("\033[96m╔════════════════════════════════════════════════════╗\033[0m")
        print("\033[96m║                 Xenage Init Wizard                ║\033[0m")
        print("\033[96m╚════════════════════════════════════════════════════╝\033[0m")
        print("")
        print("What would you like to do?")

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
            print("Please enter an integer.")

    def _setup_control_plane_and_create_cluster(self) -> None:
        print("\nSetting up control-plane node (creating a new cluster).")
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

        print("\nDone.")
        print(f"- Cluster: {group_id}")
        print(f"- Leader public key: {leader_pubkey}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")
        print(f"- CLI config: {config_path}")
        print("- Verify with: xenage get nodes")

    def _setup_control_plane_and_join_cluster(self) -> None:
        print("\nSetting up control-plane node (joining an existing cluster).")
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

        print("\nDone.")
        print(f"- Node {node_id} connected to {leader_host}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")

    def _setup_runtime_and_join_cluster(self) -> None:
        print("\nSetting up runtime node (joining an existing cluster).")
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

        print("\nDone.")
        print(f"- Node {node_id} connected to {leader_host}")
        print(f"- PID: {pid_path}")
        print(f"- Log: {log_path}")

    def _install_gui_release(self) -> None:
        target = self.env.release_target()
        print(f"\nInstalling Xenage GUI (latest release) for {target}...")
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
            print("URL from latest.json is unavailable, using a direct asset from GitHub release.")
            archive_path = download_dir / Path(fallback_url).name
            self.env.download_to_path(fallback_url, archive_path)

        install_root = Path.home() / ".xenage" / "gui"
        install_root.mkdir(parents=True, exist_ok=True)
        installed = self.env.extract_gui_artifact(archive_path, install_root)

        print("\nGUI installed.")
        print(f"- File: {archive_path}")
        print(f"- Result: {installed}")

    def _resolve_gui_asset_url(self, target: str) -> str:
        for manifest_url in (self.GUI_MANIFEST_URL, self.GUI_NIGHTLY_MANIFEST_URL):
            try:
                return self._resolve_gui_asset_url_with_manifest(target, manifest_url)
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                if manifest_url == self.GUI_MANIFEST_URL:
                    print("Latest release manifest not found, falling back to nightly release manifest.")
                continue
            except RuntimeError as error:
                print(f"Manifest URL is not usable for {target}: {error}. Falling back to release assets.")
                break
        return self._resolve_gui_asset_url_from_release_assets(target)

    def _target_candidates(self, target: str) -> tuple[str, ...]:
        return self._FALLBACK_TARGETS.get(target, (target,))

    def _is_supported_gui_artifact_for_target(self, artifact_ref: str, target: str) -> bool:
        lower = artifact_ref.lower()
        if target.startswith("linux-"):
            return lower.endswith(".appimage")
        if target.startswith("darwin-"):
            return lower.endswith(".app.tar.gz")
        if target.startswith("windows-"):
            return lower.endswith(".exe")
        return False

    def _resolve_gui_asset_url_with_manifest(self, target: str, manifest_url: str) -> str:
        payload = self.env.fetch_json(manifest_url)
        platforms = payload.get("platforms")
        if not isinstance(platforms, dict):
            raise RuntimeError(f"invalid release manifest at {manifest_url}: missing platforms")

        for candidate in self._target_candidates(target):
            target_payload = platforms.get(candidate)
            if not isinstance(target_payload, dict):
                continue
            url = target_payload.get("url")
            if not isinstance(url, str) or not url:
                continue
            if not self._is_supported_gui_artifact_for_target(url, candidate):
                continue
            if candidate != target:
                print(f"Target artifact {target} was not found, using {candidate}.")
            return url

        raise RuntimeError(
            f"release manifest does not contain a supported app artifact for target: {target}"
        )

    def _infer_gui_target_from_asset_name(self, name: str) -> str | None:
        lower = name.lower()
        if lower.endswith(".sig"):
            return None
        if lower.endswith(".appimage"):
            if "aarch64" in lower or "arm64" in lower or "aarch" in lower:
                return "linux-aarch64"
            return "linux-x86_64"
        if lower.endswith(".app.tar.gz"):
            if "aarch64" in lower or "arm64" in lower or "aarch" in lower:
                return "darwin-aarch64"
            return "darwin-x86_64"
        if lower.endswith("-setup.exe") or lower.endswith(".exe"):
            if "arm64" in lower or "aarch64" in lower or "aarch" in lower:
                return "windows-aarch64"
            return "windows-x86_64"
        return None

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

        grouped: dict[str, list[dict[str, str]]] = {}
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
            inferred_target = self._infer_gui_target_from_asset_name(name)
            if inferred_target is None:
                continue
            grouped.setdefault(inferred_target, []).append({"name": name, "url": url})

        for candidate_target in self._target_candidates(target):
            candidates = grouped.get(candidate_target, [])
            if not candidates:
                continue
            if candidate_target != target:
                print(f"Target artifact {target} was not found in release assets, using {candidate_target}.")
            for candidate in candidates:
                if self._is_supported_gui_artifact_for_target(candidate["name"], candidate_target):
                    return candidate["url"]

        raise RuntimeError(f"no supported GUI app artifacts match target {target}")
