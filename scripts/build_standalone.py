#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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


def normalize_labels(platform_name: str, arch: str) -> tuple[str, str]:
    if platform_name == "windows":
        os_label = "win"
    elif platform_name == "macos":
        os_label = "mac"
    else:
        os_label = "linux"

    arch_label = arch
    if arch == "x86_64":
        arch_label = "x86"
    elif arch == "aarch64":
        arch_label = "aarch"
    return os_label, arch_label


def export_direct_binaries(
    binaries: list[Path],
    output_dir: Path,
    version: str,
    platform_name: str,
    arch: str,
) -> list[Path]:
    os_label, arch_label = normalize_labels(platform_name, arch)
    exported: list[Path] = []

    for binary in binaries:
        ext = binary.suffix
        target_name = f"{os_label}_{arch_label}_xenage_{version}{ext}"
        target_path = output_dir / target_name
        shutil.copy2(binary, target_path)
        exported.append(target_path)
    return exported


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
        TargetBinary("xenage", Path("scripts/standalone/xenage_entrypoint.py").resolve()),
    ]

    built_binaries = [run_pyinstaller(target, build_dir, pyinstaller_dist) for target in targets]
    platform_name, arch = platform_triplet()
    outputs = export_direct_binaries(
        binaries=built_binaries,
        output_dir=output_dir,
        version=args.version,
        platform_name=platform_name,
        arch=arch,
    )
    for output in outputs:
        print(f"Built standalone artifact: {output}")


if __name__ == "__main__":
    main()
