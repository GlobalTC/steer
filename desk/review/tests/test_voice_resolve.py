"""Tests for voice dictation → mark proposal resolution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REVIEW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REVIEW))

from mark_index import map_phrase, paragraph_by_index  # noqa: E402
from mark_index import build_visible_index as bvi  # noqa: E402
from voice_resolve import (  # noqa: E402
    ANCHOR_CONFIDENCE_MIN,
    resolve_clause_heuristic,
    resolve_dictation_heuristic,
)


SAMPLE = """# Weekly Status

First paragraph about the team and outcomes.

Second paragraph mentions Elon's timelines and delivery dates here.

Third paragraph is about something else entirely.
"""


class TestAnchoring(unittest.TestCase):
    def test_unique_phrase_maps_with_high_confidence(self) -> None:
        proposals = resolve_dictation_heuristic(
            'In the second paragraph, cut the bit about Elon\'s timelines.',
            SAMPLE,
        )
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(p.kind, "comment")
        self.assertIsNotNone(p.anchor)
        self.assertGreaterEqual(p.confidence, ANCHOR_CONFIDENCE_MIN)
        assert p.anchor is not None
        self.assertIn("Elon", p.anchor.text)

    def test_ambiguous_instruction_becomes_general(self) -> None:
        proposals = resolve_dictation_heuristic(
            "Make the tone less corporate overall.",
            SAMPLE,
        )
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(p.kind, "general")
        self.assertIsNone(p.anchor)
        self.assertLess(p.confidence, ANCHOR_CONFIDENCE_MIN)

    def test_replace_with_anchored_phrase(self) -> None:
        md = "# Title\n\nThe hook line is something punchier for readers.\n\nBody text."
        proposals = resolve_dictation_heuristic(
            'Replace something punchier with a sharper hook.',
            md,
        )
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(p.kind, "replace")
        self.assertIsNotNone(p.anchor)
        self.assertIn("punchier", (p.excerpt or "").lower())

    def test_paragraph_only_without_phrase_is_general(self) -> None:
        idx = bvi(SAMPLE)
        proposal = resolve_clause_heuristic(
            "In the second paragraph, tighten the wording.",
            SAMPLE,
            idx,
        )
        self.assertEqual(proposal.kind, "general")
        self.assertIsNone(proposal.anchor)
        self.assertEqual(proposal.anchor_scope, "general")

    def test_map_phrase_respects_paragraph_scope(self) -> None:
        mapped = map_phrase(
            SAMPLE,
            "Elon's timelines",
            paragraph_index=1,
        )
        self.assertIsNotNone(mapped)
        start, end, text = mapped
        self.assertIn("Elon", text)


class TestAcceptRejectSemantics(unittest.TestCase):
    """Proposals carry enough data for the UI to accept or reject without guessing."""

    def test_proposal_serializes_anchor_for_accept(self) -> None:
        proposals = resolve_dictation_heuristic(
            "Remove Elon's timelines from the second paragraph.",
            SAMPLE,
        )
        p = proposals[0]
        d = p.to_dict()
        self.assertIn("anchor", d)
        if d["anchor"]:
            self.assertIn("start", d["anchor"])
            self.assertIn("end", d["anchor"])
            self.assertIn("text", d["anchor"])

    def test_low_confidence_general_has_no_anchor(self) -> None:
        proposals = resolve_dictation_heuristic(
            "The ending feels weak.",
            SAMPLE,
        )
        for p in proposals:
            if p.confidence < ANCHOR_CONFIDENCE_MIN:
                self.assertIsNone(p.anchor)
                self.assertEqual(p.kind, "general")


if __name__ == "__main__":
    unittest.main()
