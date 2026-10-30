"""Tests for server STT helper."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from voice_stt import stt_configured, transcribe_audio  # noqa: E402


class TestVoiceStt(unittest.TestCase):
    def test_stt_configured_requires_url(self) -> None:
        self.assertFalse(stt_configured({}))
        self.assertTrue(stt_configured({"VOICE_STT_URL": "https://example/stt"}))

    @patch("voice_stt.urlopen")
    def test_transcribe_multipart_response(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.read.return_value = json.dumps({"transcript": " hello "}).encode()
        resp.__enter__.return_value = resp
        mock_urlopen.return_value = resp
        text = transcribe_audio(
            b"abc",
            content_type="audio/webm",
            env={"VOICE_STT_URL": "https://example/stt"},
        )
        self.assertEqual(text, "hello")

    def test_transcribe_without_config_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            transcribe_audio(b"x", env={})


if __name__ == "__main__":
    unittest.main()
