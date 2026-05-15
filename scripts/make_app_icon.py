#!/usr/bin/env python3
"""Create a macOS .icns icon from the first pet spritesheet frame."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ICON_PIXEL_SIZES = [32, 64, 128, 256, 512, 1024]
CELL_SIZE = (192, 208)
ICON_FILL_RATIO = 0.92


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: make_app_icon.py <spritesheet.webp> <output.icns>", file=sys.stderr)
        return 2

    spritesheet = Path(sys.argv[1])
    output = Path(sys.argv[2])

    base = Image.open(spritesheet).convert("RGBA").crop((0, 0, *CELL_SIZE))
    bbox = base.getchannel("A").getbbox()
    if bbox is not None:
        base = base.crop(bbox)

    output.parent.mkdir(parents=True, exist_ok=True)
    icons = [make_icon_image(base, size) for size in ICON_PIXEL_SIZES]
    icons[-1].save(output, format="ICNS", append_images=icons[:-1])
    return 0


def make_icon_image(base: Image.Image, canvas_size: int) -> Image.Image:
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    art_size = int(canvas_size * ICON_FILL_RATIO)
    ratio = min(art_size / base.width, art_size / base.height)
    resized_size = (max(1, int(base.width * ratio)), max(1, int(base.height * ratio)))
    art = base.resize(resized_size, Image.Resampling.NEAREST)
    origin = ((canvas_size - art.width) // 2, (canvas_size - art.height) // 2)
    canvas.alpha_composite(art, origin)
    return canvas


if __name__ == "__main__":
    raise SystemExit(main())
