"""POST origin, Referer, and Content-Type guards (temp catalog only)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402

# Simulated Tailscale Serve hostname (not a real tailnet node).
PROXY_HOST = "steer-node.example.ts.net"


def _write_min_catalog(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "review" / "saves").mkdir(parents=True)
    (root / "assets" / "piece.md").write_text("# Piece\n\nBody.\n", encoding="utf-8")
    (root / "review" / "current.json").write_text(
        json.dumps({"id": "piece", "asset": "assets/piece.md"}) + "\n",
        encoding="utf-8",
    )
    (root / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "id": "piece",
                        "title": "Piece",
                        "body": "assets/piece.md",
                        "status": "draft",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "steer.json").write_text(
        json.dumps({"name": "TEST", "base_path": "/steer"}) + "\n",
        encoding="utf-8",
    )


class TestPostCsrf(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._catalog_dir = tempfile.mkdtemp(prefix="steer-csrf-test-")
        cls.catalog = Path(cls._catalog_dir)
        _write_min_catalog(cls.catalog)
        steer_server.configure(["--catalog", str(cls.catalog)])
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
        shutil.rmtree(cls._catalog_dir, ignore_errors=True)

    def _post(
        self,
        path: str,
        body: bytes,
        headers: dict,
        *,
        host: str | None = None,
    ) -> tuple[int, dict]:
        url = "http://127.0.0.1:%d%s%s" % (self.port, self.base, path)
        req = Request(url, data=body, method="POST")
        if host is not None:
            req.add_header("Host", host)
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urlopen(req, timeout=5) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw.strip() else {}
        except HTTPError as exc:
            raw = exc.read().decode()
            return exc.code, json.loads(raw) if raw.strip() else {}

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

    def test_proxied_host_matching_origin_and_referer_allowed(self) -> None:
        origin = "https://%s" % PROXY_HOST
        code, data = self._post(
            "/api/save",
            json.dumps({"markdown": "# ok\n", "id": "piece"}).encode(),
            {
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": origin + "/steer/",
            },
            host=PROXY_HOST,
        )
        self.assertEqual(code, 200)
        self.assertTrue(data.get("ok"))

    def test_proxied_host_foreign_origin_forbidden(self) -> None:
        origin = "https://%s" % PROXY_HOST
        code, data = self._post(
            "/api/save",
            b'{"markdown":"# x\\n"}',
            {
                "Content-Type": "application/json",
                "Origin": "https://evil.example",
                "Referer": origin + "/steer/",
            },
            host=PROXY_HOST,
        )
        self.assertEqual(code, 403)
        self.assertFalse(data.get("ok", True))

    def test_proxied_host_foreign_referer_forbidden(self) -> None:
        origin = "https://%s" % PROXY_HOST
        code, data = self._post(
            "/api/save",
            b'{"markdown":"# x\\n"}',
            {
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": "https://evil.example/steer/",
            },
            host=PROXY_HOST,
        )
        self.assertEqual(code, 403)
        self.assertFalse(data.get("ok", True))

    def test_lookalike_referer_host_forbidden(self) -> None:
        origin = "https://%s" % PROXY_HOST
        lookalike = "https://%s.evil.com" % PROXY_HOST
        code, data = self._post(
            "/api/save",
            b'{"markdown":"# x\\n"}',
            {
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": lookalike + "/steer/",
            },
            host=PROXY_HOST,
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
        primary = self.catalog / "review" / ".webhook.env"
        second = self.catalog / "review" / "second.webhook.env"
        primary.write_text("WEBHOOK_URL=http://old\nWEBHOOK_KEY=old\n", encoding="utf-8")
        second.write_text("WEBHOOK_URL=http://old2\nWEBHOOK_KEY=old2\n", encoding="utf-8")
        steer_path = self.catalog / "steer.json"
        cfg = json.loads(steer_path.read_text())
        cfg["notify"] = [
            {"name": "Primary", "env": "review/.webhook.env"},
            {"name": "Second", "env": "review/second.webhook.env", "required": False},
        ]
        steer_path.write_text(json.dumps(cfg, indent=2) + "\n")
        steer_server.configure(["--catalog", str(self.catalog)])
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
            cfg["notify"] = []
            steer_path.write_text(json.dumps(cfg, indent=2) + "\n")
            if second.is_file():
                second.unlink()
            if primary.is_file():
                primary.unlink()
            steer_server.configure(["--catalog", str(self.catalog)])


if __name__ == "__main__":
    unittest.main()
