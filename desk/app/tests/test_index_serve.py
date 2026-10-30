"""Rendered index.html: template substitution, logo asset, STEER_CONFIG."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402

# Minimal valid 1×1 PNG (exercise static serving from catalog brand/, not repo desk/brand).
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_temp_catalog(root: Path) -> None:
    """Catalog layout like a live install: brand/ under catalog, app code elsewhere."""
    (root / "assets").mkdir()
    (root / "brand").mkdir()
    (root / "review" / "saves").mkdir(parents=True)
    (root / "assets" / "sample.md").write_text("# Sample\n\nBody.\n", encoding="utf-8")
    (root / "brand" / "test-toolbar.png").write_bytes(_TINY_PNG)
    (root / "review" / "current.json").write_text(
        json.dumps({"id": "sample", "asset": "assets/sample.md"}) + "\n",
        encoding="utf-8",
    )
    (root / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "id": "sample",
                        "title": "Sample",
                        "body": "assets/sample.md",
                        "status": "draft",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "steer.json").write_text(
        json.dumps(
            {
                "name": "TEST",
                "base_path": "/steer",
                "brand": {
                    "toolbar_logo": "test-toolbar.png",
                    "favicon": "test-mark.png",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "brand" / "test-mark.png").write_bytes(_TINY_PNG)


class TestIndexServe(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._catalog_dir = tempfile.mkdtemp(prefix="steer-catalog-test-")
        cls.catalog = Path(cls._catalog_dir)
        _write_temp_catalog(cls.catalog)
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

    def test_steers_home_has_config_and_logo(self) -> None:
        root = "http://127.0.0.1:%d%s/" % (self.port, self.base)
        with urlopen(root, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        self.assertNotIn("{{", html, "unsubstituted template placeholders")
        self.assertIn("window.STEER_CONFIG", html)
        self.assertIn('"base"', html)
        self.assertIn("test-toolbar.png", html)
        m = re.search(r'<img class="brand-mark" src="([^"]+)"', html)
        self.assertIsNotNone(m, "toolbar logo img")
        logo_url = m.group(1)
        if logo_url.startswith("/"):
            logo_url = "http://127.0.0.1:%d%s" % (self.port, logo_url)
        elif logo_url.startswith(self.base):
            logo_url = "http://127.0.0.1:%d%s" % (self.port, logo_url)
        with urlopen(logo_url, timeout=5) as logo_resp:
            self.assertEqual(logo_resp.status, 200)
            body = logo_resp.read()
            self.assertGreater(len(body), 0)


if __name__ == "__main__":
    unittest.main()
