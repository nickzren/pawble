#!/usr/bin/env python3
"""Create a default Pawble runtime config for an imported Codex pet."""

from __future__ import annotations

import json
import sys
from pathlib import Path


DEFAULT_CONFIG = {
    "schemaVersion": 1,
    "movementFrameSource": "running",
    "mirrorMovementFrameSourceForLeft": True,
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ensure_pawble_config.py <pet-package-dir>", file=sys.stderr)
        return 2

    pack_dir = Path(sys.argv[1]).resolve()
    config_path = pack_dir / "pawble.json"
    if config_path.exists():
        print(f"preserved {display_path(config_path)}")
        return 0

    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    print(f"created {display_path(config_path)}")
    return 0


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
