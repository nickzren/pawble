#!/usr/bin/env python3
"""Tests for Pawble app icon generation."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]


class AppIconTests(unittest.TestCase):
    def test_generated_icon_is_pet_only_with_transparent_background(self) -> None:
        output = REPO_ROOT / ".build" / "icon-tests" / "AppIcon.icns"
        iconset = output.with_suffix(".iconset")
        if output.parent.exists():
            shutil.rmtree(output.parent)
        output.parent.mkdir(parents=True)

        subprocess.run(
            [
                "python3",
                "scripts/make_app_icon.py",
                "sample-pets/blueberry/spritesheet.webp",
                str(output),
            ],
            cwd=REPO_ROOT,
            check=True,
        )
        subprocess.run(["iconutil", "-c", "iconset", str(output), "-o", str(iconset)], check=True)

        icon = Image.open(iconset / "icon_512x512@2x.png").convert("RGBA")
        alpha = icon.getchannel("A")
        bbox = alpha.getbbox()

        self.assertIsNotNone(bbox)
        assert bbox is not None
        left, top, right, bottom = bbox
        self.assertEqual(icon.getpixel((0, 0))[3], 0)
        self.assertEqual(icon.getpixel((icon.width - 1, 0))[3], 0)
        self.assertEqual(icon.getpixel((0, icon.height - 1))[3], 0)
        self.assertEqual(icon.getpixel((icon.width - 1, icon.height - 1))[3], 0)

        fill_ratio = max((right - left) / icon.width, (bottom - top) / icon.height)
        self.assertGreaterEqual(fill_ratio, 0.86)
        self.assertLessEqual(fill_ratio, 0.96)


if __name__ == "__main__":
    unittest.main(verbosity=2)
