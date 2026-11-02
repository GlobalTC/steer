"""Refuse binds to the live workspace STEER catalog."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP))

import catalog_paths  # noqa: E402
import install_port  # noqa: E402
import server as steer_server  # noqa: E402


class TestLiveCatalogGuard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="steer-live-guard-"))
        self.live = self._tmp / "live-catalog"
        self.live.mkdir()
        os.environ["STEER_LIVE_CATALOG_PATH"] = str(self.live)

    def tearDown(self) -> None:
        os.environ.pop("STEER_LIVE_CATALOG_PATH", None)
        os.environ.pop("STEER_ALLOW_LIVE_CATALOG", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_refuse_dotdot_traversal(self) -> None:
        raw = "%s/../%s" % (self.live, self.live.name)
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(
                catalog_paths.resolve_catalog_path(raw),
                operation="install",
            )

    def test_refuse_symlink_to_live(self) -> None:
        link = self._tmp / "link"
        link.symlink_to(self.live, target_is_directory=True)
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(link, operation="install")

    def test_refuse_explicit_path_to_live(self) -> None:
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(self.live, operation="install")

    def test_install_catalog_script_refuses_live(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env={
                **os.environ,
                "STEER_CATALOG": str(self.live),
            },
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)

    def test_server_default_cwd_serves_live_without_allow(self) -> None:
        ws = self._tmp / "workspace"
        ws.mkdir()
        (ws / "steer-catalog").symlink_to(self.live, target_is_directory=True)
        os.environ.pop("STEER_ALLOW_LIVE_CATALOG", None)
        os.environ.pop("STEER_CATALOG", None)
        prev = os.getcwd()
        try:
            os.chdir(ws)
            target = catalog_paths.default_catalog_path()
            with self.assertRaises(catalog_paths.CatalogRefusalError):
                catalog_paths.ensure_server_catalog_allowed(target)
        finally:
            os.chdir(prev)

    def test_server_allows_live_with_allow_env(self) -> None:
        os.environ["STEER_ALLOW_LIVE_CATALOG"] = "1"
        steer_server.configure(["--catalog", str(self.live)])
        self.assertEqual(steer_server.CATALOG.resolve(), self.live.resolve())

    def test_install_catalog_honors_steer_port(self) -> None:
        catalog = self._tmp / "port-catalog"
        script = ROOT / "packaging" / "install-catalog.sh"
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env={
                **os.environ,
                "STEER_CATALOG": str(catalog),
                "STEER_PORT": str(port),
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertTrue(install_port.page_responds("127.0.0.1", port, "/steer"))
        listener = install_port.listener_catalog("127.0.0.1", port, "/steer")
        self.assertIsNotNone(listener)
        self.assertTrue(install_port.catalogs_match(listener, catalog))
        install_port.stop_desk_on_port(port)


if __name__ == "__main__":
    unittest.main()
