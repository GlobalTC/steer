"""Rendered index.html: template substitution, logo asset, STEER_CONFIG."""

from __future__ import annotations

import re
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

APP = Path(__file__).resolve().parent.parent
DESK = APP.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402


class TestIndexServe(unittest.TestCase):
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

    def test_steers_home_has_config_and_logo(self) -> None:
        root = "http://127.0.0.1:%d%s/" % (self.port, self.base)
        with urlopen(root, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        self.assertNotIn("{{", html, "unsubstituted template placeholders")
        self.assertIn("window.STEER_CONFIG", html)
        self.assertIn('"base"', html)
        m = re.search(r'<img class="brand-mark" src="([^"]+)"', html)
        self.assertIsNotNone(m, "toolbar logo img")
        logo_url = m.group(1)
        if logo_url.startswith("/"):
            logo_url = "http://127.0.0.1:%d%s" % (self.port, logo_url)
        elif logo_url.startswith(self.base):
            logo_url = "http://127.0.0.1:%d%s" % (self.port, logo_url)
        with urlopen(logo_url, timeout=5) as logo_resp:
            self.assertEqual(logo_resp.status, 200)
            self.assertGreater(int(logo_resp.headers.get("Content-Length", "1")), 0)


if __name__ == "__main__":
    unittest.main()
