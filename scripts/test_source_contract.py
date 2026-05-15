#!/usr/bin/env python3
"""Source-level guardrails for Pawble AppKit behavior."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_SWIFT = REPO_ROOT / "Sources" / "Pawble" / "main.swift"


class SourceContractTests(unittest.TestCase):
    def test_pet_panel_joins_all_spaces(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")
        match = re.search(r"panel\.collectionBehavior\s*=\s*\[(?P<flags>[^\]]+)\]", source)

        self.assertIsNotNone(match, "Expected panel.collectionBehavior assignment")
        assert match is not None
        self.assertIn(".canJoinAllSpaces", match.group("flags"))

    def test_autonomous_behavior_uses_living_states(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")
        match = re.search(r"private func behaviorChoices\(\) -> \[CodexPetState\] \{(?P<body>.*?)\n    \}", source, re.S)

        self.assertIsNotNone(match, "Expected behaviorChoices implementation")
        assert match is not None
        body = match.group("body")
        for state in (".waiting", ".review", ".waving", ".jumping"):
            self.assertIn(state, body)
        self.assertNotIn(".failed", body)

    def test_pet_reacts_to_cursor_and_clicks(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")

        self.assertIn("cursorReactionIfAllowed()", source)
        self.assertIn("private func petDidClick()", source)
        self.assertIn("clickHandler?()", source)

    def test_cursor_reactions_share_cooldown_gate(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")
        choose_match = re.search(r"private func chooseNextBehavior\(\) \{(?P<body>.*?)\n    \}", source, re.S)
        gate_match = re.search(r"private func cursorReactionIfAllowed\(\) -> CodexPetState\? \{(?P<body>.*?)\n    \}", source, re.S)

        self.assertIsNotNone(choose_match, "Expected chooseNextBehavior implementation")
        self.assertIsNotNone(gate_match, "Expected cursorReactionIfAllowed implementation")
        assert choose_match is not None
        assert gate_match is not None

        self.assertIn("cursorReactionIfAllowed()", choose_match.group("body"))
        self.assertNotIn("cursorReactionState()", choose_match.group("body"))
        self.assertIn("lastCursorReaction = Date()", gate_match.group("body"))

    def test_drag_does_not_freeze_animation(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")
        drag_match = re.search(r"imageView\.dragDidBegin = \{ \[weak self\] in(?P<body>.*?)\n        \}", source, re.S)

        self.assertIsNotNone(drag_match, "Expected dragDidBegin handler")
        assert drag_match is not None
        self.assertIn("dragging = true", drag_match.group("body"))
        self.assertNotIn("paused = true", drag_match.group("body"))

    def test_cursor_distance_uses_hypot(self) -> None:
        source = MAIN_SWIFT.read_text(encoding="utf-8")

        self.assertIn("let distance = hypot(deltaX, deltaY)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
