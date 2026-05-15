#!/usr/bin/env python3
"""Append Pawble extracted-frame quality rules to hatch-pet row prompts."""

from __future__ import annotations

import sys
from pathlib import Path


STRICT_ROWS = {"idle", "running-right", "running-left", "waiting", "running", "review"}
STRICT_STARTS = (
    "Pawble source-quality requirement:",
    "Pawble extracted-frame quality requirement:",
)
STRICT_NOTE = """

Pawble extracted-frame quality requirement:
- Raw generated row images do not need to match the final atlas dimensions. They may be larger or differently shaped if frame extraction can recover the requested poses cleanly.
- Source row geometry is guidance, not the pack contract. Use the layout guide for frame count, spacing, centering, and padding; judge acceptance on the extracted 192x208 frames and final 1536x1872 WebP atlas.
- Aim to pass Pawble structural validation without relying on `make stabilize-pet`. Default validation checks package structure and loadability; strict visual QA is optional for showcase pets.
- Generate this as a locked sprite row, not as separate new drawings per frame.
- Keep the pet's body scale, head size, torso size, center, feet baseline, outline thickness, and visible body bounds consistent across every extracted frame in this row.
- Width, height, center, top of head, torso width, and bottom baseline should stay within 2 pixels across the extracted frames.
- Animate through limb, paw, tail, eye, head, or tiny expression pixel changes only. Do not resize the pet, raise/lower the whole body, stretch the torso, shrink the head, or change the body silhouette envelope between frames.
- For running rows, use a compact treadmill-style leg cycle inside the same body envelope. Do not use stride poses that make the full body wider, taller, crouched, or stretched.
- Use the same full-body sprite size, anchor point, and padding in every frame slot.
- Use one flat chroma-key background only; no cyan/blue fringe, antialias haze, shadows, gradients, or semi-transparent background pixels around the pet.
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: harden_hatch_prompts.py <hatch-pet-run-dir>", file=sys.stderr)
        return 2

    run_dir = Path(sys.argv[1]).resolve()
    prompt_dir = run_dir / "prompts" / "rows"
    if not prompt_dir.is_dir():
        print(f"missing row prompt directory: {prompt_dir}", file=sys.stderr)
        return 1

    changed = []
    for row in sorted(STRICT_ROWS):
        path = prompt_dir / f"{row}.md"
        if not path.exists():
            print(f"missing row prompt: {path}", file=sys.stderr)
            return 1

        text = path.read_text(encoding="utf-8")
        for start in STRICT_STARTS:
            if start in text:
                text = text.split(start, 1)[0].rstrip()
                break
        path.write_text(text.rstrip() + STRICT_NOTE, encoding="utf-8")
        changed.append(row)

    if changed:
        print("hardened row prompts: " + ", ".join(changed))
    else:
        print("row prompts already hardened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
