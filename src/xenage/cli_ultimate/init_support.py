from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


class InitEnvironment:
    def run_cli(self, args: list[str]) -> str:
        cmd = [self.resolve_cli_executable(), *args]
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def start_background_process(self, args: list[str], log_path: Path, pid_path: Path) -> None:
        cmd = [self.resolve_cli_executable(), *args]
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if pid_path.exists():
            previous_pid = pid_path.read_text(encoding="utf-8").strip()
            if previous_pid.isdigit() and self.is_process_alive(int(previous_pid)):
                raise RuntimeError(f"existing node process is running with pid {previous_pid}: {pid_path}")

        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        pid_path.write_text(f"{process.pid}\n", encoding="utf-8")

    def wait_for_heartbeat(self, url: str, timeout_seconds: int) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1.5) as response:
                    if response.status == 200:
                        return
            except urllib.error.URLError:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"node did not become healthy in time: {url}")

    def resolve_cli_executable(self) -> str:
        current = Path(os.path.realpath(os.sys.argv[0]))
        current_name = current.name.lower()
        if current.exists() and current_name.startswith("xenage"):
            return str(current)

        resolved = shutil.which("xenage")
        if resolved:
            return resolved
        raise RuntimeError("xenage executable was not found in PATH")

    def release_target(self) -> str:
        os_name = os.sys.platform
        if os_name.startswith("linux"):
            normalized_os = "linux"
        elif os_name == "darwin":
            normalized_os = "darwin"
        elif os_name in {"win32", "cygwin"}:
            normalized_os = "windows"
        else:
            raise RuntimeError(f"unsupported operating system: {os_name}")

        machine = platform.machine().lower()
        aliases = {
            "x64": "x86_64",
            "amd64": "x86_64",
            "arm64": "aarch64",
            "armv8": "aarch64",
        }
        normalized_arch = aliases.get(machine, machine)
        if normalized_arch not in {"x86_64", "aarch64"}:
            raise RuntimeError(f"unsupported architecture: {machine}")

        return f"{normalized_os}-{normalized_arch}"

    def resolve_asset_url(self, manifest_url: str, target: str) -> str:
        payload = self.fetch_json(manifest_url)
        platforms = payload.get("platforms")
        if not isinstance(platforms, dict):
            raise RuntimeError(f"invalid release manifest at {manifest_url}: missing platforms")
        target_payload = platforms.get(target)
        if not isinstance(target_payload, dict):
            raise RuntimeError(f"release manifest does not contain target: {target}")
        url = target_payload.get("url")
        if not isinstance(url, str) or not url:
            raise RuntimeError(f"release manifest target {target} has no url")
        return url

    def fetch_json(self, url: str) -> dict[str, object]:
        with urllib.request.urlopen(url, timeout=15) as response:
            content = response.read().decode("utf-8")
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError(f"json payload from {url} is not an object")
        return payload

    def download_to_path(self, url: str, destination: Path) -> None:
        encoded_url = self._encode_url(url)
        with urllib.request.urlopen(encoded_url, timeout=60) as response:
            data = response.read()
        destination.write_bytes(data)

    def extract_gui_artifact(self, archive_path: Path, install_root: Path) -> Path:
        lower_name = archive_path.name.lower()
        if lower_name.endswith(".appimage"):
            target = install_root / "Xenage GUI.AppImage"
            shutil.copy2(archive_path, target)
            mode = os.stat(target).st_mode
            os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self._create_desktop_shortcut_if_present(target)
            return target
        if lower_name.endswith(".app.tar.gz"):
            target_dir = install_root / "macos"
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(target_dir)
            app_bundle = self._find_macos_app_bundle(target_dir)
            if app_bundle is not None:
                self._clear_macos_quarantine(app_bundle)
                self._create_desktop_shortcut_if_present(app_bundle)
                return app_bundle
            return target_dir
        if lower_name.endswith(".exe"):
            target = install_root / archive_path.name
            shutil.copy2(archive_path, target)
            return target
        if lower_name.endswith(".zip"):
            target_dir = install_root / "windows"
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(target_dir)
            return target_dir
        target = install_root / archive_path.name
        shutil.copy2(archive_path, target)
        return target

    def is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _encode_url(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        encoded_path = urllib.parse.quote(parsed.path)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))

    def _desktop_dir_if_present(self) -> Path | None:
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            return desktop
        return None

    def _create_desktop_shortcut_if_present(self, target: Path) -> Path | None:
        desktop = self._desktop_dir_if_present()
        if desktop is None:
            return None

        shortcut = desktop / target.name
        try:
            if shortcut.is_symlink() or shortcut.is_file():
                shortcut.unlink()
            elif shortcut.exists():
                return None
            shortcut.symlink_to(target)
            return shortcut
        except OSError:
            return None

    def _find_macos_app_bundle(self, root: Path) -> Path | None:
        bundles = sorted(root.rglob("*.app"))
        if not bundles:
            return None
        return bundles[0]

    def _clear_macos_quarantine(self, app_path: Path) -> None:
        if os.sys.platform != "darwin":
            return
        xattr_path = shutil.which("xattr")
        if not xattr_path:
            return
        subprocess.run(
            [xattr_path, "-r", "-d", "com.apple.quarantine", str(app_path)],
            check=False,
            capture_output=True,
            text=True,
        )
