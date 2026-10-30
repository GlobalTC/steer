"""Multipart upload to POST /api/transcribe-voice (no cgi module)."""

from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent.parent
DESK = APP.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402


def _multipart_body(boundary: str, audio: bytes) -> bytes:
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="clip.webm"\r\n'
        f"Content-Type: audio/webm\r\n\r\n"
    ).encode("ascii")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + audio + suffix


class TestTranscribeMultipart(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        steer_server.configure(["--catalog", str(DESK)])

    def test_parse_multipart_field_roundtrip(self) -> None:
        boundary = "SteerTestBoundary"
        audio = b"\x00\x01fake-webm"
        body = _multipart_body(boundary, audio)
        ct = f"multipart/form-data; boundary={boundary}"
        payload, part_type = steer_server.parse_multipart_field(body, ct, "audio")
        self.assertEqual(payload, audio)
        self.assertEqual(part_type, "audio/webm")

    @patch("voice_stt.transcribe_audio", return_value="hello from mic")
    @patch("voice_stt.stt_configured", return_value=True)
    def test_transcribe_handler_accepts_multipart_audio(
        self, _mock_cfg: object, mock_transcribe: object
    ) -> None:
        boundary = "SteerHandlerBoundary"
        audio = b"recorded-audio-bytes"
        body = _multipart_body(boundary, audio)
        ct = f"multipart/form-data; boundary={boundary}"
        httpd = steer_server.ThreadedHTTPServer(("127.0.0.1", 0), steer_server.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            req = Request(
                "http://127.0.0.1:%d/steer/api/transcribe-voice" % port,
                data=body,
                method="POST",
            )
            req.add_header("Content-Type", ct)
            with urlopen(req, timeout=5) as resp:
                out = json.loads(resp.read().decode("utf-8"))
        finally:
            httpd.shutdown()
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("transcript"), "hello from mic")
        mock_transcribe.assert_called_once()
        args, kwargs = mock_transcribe.call_args
        self.assertEqual(args[0], audio)
        self.assertEqual(kwargs.get("content_type"), "audio/webm")


if __name__ == "__main__":
    unittest.main()
