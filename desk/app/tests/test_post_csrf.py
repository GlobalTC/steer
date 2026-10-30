"""POST origin and Content-Type guards."""

from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent.parent
DESK = APP.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402


class TestPostCsrf(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        steer_server.configure(["--catalog", str(DESK)])
        cls.httpd = steer_server.ThreadedHTTPServer(
            ("127.0.0.1", 0), steer_server.Handler
        )
        cls.port = cls.httpd.server_address[1]
        cls.base = steer_server.BASE_PATH or "/steer"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _post(self, path: str, body: bytes, headers: dict) -> tuple[int, dict]:
        url = "http://127.0.0.1:%d%s%s" % (self.port, self.base, path)
        req = Request(url, data=body, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_cross_origin_save_forbidden(self) -> None:
        code, data = self._post(
            "/api/save",
            b'{"markdown":"# x\\n"}',
            {
                "Content-Type": "application/json",
                "Origin": "http://evil.example",
            },
        )
        self.assertEqual(code, 403)
        self.assertFalse(data.get("ok", True))

    def test_text_plain_save_unsupported(self) -> None:
        code, data = self._post(
            "/api/save",
            b"markdown=hack",
            {
                "Content-Type": "text/plain",
                "Origin": "http://127.0.0.1:%d" % self.port,
            },
        )
        self.assertEqual(code, 415)
        self.assertFalse(data.get("ok", True))

    def test_webhook_config_honors_target(self) -> None:
        primary = DESK / "review" / ".webhook.env"
        second = DESK / "review" / "second.webhook.env"
        primary.write_text("WEBHOOK_URL=http://old\nWEBHOOK_KEY=old\n", encoding="utf-8")
        second.write_text("WEBHOOK_URL=http://old2\nWEBHOOK_KEY=old2\n", encoding="utf-8")
        steer_path = DESK / "steer.json"
        cfg = json.loads(steer_path.read_text())
        cfg["notify"] = [
            {"name": "Primary", "env": "review/.webhook.env"},
            {"name": "Second", "env": "review/second.webhook.env", "required": False},
        ]
        steer_path.write_text(json.dumps(cfg, indent=2) + "\n")
        steer_server.configure(["--catalog", str(DESK)])
        try:
            code, data = self._post(
                "/api/webhook-config",
                json.dumps(
                    {
                        "url": "http://127.0.0.1:9/second",
                        "key": "k2",
                        "target": "Second",
                    }
                ).encode(),
                {
                    "Content-Type": "application/json",
                    "Origin": "http://127.0.0.1:%d" % self.port,
                },
            )
            self.assertEqual(code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("old", primary.read_text())
            self.assertIn("127.0.0.1:9/second", second.read_text())
        finally:
            cfg["notify"] = [
                {
                    "name": "STEER",
                    "env": "review/.webhook.env",
                    "why": "this bot's Draft review save ping routine",
                }
            ]
            steer_path.write_text(json.dumps(cfg, indent=2) + "\n")
            if second.is_file():
                second.unlink()
            if primary.is_file():
                primary.unlink()
            steer_server.configure(["--catalog", str(DESK)])


if __name__ == "__main__":
    unittest.main()
