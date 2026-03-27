from __future__ import annotations

from pathlib import Path

from scripts.build_standalone import export_direct_binaries


def test_export_direct_binaries_emits_single_xenage_name(tmp_path: Path) -> None:
    source = tmp_path / "xenage"
    source.write_text("binary", encoding="utf-8")
    output_dir = tmp_path / "release"
    output_dir.mkdir()

    exported = export_direct_binaries(
        binaries=[source],
        output_dir=output_dir,
        version="0.1.0-42",
        platform_name="linux",
        arch="x86_64",
    )

    assert len(exported) == 1
    assert exported[0].name == "linux_x86_xenage_0.1.0-42"
    assert exported[0].read_text(encoding="utf-8") == "binary"
