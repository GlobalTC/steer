"""Voice proposal re-anchoring after an earlier accept."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from voice_resolve import reanchor_proposal_dicts  # noqa: E402


SAMPLE = """# Title

First line with crap ton of detail here.

Second line mentions two uninterrupted hours of focus.
"""


class TestReanchorVoice(unittest.TestCase):
    def test_second_proposal_reanchors_after_first_replace(self) -> None:
        proposals = [
            {
                "kind": "replace",
                "body": "huge number",
                "anchor": {"start": 20, "end": 28, "text": "crap ton"},
                "excerpt": "crap ton",
            },
            {
                "kind": "comment",
                "body": "nice",
                "anchor": {"start": 60, "end": 82, "text": "two uninterrupted hours"},
                "excerpt": "two uninterrupted hours",
            },
        ]
        md = SAMPLE
        first = reanchor_proposal_dicts(md, [proposals[0]])[0]
        md = md.replace("crap ton", "huge number", 1)
        remaining = reanchor_proposal_dicts(md, [proposals[1]])[0]
        self.assertIsNotNone(remaining.get("anchor"))
        self.assertIn("two uninterrupted hours", remaining["anchor"]["text"])

    def test_reanchor_preserves_pid_when_entries_skipped(self) -> None:
        proposals = [
            {"kind": "comment", "body": "a", "_pid": "p0", "anchor": None},
            "not-a-dict",
            {
                "kind": "comment",
                "body": "b",
                "_pid": "p2",
                "anchor": {"start": 60, "end": 82, "text": "two uninterrupted hours"},
            },
        ]
        out = reanchor_proposal_dicts(SAMPLE, proposals)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0].get("_pid"), "p0")
        self.assertEqual(out[2].get("pid"), "p2")


if __name__ == "__main__":
    unittest.main()
