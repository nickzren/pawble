#!/usr/bin/env python3
"""Validate a Pawble/Codex pet package."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image


COLUMNS = 8
ROWS = 9
CELL_WIDTH = 192
CELL_HEIGHT = 208
ATLAS_WIDTH = COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ROWS * CELL_HEIGHT
ROW_SPECS = [
    ("idle", 0, 6),
    ("running-right", 1, 8),
    ("running-left", 2, 8),
    ("waving", 3, 4),
    ("jumping", 4, 5),
    ("failed", 5, 8),
    ("waiting", 6, 6),
    ("running", 7, 6),
    ("review", 8, 6),
]
ROW_FRAME_COUNTS = {state: frame_count for state, _row, frame_count in ROW_SPECS}
IDLE_SEQUENCE_MAX_BOUNDS_DRIFT_PX = 2
FULL_ROW_MAX_BOUNDS_DRIFT_PX = 2
ROW_CENTER_MAX_DRIFT_PX = 2
FULL_ROW_STABLE_STATES = {"idle", "running-right", "running-left", "waiting", "running", "review"}
BOUNDS_STABILITY_METRICS = ("width", "height", "centerX", "centerY", "bottom")
CENTER_STABILITY_METRICS = ("centerX", "centerY")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Pawble/Codex pet package.")
    parser.add_argument("pack_dir", nargs="?", default="sample-pets/blueberry")
    parser.add_argument(
        "--strict-visual",
        action="store_true",
        help="also fail on row drift/grow-shrink quality issues",
    )
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir).resolve()
    issues = validate_pack(pack_dir, strict_visual=args.strict_visual)

    if issues:
        print(f"pack invalid: {display_path(pack_dir)}")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"pack ready: {display_path(pack_dir)}")
    return 0


def validate_pack(pack_dir: Path, strict_visual: bool = False) -> list[str]:
    issues: list[str] = []

    if not pack_dir.exists():
        return [f"{display_path(pack_dir)}: pet package directory does not exist"]
    if not pack_dir.is_dir():
        return [f"{display_path(pack_dir)}: pet package path is not a directory"]

    profile = load_pet_json(pack_dir / "pet.json", issues)
    if profile is None:
        return issues

    for key in ("id", "displayName", "spritesheetPath"):
        value = profile.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"pet.json: {key} must be a non-empty string")

    spritesheet_path = profile.get("spritesheetPath")
    spritesheet_image: Image.Image | None = None
    if isinstance(spritesheet_path, str):
        spritesheet_image = validate_spritesheet_path(pack_dir, spritesheet_path, issues)
    if strict_visual and spritesheet_image is not None:
        validate_full_row_visual_stability(spritesheet_image, issues)
    pawble_config = validate_pawble_json(pack_dir, issues)
    if strict_visual and spritesheet_image is not None and pawble_config is not None:
        validate_pawble_visual_tuning(pawble_config, spritesheet_image, issues)

    return issues


def load_pet_json(path: Path, issues: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        issues.append("pet.json: missing required Codex pet metadata")
        return None
    if not path.is_file():
        issues.append("pet.json: expected a file")
        return None

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"pet.json: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return None

    if not isinstance(parsed, dict):
        issues.append("pet.json: root value must be an object")
        return None

    return parsed


def validate_spritesheet_path(pack_dir: Path, raw_path: str, issues: list[str]) -> Image.Image | None:
    if raw_path != "spritesheet.webp":
        issues.append("pet.json: spritesheetPath must be spritesheet.webp")

    if os.path.isabs(raw_path):
        issues.append(f"pet.json: spritesheetPath must be relative, got absolute path {raw_path}")
        return None

    if ".." in Path(raw_path).parts:
        issues.append(f"pet.json: spritesheetPath must not contain '..': {raw_path}")
        return None

    spritesheet = (pack_dir / raw_path).resolve()
    if not is_relative_to(spritesheet, pack_dir):
        issues.append(f"pet.json: spritesheetPath escapes the package: {raw_path}")
        return None

    if not spritesheet.exists():
        issues.append(f"{raw_path}: missing spritesheet file")
        return None
    if not spritesheet.is_file():
        issues.append(f"{raw_path}: expected a file")
        return None

    return validate_spritesheet(spritesheet, raw_path, issues)


def validate_spritesheet(path: Path, display_name: str, issues: list[str]) -> Image.Image | None:
    try:
        with Image.open(path) as opened:
            if opened.format != "WEBP":
                issues.append(f"{display_name}: spritesheet must be WebP, got {opened.format or 'unknown'}")
                return None
            image = opened.convert("RGBA")
    except Exception as exc:
        issues.append(f"{display_name}: could not decode spritesheet: {exc}")
        return None

    if image.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        issues.append(
            f"{display_name}: spritesheet must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}, got {image.width}x{image.height}"
        )
        return None

    for state, row, frame_count in ROW_SPECS:
        for column in range(frame_count):
            if cell_is_empty(image, row, column):
                issues.append(f"{display_name}: {state}[{column}] must not be empty")

        for column in range(frame_count, COLUMNS):
            if not cell_is_empty(image, row, column):
                issues.append(f"{display_name}: unused {state}[{column}] cell must be transparent")

    return image


def validate_pawble_json(pack_dir: Path, issues: list[str]) -> dict[str, Any] | None:
    path = pack_dir / "pawble.json"
    if not path.exists():
        return None
    if not path.is_file():
        issues.append("pawble.json: expected a file")
        return None

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"pawble.json: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return None

    if not isinstance(parsed, dict):
        issues.append("pawble.json: root value must be an object")
        return None

    if parsed.get("schemaVersion") != 1:
        issues.append("pawble.json: schemaVersion must be 1")

    idle_sequence = parsed.get("idleFrameSequence")
    if idle_sequence is not None:
        if not isinstance(idle_sequence, list) or not idle_sequence:
            issues.append("pawble.json: idleFrameSequence must be a non-empty array")
        else:
            for index, value in enumerate(idle_sequence):
                if not isinstance(value, int) or value < 0 or value >= ROW_FRAME_COUNTS["idle"]:
                    issues.append(
                        f"pawble.json: idleFrameSequence[{index}] must be an idle frame index between 0 and {ROW_FRAME_COUNTS['idle'] - 1}"
                    )

    movement_source = parsed.get("movementFrameSource")
    if movement_source is not None:
        if movement_source not in ROW_FRAME_COUNTS:
            issues.append("pawble.json: movementFrameSource must be one of " + ", ".join(ROW_FRAME_COUNTS))

    mirror_left = parsed.get("mirrorMovementFrameSourceForLeft")
    if mirror_left is not None and not isinstance(mirror_left, bool):
        issues.append("pawble.json: mirrorMovementFrameSourceForLeft must be a boolean")

    return parsed


def validate_pawble_visual_tuning(config: dict[str, Any], image: Image.Image, issues: list[str]) -> None:
    validate_pawble_idle_tuning(config, image, issues)
    validate_pawble_movement_tuning(config, image, issues)


def validate_pawble_idle_tuning(config: dict[str, Any], image: Image.Image, issues: list[str]) -> None:
    idle_sequence = config.get("idleFrameSequence")
    if not isinstance(idle_sequence, list) or not idle_sequence:
        return
    if any(not isinstance(value, int) or value < 0 or value >= ROW_FRAME_COUNTS["idle"] for value in idle_sequence):
        return

    unique_indices = list(dict.fromkeys(idle_sequence))
    if len(unique_indices) < 2:
        return

    indexed_metrics: list[tuple[int, dict[str, float]]] = []
    for index in unique_indices:
        bbox = cell_alpha_bbox(image, 0, index)
        if bbox is None:
            continue
        indexed_metrics.append((index, bbox_metrics(bbox)))

    drift = first_excessive_bounds_spread(indexed_metrics)
    if drift is None:
        return

    issues.append(
        format_bounds_drift_issue(
            "pawble.json: idleFrameSequence visible bounds drift too much",
            "idle",
            drift,
            IDLE_SEQUENCE_MAX_BOUNDS_DRIFT_PX,
        )
    )


def validate_pawble_movement_tuning(config: dict[str, Any], image: Image.Image, issues: list[str]) -> None:
    movement_source = config.get("movementFrameSource")
    if movement_source not in ROW_FRAME_COUNTS:
        return

    row = next(row for state, row, _frame_count in ROW_SPECS if state == movement_source)
    frame_count = ROW_FRAME_COUNTS[movement_source]
    indexed_metrics: list[tuple[int, dict[str, float]]] = []
    for column in range(frame_count):
        bbox = cell_alpha_bbox(image, row, column)
        if bbox is None:
            continue
        indexed_metrics.append((column, bbox_metrics(bbox)))

    drift = first_excessive_bounds_spread(
        indexed_metrics,
        metrics=BOUNDS_STABILITY_METRICS,
        max_spread=FULL_ROW_MAX_BOUNDS_DRIFT_PX,
    )
    if drift is None:
        return

    issues.append(
        format_bounds_drift_issue(
            f"pawble.json: movementFrameSource {movement_source} visible bounds drift too much",
            movement_source,
            drift,
            FULL_ROW_MAX_BOUNDS_DRIFT_PX,
        )
    )


def validate_full_row_visual_stability(image: Image.Image, issues: list[str]) -> None:
    for state, row, frame_count in ROW_SPECS:
        indexed_metrics: list[tuple[int, dict[str, float]]] = []
        for column in range(frame_count):
            bbox = cell_alpha_bbox(image, row, column)
            if bbox is None:
                continue
            indexed_metrics.append((column, bbox_metrics(bbox)))

        center_drift = first_excessive_bounds_spread(
            indexed_metrics,
            metrics=CENTER_STABILITY_METRICS,
            max_spread=ROW_CENTER_MAX_DRIFT_PX,
        )
        if center_drift is not None:
            issues.append(
                format_bounds_drift_issue(
                    f"spritesheet.webp: {state} row center drift too much",
                    state,
                    center_drift,
                    ROW_CENTER_MAX_DRIFT_PX,
                )
            )

        if state in FULL_ROW_STABLE_STATES:
            bounds_drift = first_excessive_bounds_spread(
                indexed_metrics,
                metrics=BOUNDS_STABILITY_METRICS,
                max_spread=FULL_ROW_MAX_BOUNDS_DRIFT_PX,
            )
            if bounds_drift is None:
                continue

            issues.append(
                format_bounds_drift_issue(
                    f"spritesheet.webp: {state} row visible bounds drift too much",
                    state,
                    bounds_drift,
                    FULL_ROW_MAX_BOUNDS_DRIFT_PX,
                )
            )


def cell_is_empty(image: Image.Image, row: int, column: int) -> bool:
    return cell_alpha_bbox(image, row, column) is None


def cell_alpha_bbox(image: Image.Image, row: int, column: int) -> tuple[int, int, int, int] | None:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    cell = image.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
    alpha = cell.getchannel("A")
    return alpha.getbbox()


def bbox_metrics(bbox: tuple[int, int, int, int]) -> dict[str, float]:
    left, top, right, bottom = bbox
    return {
        "width": right - left,
        "height": bottom - top,
        "centerX": (left + right) / 2,
        "centerY": (top + bottom) / 2,
        "bottom": bottom,
    }


def first_excessive_bounds_spread(
    indexed_metrics: list[tuple[int, dict[str, float]]],
    metrics: tuple[str, ...] = BOUNDS_STABILITY_METRICS,
    max_spread: int = IDLE_SEQUENCE_MAX_BOUNDS_DRIFT_PX,
) -> tuple[str, tuple[int, dict[str, float]], tuple[int, dict[str, float]]] | None:
    if len(indexed_metrics) < 2:
        return None

    for metric in metrics:
        low = min(indexed_metrics, key=lambda item: item[1][metric])
        high = max(indexed_metrics, key=lambda item: item[1][metric])
        if high[1][metric] - low[1][metric] > max_spread:
            return metric, low, high

    return None


def format_bounds_drift_issue(
    prefix: str,
    state: str,
    drift: tuple[str, tuple[int, dict[str, float]], tuple[int, dict[str, float]]],
    max_spread: int,
) -> str:
    metric, low, high = drift
    low_index, low_metrics = low
    high_index, high_metrics = high
    return (
        f"{prefix} for {metric} between {state}[{low_index}] ({format_bbox_metrics(low_metrics)}) "
        f"and {state}[{high_index}] ({format_bbox_metrics(high_metrics)}); "
        f"max allowed spread is {max_spread}px"
    )


def format_bbox_metrics(metrics: dict[str, float]) -> str:
    return (
        f"{metrics['width']:.0f}x{metrics['height']:.0f}, "
        f"center=({metrics['centerX']:.1f},{metrics['centerY']:.1f}), "
        f"bottom={metrics['bottom']:.0f}"
    )


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
