"""Tests for rewrite-agent revise_hints on save."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REVIEW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REVIEW))

from revise_hints import revise_hints_from_comments  # noqa: E402


class TestReviseHints(unittest.TestCase):
    def test_no_voice_marks_returns_none(self) -> None:
        self.assertIsNone(
            revise_hints_from_comments(
                [{"type": "comment", "id": "c1", "body": "Fix intro"}]
            )
        )

    def test_voice_marks_include_literal_instruction(self) -> None:
        hints = revise_hints_from_comments(
            [
                {"type": "comment", "id": "c2", "via": "voice", "body": "Cut the fluff"},
                {"type": "comment", "id": "c1", "body": "typed"},
            ]
        )
        self.assertIsNotNone(hints)
        assert hints is not None
        self.assertIn("spoken", hints["voice_marks_literal"].lower())
        self.assertEqual(hints["voice_mark_ids"], ["c2"])
        self.assertEqual(hints["voice_mark_count"], 1)


if __name__ == "__main__":
    unittest.main()
