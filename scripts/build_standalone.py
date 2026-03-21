#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import zipfile


@dataclass(frozen=True)
class TargetBinary:
    name: str
    entrypoint: Path


def platform_triplet() -> tuple[str, str]:
    os_name = sys.platform
    if os_name.startswith("linux"):
        platform_name = "linux"
    elif os_name == "darwin":
        platform_name = "macos"
    elif os_name in {"win32", "cygwin"}:
        platform_name = "windows"
    else:
        raise RuntimeError(f"Unsupported platform: {os_name}")

    machine = platform.machine().lower()
    arch_aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
        "armv8": "aarch64",
    }
    arch = arch_aliases.get(machine, machine)
    return platform_name, arch


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pyinstaller(target: TargetBinary, build_root: Path, dist_root: Path) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        target.name,
        "--distpath",
        str(dist_root),
        "--workpath",
        str(build_root / "pyi-work" / target.name),
        "--specpath",
        str(build_root / "pyi-spec"),
        "--paths",
        str(Path("src").resolve()),
        "--paths",
        str(Path(".").resolve()),
        str(target.entrypoint),
    ]
    subprocess.run(cmd, check=True)
    exe_name = f"{target.name}.exe" if os.name == "nt" else target.name
    artifact = dist_root / exe_name
    if not artifact.exists():
        raise FileNotFoundError(f"Expected PyInstaller artifact was not produced: {artifact}")
    return artifact


def package_release(
    binaries: list[Path],
    output_dir: Path,
    release_name: str,
    version: str,
    platform_name: str,
    arch: str,
) -> tuple[Path, Path]:
    staging = output_dir / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": version,
        "platform": platform_name,
        "arch": arch,
        "binaries": [path.name for path in binaries],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    for binary in binaries:
        shutil.copy2(binary, staging / binary.name)

    manifest_path = staging / "standalone-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    archive = output_dir / release_name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(staging.iterdir()):
            zf.write(item, arcname=item.name)

    checksum_path = output_dir / f"{release_name}.sha256"
    checksum_path.write_text(f"{sha256_file(archive)}  {archive.name}\n", encoding="utf-8")
    return archive, checksum_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standalone Xenage binaries for GUI-managed services.")
    parser.add_argument("--version", required=True, help="Version string embedded into standalone-manifest.json")
    parser.add_argument(
        "--output-dir",
        default="dist/standalone-release",
        help="Directory where final release assets are written",
    )
    parser.add_argument(
        "--build-dir",
        default="dist/standalone-build",
        help="Directory used for intermediate PyInstaller output",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    build_dir = Path(args.build_dir).resolve()
    pyinstaller_dist = build_dir / "pyinstaller-dist"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    pyinstaller_dist.mkdir(parents=True, exist_ok=True)

    targets = [
        TargetBinary("xenage-control-plane", Path("scripts/standalone/control_plane_entrypoint.py").resolve()),
        TargetBinary("xenage-runtime", Path("scripts/standalone/runtime_entrypoint.py").resolve()),
    ]

    built_binaries = [run_pyinstaller(target, build_dir, pyinstaller_dist) for target in targets]
    platform_name, arch = platform_triplet()
    arch_label = arch
    if arch == "x86_64":
        arch_label = "x86"
    elif arch == "aarch64":
        arch_label = "arm" if platform_name == "linux" else "aarch"
    archive_name = f"{platform_name}_{arch_label}_xenage_standalone_{args.version}.zip"
    archive, checksum = package_release(
        binaries=built_binaries,
        output_dir=output_dir,
        release_name=archive_name,
        version=args.version,
        platform_name=platform_name,
        arch=arch,
    )

    print(f"Built standalone archive: {archive}")
    print(f"Checksum: {checksum}")


if __name__ == "__main__":
    main()
