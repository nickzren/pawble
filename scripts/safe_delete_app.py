#!/usr/bin/env python3
"""Safely delete a generated .app bundle inside an expected directory."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely delete a generated .app bundle.")
    parser.add_argument("--base", required=True, help="directory the target must stay inside")
    parser.add_argument("--target", required=True, help=".app bundle path to delete if present")
    args = parser.parse_args()

    target = Path(args.target)
    if not args.target.strip() or target.suffix != ".app":
        return refuse(args.target)

    base = Path(args.base).resolve()
    resolved_target = target.resolve()

    if base.parent == base:
        return refuse(args.target)

    try:
        resolved_target.relative_to(base)
    except ValueError:
        return refuse(args.target)

    if not resolved_target.exists():
        return 0
    if not resolved_target.is_dir():
        return refuse(args.target)

    shutil.rmtree(resolved_target)
    return 0


def refuse(path: str) -> int:
    print(f"refusing to delete unexpected path: {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
