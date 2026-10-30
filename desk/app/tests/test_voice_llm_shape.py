"""Malformed LLM chat responses fall back without raising."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from voice_llm import resolve_dictation_host_chat  # noqa: E402


class TestVoiceLlmShape(unittest.TestCase):
    @patch("voice_llm.urlopen")
    def test_bad_choices_shape_returns_none(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.read.return_value = b'{"choices":["x"]}'
        resp.__enter__.return_value = resp
        mock_urlopen.return_value = resp
        with patch.dict("os.environ", {"XAI_API_KEY": "test"}, clear=False):
            out = resolve_dictation_host_chat("Make it shorter.", "# Title\n\nBody.\n")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
