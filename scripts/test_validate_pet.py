#!/usr/bin/env python3
"""Focused tests for the Pawble/Codex pet package validator."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PACK = REPO_ROOT / "sample-pets" / "blueberry"

spec = importlib.util.spec_from_file_location("validate_pet", REPO_ROOT / "scripts" / "validate_pet.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load validate_pet.py")
validate_pet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_pet)


class ValidatorTests(unittest.TestCase):
    def test_sample_pack_is_valid(self) -> None:
        self.assertEqual(validate_pet.validate_pack(SAMPLE_PACK), [])

    def test_rejects_missing_pet_json(self) -> None:
        with copied_sample_pack() as pack_dir:
            (pack_dir / "pet.json").unlink()

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "pet.json: missing required Codex pet metadata")

    def test_rejects_wrong_spritesheet_path(self) -> None:
        with copied_sample_pack() as pack_dir:
            profile = read_pet_json(pack_dir)
            profile["spritesheetPath"] = "sheet.webp"
            write_pet_json(pack_dir, profile)

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "pet.json: spritesheetPath must be spritesheet.webp")
        self.assertContains(issues, "sheet.webp: missing spritesheet file")

    def test_rejects_path_traversal(self) -> None:
        with copied_sample_pack() as pack_dir:
            profile = read_pet_json(pack_dir)
            profile["spritesheetPath"] = "../spritesheet.webp"
            write_pet_json(pack_dir, profile)

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "pet.json: spritesheetPath must be spritesheet.webp")
        self.assertContains(issues, "pet.json: spritesheetPath must not contain '..': ../spritesheet.webp")

    def test_rejects_wrong_dimensions(self) -> None:
        with copied_sample_pack() as pack_dir:
            Image.new("RGBA", (192, 208), (0, 0, 0, 0)).save(pack_dir / "spritesheet.webp")

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "spritesheet.webp: spritesheet must be 1536x1872, got 192x208")

    def test_rejects_non_webp_spritesheet(self) -> None:
        with copied_sample_pack() as pack_dir:
            Image.new("RGBA", (1536, 1872), (255, 0, 0, 255)).save(pack_dir / "spritesheet.webp", format="PNG")

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "spritesheet.webp: spritesheet must be WebP, got PNG")

    def test_rejects_empty_required_cell(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            sheet.paste((0, 0, 0, 0), (0, 0, 192, 208))
            sheet.save(pack_dir / "spritesheet.webp")

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "spritesheet.webp: idle[0] must not be empty")

    def test_rejects_nontransparent_unused_cell(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            sheet.paste((255, 0, 0, 255), (6 * 192, 0, 7 * 192, 208))
            sheet.save(pack_dir / "spritesheet.webp")

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(issues, "spritesheet.webp: unused idle[6] cell must be transparent")

    def test_rejects_invalid_pawble_config(self) -> None:
        with copied_sample_pack() as pack_dir:
            (pack_dir / "pawble.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idleFrameSequence": [0, 9],
                        "movementFrameSource": "not-a-state",
                        "mirrorMovementFrameSourceForLeft": "yes",
                    }
                ),
                encoding="utf-8",
            )

            issues = validate_pet.validate_pack(pack_dir)

        self.assertContains(
            issues,
            "pawble.json: idleFrameSequence[1] must be an idle frame index between 0 and 5",
        )
        self.assertContains(
            issues,
            "pawble.json: movementFrameSource must be one of idle, running-right, running-left, waving, jumping, failed, waiting, running, review",
        )
        self.assertContains(issues, "pawble.json: mirrorMovementFrameSourceForLeft must be a boolean")

    def test_strict_visual_rejects_idle_sequence_size_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            paint_test_box(sheet, row=0, column=0, center_x=96, width=40)
            paint_test_box(sheet, row=0, column=3, center_x=96, width=48)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)
            (pack_dir / "pawble.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idleFrameSequence": [0, 0, 0, 0, 0, 3, 0],
                        "movementFrameSource": "running",
                        "mirrorMovementFrameSourceForLeft": True,
                    }
                ),
                encoding="utf-8",
            )

            issues = validate_pet.validate_pack(pack_dir, strict_visual=True)

        self.assertAnyIssueContains(issues, "idleFrameSequence visible bounds drift too much")
        self.assertAnyIssueContains(issues, "for width")
        self.assertAnyIssueContains(issues, "idle[0]")
        self.assertAnyIssueContains(issues, "idle[3]")

    def test_strict_visual_rejects_idle_sequence_total_spread_even_when_baseline_is_middle(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            paint_test_box(sheet, row=0, column=0, center_x=90)
            paint_test_box(sheet, row=0, column=1, center_x=92)
            paint_test_box(sheet, row=0, column=2, center_x=88)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)
            (pack_dir / "pawble.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idleFrameSequence": [0, 1, 2],
                        "movementFrameSource": "running",
                        "mirrorMovementFrameSourceForLeft": True,
                    }
                ),
                encoding="utf-8",
            )

            issues = validate_pet.validate_pack(pack_dir, strict_visual=True)

        self.assertAnyIssueContains(issues, "idleFrameSequence visible bounds drift too much")
        self.assertAnyIssueContains(issues, "for centerX")
        self.assertAnyIssueContains(issues, "idle[1]")
        self.assertAnyIssueContains(issues, "idle[2]")

    def test_strict_visual_rejects_full_idle_row_drift_even_when_pawble_sequence_skips_it(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(6):
                paint_test_box(sheet, row=0, column=column, center_x=96, width=40)
            paint_test_box(sheet, row=0, column=1, center_x=96, width=48)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)
            (pack_dir / "pawble.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idleFrameSequence": [2, 2, 2],
                        "movementFrameSource": "running",
                        "mirrorMovementFrameSourceForLeft": True,
                    }
                ),
                encoding="utf-8",
            )

            issues = validate_pet.validate_pack(pack_dir, strict_visual=True)

        self.assertAnyIssueContains(issues, "idle row visible bounds drift too much")
        self.assertAnyIssueContains(issues, "for width")
        self.assertAnyIssueContains(issues, "idle[0]")
        self.assertAnyIssueContains(issues, "idle[1]")

    def test_strict_visual_rejects_movement_row_size_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(8):
                paint_test_box(sheet, row=1, column=column, center_x=96, width=40, height=40)
            paint_test_box(sheet, row=1, column=4, center_x=96, width=40, height=54)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            issues = validate_pet.validate_pack(pack_dir, strict_visual=True)

        self.assertAnyIssueContains(issues, "running-right row visible bounds drift too much")
        self.assertAnyIssueContains(issues, "for height")
        self.assertAnyIssueContains(issues, "running-right[0]")
        self.assertAnyIssueContains(issues, "running-right[4]")

    def test_default_validation_allows_visual_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(6):
                paint_test_box(sheet, row=0, column=column, center_x=96, width=40, height=40)
            paint_test_box(sheet, row=0, column=4, center_x=96, width=40, height=64)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            issues = validate_pet.validate_pack(pack_dir)

        self.assertEqual(issues, [])

    def test_stabilizer_repairs_stationary_row_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(6):
                paint_test_box(sheet, row=0, column=column, center_x=96, width=40, height=40)
            paint_test_box(sheet, row=0, column=3, center_x=96, width=40, height=52)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            issues_before = validate_pet.validate_pack(pack_dir, strict_visual=True)
            self.assertAnyIssueContains(issues_before, "idle row visible bounds drift too much")

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "stabilize_spritesheet.py"), str(pack_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(validate_pet.validate_pack(pack_dir, strict_visual=True), [])

    def test_stabilizer_repairs_configured_movement_row_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            (pack_dir / "pawble.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "movementFrameSource": "running",
                        "mirrorMovementFrameSourceForLeft": True,
                    }
                ),
                encoding="utf-8",
            )
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(6):
                paint_test_box(sheet, row=7, column=column, center_x=96, width=40, height=40)
            paint_test_box(sheet, row=7, column=4, center_x=96, width=40, height=58)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            issues_before = validate_pet.validate_pack(pack_dir, strict_visual=True)
            self.assertAnyIssueContains(issues_before, "movementFrameSource running visible bounds drift too much")

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "stabilize_spritesheet.py"), str(pack_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(validate_pet.validate_pack(pack_dir, strict_visual=True), [])

    def test_stabilizer_repairs_directional_running_row_drift(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            for column in range(8):
                paint_test_box(sheet, row=1, column=column, center_x=96, width=40, height=40)
            paint_test_box(sheet, row=1, column=5, center_x=96, width=40, height=64)
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "stabilize_spritesheet.py"), str(pack_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            repaired = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            heights = [
                cell_bbox_height(repaired, row=1, column=column)
                for column in range(8)
            ]
            self.assertEqual(max(heights) - min(heights), 0)

    def test_stabilizer_removes_cyan_key_fringe(self) -> None:
        with copied_sample_pack() as pack_dir:
            sheet = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            sheet.putpixel((20, 20), (0, 255, 255, 255))
            sheet.putpixel((21, 20), (0, 170, 170, 3))
            sheet.save(pack_dir / "spritesheet.webp", lossless=True, quality=100)

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "stabilize_spritesheet.py"), str(pack_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            repaired = Image.open(pack_dir / "spritesheet.webp").convert("RGBA")
            self.assertEqual(repaired.getpixel((20, 20))[3], 0)
            self.assertEqual(repaired.getpixel((21, 20))[3], 0)

    def test_ensure_pawble_config_creates_default_movement_config(self) -> None:
        with copied_sample_pack() as pack_dir:
            (pack_dir / "pawble.json").unlink()

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "ensure_pawble_config.py"), str(pack_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            config = json.loads((pack_dir / "pawble.json").read_text(encoding="utf-8"))
            self.assertEqual(config["movementFrameSource"], "running")
            self.assertIs(config["mirrorMovementFrameSourceForLeft"], True)

    def assertContains(self, issues: list[str], expected: str) -> None:
        self.assertIn(expected, issues, f"Expected issue not found.\nExpected: {expected}\nActual: {issues}")

    def assertAnyIssueContains(self, issues: list[str], expected: str) -> None:
        self.assertTrue(
            any(expected in issue for issue in issues),
            f"Expected issue fragment not found.\nExpected fragment: {expected}\nActual: {issues}",
        )


class copied_sample_pack:
    def __enter__(self) -> Path:
        build_dir = REPO_ROOT / ".build" / "validator-tests"
        build_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(prefix="pack-", dir=build_dir)
        self.pack_dir = Path(self.temp_dir.name) / "blueberry"
        shutil.copytree(SAMPLE_PACK, self.pack_dir)
        return self.pack_dir

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.temp_dir.cleanup()


def read_pet_json(pack_dir: Path) -> dict:
    return json.loads((pack_dir / "pet.json").read_text(encoding="utf-8"))


def write_pet_json(pack_dir: Path, profile: dict) -> None:
    (pack_dir / "pet.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")


def paint_test_box(
    sheet: Image.Image,
    row: int,
    column: int,
    center_x: int,
    width: int = 40,
    height: int = 40,
) -> None:
    cell_left = column * 192
    cell_top = row * 208
    sheet.paste((0, 0, 0, 0), (cell_left, cell_top, cell_left + 192, cell_top + 208))
    left = cell_left + center_x - width // 2
    top = cell_top + 80
    sheet.paste((80, 80, 80, 255), (left, top, left + width, top + height))


def cell_bbox_height(sheet: Image.Image, row: int, column: int) -> int:
    left = column * 192
    top = row * 208
    bbox = sheet.crop((left, top, left + 192, top + 208)).getchannel("A").getbbox()
    if bbox is None:
        return 0
    return bbox[3] - bbox[1]


if __name__ == "__main__":
    unittest.main(verbosity=2)
