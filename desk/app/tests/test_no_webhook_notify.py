"""No-webhook saves should not show unhealthy notify state."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402


def _write_min_catalog(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "review" / "saves").mkdir(parents=True)
    (root / "assets" / "piece.md").write_text("# Piece\n\nBody.\n", encoding="utf-8")
    (root / "review" / "current.json").write_text(
        json.dumps({"id": "piece", "asset": "assets/piece.md"}) + "\n",
        encoding="utf-8",
    )
    (root / "steer.json").write_text(
        json.dumps({"name": "TEST", "base_path": "/steer"}) + "\n",
        encoding="utf-8",
    )


class TestNoWebhookNotify(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._catalog_dir = tempfile.mkdtemp(prefix="steer-nowh-")
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

    def test_save_notify_healthy_without_webhook(self) -> None:
        body = json.dumps({"markdown": "# Piece\n\nNew.\n", "id": "piece"}).encode()
        url = "http://127.0.0.1:%d%s/api/save" % (self.port, self.base)
        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": "http://127.0.0.1:%d" % self.port,
                "Referer": "http://127.0.0.1:%d%s/" % (self.port, self.base),
            },
        )
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
        time.sleep(0.3)
        snap = steer_server.doc_snapshot()
        notify = snap.get("notify") or {}
        self.assertTrue(notify.get("healthy"))
        self.assertEqual(notify.get("not_notified"), [])
        self.assertEqual(notify.get("save_wake_mode"), "agent")


if __name__ == "__main__":
    unittest.main()
