#!/usr/bin/env python3
"""Normalize stationary Codex pet rows so the pet does not grow or shrink."""

from __future__ import annotations

import sys
import json
from pathlib import Path

from PIL import Image


COLUMNS = 8
CELL_WIDTH = 192
CELL_HEIGHT = 208
STATIONARY_ROWS = {
    "idle": (0, 6),
    "waiting": (6, 6),
    "review": (8, 6),
}
MOVEMENT_ROWS = {
    "running-right": (1, 8),
    "running-left": (2, 8),
    "running": (7, 6),
}
ROW_SPECS = {
    "idle": (0, 6),
    "running-right": (1, 8),
    "running-left": (2, 8),
    "waving": (3, 4),
    "jumping": (4, 5),
    "failed": (5, 8),
    "waiting": (6, 6),
    "running": (7, 6),
    "review": (8, 6),
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: stabilize_spritesheet.py <pet-package-dir>", file=sys.stderr)
        return 2

    pack_dir = Path(sys.argv[1]).resolve()
    spritesheet_path = pack_dir / "spritesheet.webp"
    if not spritesheet_path.exists():
        print(f"missing {spritesheet_path}", file=sys.stderr)
        return 1

    image = Image.open(spritesheet_path).convert("RGBA")
    states_to_stabilize = {**STATIONARY_ROWS, **MOVEMENT_ROWS}
    movement_state = movement_frame_source(pack_dir)
    if movement_state in ROW_SPECS:
        states_to_stabilize[movement_state] = ROW_SPECS[movement_state]

    clean_chroma_fringe(image)
    for state, (row, frame_count) in states_to_stabilize.items():
        stabilize_row(image, state, row, frame_count)

    image.save(spritesheet_path, format="WEBP", lossless=True, quality=100, method=6)
    print(f"stabilized rows: {', '.join(states_to_stabilize)}")
    print(f"cleaned chroma-key fringe: {display_path(spritesheet_path)}")
    return 0


def movement_frame_source(pack_dir: Path) -> str | None:
    config_path = pack_dir / "pawble.json"
    if not config_path.exists():
        return None
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    source = parsed.get("movementFrameSource")
    return source if isinstance(source, str) else None


def stabilize_row(image: Image.Image, state: str, row: int, frame_count: int) -> None:
    metrics = []
    cells = []
    for column in range(frame_count):
        cell = crop_cell(image, row, column)
        bbox = cell.getchannel("A").getbbox()
        if bbox is None:
            raise SystemExit(f"{state}[{column}] is empty")
        cells.append((column, cell, bbox))
        metrics.append((column, bbox_metrics(bbox)))

    reference_column, reference_metrics = choose_reference(metrics)
    target_width = int(reference_metrics["width"])
    target_height = int(reference_metrics["height"])
    target_left = int(reference_metrics["left"])
    target_top = int(reference_metrics["top"])

    for column, cell, bbox in cells:
        sprite = cell.crop(bbox)
        if sprite.size != (target_width, target_height):
            sprite = sprite.resize((target_width, target_height), Image.Resampling.NEAREST)

        normalized = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        normalized.alpha_composite(sprite, (target_left, target_top))
        paste_cell(image, row, column, normalized)

    print(f"{state}: normalized to {target_width}x{target_height} from frame {reference_column}")


def clean_chroma_fringe(image: Image.Image) -> None:
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            if is_cyan_key_artifact(red, green, blue, alpha):
                pixels[x, y] = (red, green, blue, 0)


def is_cyan_key_artifact(red: int, green: int, blue: int, alpha: int) -> bool:
    return red < 100 and green > 140 and blue > 140 and abs(green - blue) < 80 and ((green + blue) / 2 - red) > 60


def choose_reference(indexed_metrics: list[tuple[int, dict[str, float]]]) -> tuple[int, dict[str, float]]:
    widths = sorted(metric["width"] for _index, metric in indexed_metrics)
    heights = sorted(metric["height"] for _index, metric in indexed_metrics)
    center_xs = sorted(metric["centerX"] for _index, metric in indexed_metrics)
    bottoms = sorted(metric["bottom"] for _index, metric in indexed_metrics)
    target = {
        "width": median(widths),
        "height": median(heights),
        "centerX": median(center_xs),
        "bottom": median(bottoms),
    }

    def score(item: tuple[int, dict[str, float]]) -> tuple[float, int]:
        index, metric = item
        delta = sum(abs(metric[key] - target[key]) for key in target)
        return delta, index

    return min(indexed_metrics, key=score)


def median(values: list[float]) -> float:
    midpoint = len(values) // 2
    if len(values) % 2 == 1:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / 2


def bbox_metrics(bbox: tuple[int, int, int, int]) -> dict[str, float]:
    left, top, right, bottom = bbox
    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
        "centerX": (left + right) / 2,
        "bottom": bottom,
    }


def crop_cell(image: Image.Image, row: int, column: int) -> Image.Image:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    return image.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))


def paste_cell(image: Image.Image, row: int, column: int, cell: Image.Image) -> None:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    image.paste(cell, (left, top))


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
