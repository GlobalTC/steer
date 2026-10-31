"""install_port catalog detection and ensure_desk restart behavior."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import install_port  # noqa: E402
import server as steer_server  # noqa: E402


def _minimal_catalog(root: Path) -> None:
    (root / "assets").mkdir()
    (root / "review").mkdir(parents=True)
    (root / "steer.json").write_text(
        json.dumps({"port": 0, "base_path": "/steer", "host": "127.0.0.1"}) + "\n",
        encoding="utf-8",
    )
    (root / "assets" / "steer-slop-sample.md").write_text("# Hi\n", encoding="utf-8")
    (root / "review" / "current.json").write_text(
        '{"id":"steer-slop-sample","asset":"assets/steer-slop-sample.md"}\n',
        encoding="utf-8",
    )
    shutil.copy2(APP.parent / "start.py", root / "start.py")


class TestInstallPort(unittest.TestCase):
    def test_catalog_from_config(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="steer-install-port-"))
        try:
            _minimal_catalog(tmp)
            steer_server.configure(["--catalog", str(tmp), "--port", "0"])
            httpd = steer_server.ThreadedHTTPServer(
                ("127.0.0.1", 0), steer_server.Handler
            )
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                cat = install_port.catalog_from_config("127.0.0.1", port, "/steer")
                self.assertIsNotNone(cat)
                self.assertTrue(install_port.catalogs_match(cat, tmp))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ensure_desk_rejects_different_catalog_on_port(self) -> None:
        cat_a = Path(tempfile.mkdtemp(prefix="steer-cat-a-"))
        cat_b = Path(tempfile.mkdtemp(prefix="steer-cat-b-"))
        try:
            _minimal_catalog(cat_a)
            _minimal_catalog(cat_b)
            steer_server.configure(["--catalog", str(cat_a)])
            httpd = steer_server.ThreadedHTTPServer(
                ("127.0.0.1", 0), steer_server.Handler
            )
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                code, msg = install_port.ensure_desk(cat_b, "127.0.0.1", port, "/steer")
                self.assertEqual(code, 1)
                self.assertIn("different desk", msg)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
        finally:
            shutil.rmtree(cat_a, ignore_errors=True)
            shutil.rmtree(cat_b, ignore_errors=True)

    def test_catalogs_match_resolves_symlinks(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="steer-symlink-"))
        try:
            real = tmp / "real"
            real.mkdir()
            link = tmp / "link"
            link.symlink_to(real, target_is_directory=True)
            self.assertTrue(install_port.catalogs_match(link, real))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
