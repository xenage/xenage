from __future__ import annotations

import argparse
from pathlib import Path
import sys

import msgspec

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from structures import build_release_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Xenage structure release manifest for GUI/runtime.")
    parser.add_argument(
        "--out",
        default="apps/xenage-gui/src/generated/control-plane-release.json",
        help="Where to write the generated release manifest.",
    )
    args = parser.parse_args()

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_release_manifest()
    encoded = msgspec.json.format(msgspec.json.encode(payload), indent=2)
    output_path.write_bytes(encoded + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
