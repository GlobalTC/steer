"""Tests for host LLM resolver wiring."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REVIEW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REVIEW))

from voice_llm import host_chat_configured, resolve_dictation_primary  # noqa: E402


class TestVoiceLlm(unittest.TestCase):
    def test_host_chat_configured_with_xai_env(self) -> None:
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}, clear=False):
            self.assertTrue(host_chat_configured({}))

    def test_heuristic_fallback_when_llm_unreachable(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XAI_API_KEY", None)
            proposals, resolver = resolve_dictation_primary(
                "Make the tone less corporate overall.",
                "# Title\n\nBody paragraph here.\n",
            )
            self.assertEqual(resolver, "heuristic")
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0].kind, "general")


if __name__ == "__main__":
    unittest.main()
