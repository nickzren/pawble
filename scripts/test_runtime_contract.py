#!/usr/bin/env python3
"""Runtime contract tests for Pawble's Swift pack loader."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PACK = REPO_ROOT / "sample-pets" / "blueberry"
SWIFT_FLAGS = [
    "--disable-sandbox",
    "--scratch-path",
    ".build",
    "--cache-path",
    ".build/swiftpm-cache",
    "--config-path",
    ".build/swiftpm-config",
    "--security-path",
    ".build/swiftpm-security",
    "--manifest-cache",
    "local",
]


class RuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("PAWBLE_SKIP_SWIFT_BUILD") == "1":
            return
        env = swift_env()
        subprocess.run(["swift", "build", *SWIFT_FLAGS], cwd=REPO_ROOT, env=env, check=True)

    def test_rejects_noncanonical_spritesheet_path(self) -> None:
        with copied_sample_pack() as pack_dir:
            shutil.copy2(pack_dir / "spritesheet.webp", pack_dir / "alt.webp")
            profile = read_pet_json(pack_dir)
            profile["spritesheetPath"] = "alt.webp"
            write_pet_json(pack_dir, profile)

            result = run_pawble(pack_dir)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid Codex pet package", result.stderr)
        self.assertIn("pet.json: spritesheetPath must be spritesheet.webp", result.stderr)

    def test_rejects_empty_display_name(self) -> None:
        with copied_sample_pack() as pack_dir:
            profile = read_pet_json(pack_dir)
            profile["displayName"] = ""
            write_pet_json(pack_dir, profile)

            result = run_pawble(pack_dir)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid Codex pet package", result.stderr)
        self.assertIn("pet.json: displayName must be a non-empty string", result.stderr)


class copied_sample_pack:
    def __enter__(self) -> Path:
        build_dir = REPO_ROOT / ".build" / "runtime-contract-tests"
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


def run_pawble(pack_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(REPO_ROOT / ".build" / "debug" / "Pawble"), "--pack", str(pack_dir)],
        cwd=REPO_ROOT,
        env=swift_env(),
        text=True,
        capture_output=True,
        timeout=5,
    )


def swift_env() -> dict[str, str]:
    env = os.environ.copy()
    env["CLANG_MODULE_CACHE_PATH"] = str(REPO_ROOT / ".build" / "clang-module-cache")
    return env


if __name__ == "__main__":
    unittest.main(verbosity=2)
