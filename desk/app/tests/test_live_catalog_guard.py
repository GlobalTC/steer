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

APP = Path(__file__).resolve().parents[1]
DESK = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP))

import catalog_paths  # noqa: E402
import install_port  # noqa: E402
import server as steer_server  # noqa: E402


def _minimal_live_catalog(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "review" / "saves").mkdir(parents=True)
    (root / "assets" / "steer-slop-sample.md").write_text("# Hi\n", encoding="utf-8")
    (root / "review" / "current.json").write_text(
        '{"id":"steer-slop-sample","asset":"assets/steer-slop-sample.md"}\n',
        encoding="utf-8",
    )
    (root / "steer.json").write_text(
        json.dumps({"port": 8766, "base_path": "/steer", "host": "127.0.0.1"}) + "\n",
        encoding="utf-8",
    )


class TestLiveCatalogGuard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="steer-live-guard-"))
        self.live = self._tmp / "live-catalog"
        self.live.mkdir()
        os.environ["STEER_UNITTEST_LIVE_CATALOG"] = str(self.live)

    def tearDown(self) -> None:
        os.environ.pop("STEER_UNITTEST_LIVE_CATALOG", None)
        os.environ.pop("STEER_ALLOW_LIVE_CATALOG", None)
        os.environ.pop("STEER_CATALOG", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_refuse_dotdot_traversal_install(self) -> None:
        raw = "%s/../%s" % (self.live, self.live.name)
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(
                catalog_paths.resolve_catalog_path(raw),
                operation="install",
            )

    def test_refuse_symlink_to_live_install(self) -> None:
        link = self._tmp / "link"
        link.symlink_to(self.live, target_is_directory=True)
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(link, operation="install")

    def test_install_catalog_script_refuses_live(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env={**os.environ, "STEER_CATALOG": str(self.live)},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)

    def test_install_catalog_script_refuses_subdirectory_of_live(self) -> None:
        sub = self.live / "sub"
        sub.mkdir()
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env={**os.environ, "STEER_CATALOG": str(sub)},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)
        self.assertFalse((sub / "app").exists())

    def test_refuse_subdirectory_of_live_install(self) -> None:
        sub = self.live / "nested" / "desk"
        sub.mkdir(parents=True)
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(sub, operation="install")

    def test_install_ignores_inherited_allow_env(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env={
                **os.environ,
                "STEER_CATALOG": str(self.live),
                "STEER_ALLOW_LIVE_CATALOG": "1",
            },
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_server_implicit_cwd_refuses_live(self) -> None:
        ws = self._tmp / "workspace"
        ws.mkdir()
        (ws / "steer-catalog").symlink_to(self.live, target_is_directory=True)
        os.environ.pop("STEER_CATALOG", None)
        prev = os.getcwd()
        try:
            os.chdir(ws)
            with self.assertRaises(catalog_paths.CatalogRefusalError):
                catalog_paths.refuse_implicit_live_server_catalog(
                    Path.cwd() / "steer-catalog"
                )
        finally:
            os.chdir(prev)

    def test_inherited_allow_does_not_bypass_implicit_server(self) -> None:
        os.environ["STEER_ALLOW_LIVE_CATALOG"] = "1"
        ws = self._tmp / "workspace2"
        ws.mkdir()
        (ws / "steer-catalog").symlink_to(self.live, target_is_directory=True)
        prev = os.getcwd()
        try:
            os.chdir(ws)
            with self.assertRaises(SystemExit):
                steer_server.configure([])
        finally:
            os.chdir(prev)

    def test_subprocess_app_outside_catalog_restart_command(self) -> None:
        """Documented Grok restart: python3 <app-outside>/server.py --catalog <live>."""
        _minimal_live_catalog(self.live)
        app_outside = self._tmp / "steer" / "app"
        shutil.copytree(APP, app_outside)
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        cfg = json.loads((self.live / "steer.json").read_text(encoding="utf-8"))
        cfg["port"] = port
        (self.live / "steer.json").write_text(json.dumps(cfg) + "\n", encoding="utf-8")
        run_cwd = self._tmp / "workspace"
        run_cwd.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "STEER_CATALOG"}
        proc = subprocess.Popen(
            [
                sys.executable,
                str(app_outside / "server.py"),
                "--catalog",
                str(self.live),
            ],
            cwd=str(run_cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        try:
            ok = False
            for _ in range(40):
                if install_port.page_responds("127.0.0.1", port, "/steer"):
                    ok = True
                    break
                if proc.poll() is not None:
                    break
                threading.Event().wait(0.05)
            if proc.poll() is not None and proc.stderr:
                self.fail(proc.stderr.read().decode("utf-8", errors="replace"))
            self.assertTrue(ok, "server did not respond on /steer")
        finally:
            install_port.stop_desk_on_port(port)
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)

    def test_explicit_catalog_restart_command_starts(self) -> None:
        """Grok layout: app outside catalog, explicit --catalog on CLI."""
        _minimal_live_catalog(self.live)
        steer_server.configure(["--catalog", str(self.live)])
        httpd = steer_server.ThreadedHTTPServer(
            ("127.0.0.1", 0), steer_server.Handler
        )
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(install_port.page_responds("127.0.0.1", port, "/steer"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_live_catalog_start_py_passes_explicit_flag(self) -> None:
        _minimal_live_catalog(self.live)
        shutil.copy2(DESK / "start.py", self.live / "start.py")
        shutil.copytree(APP, self.live / "app")
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        cfg = json.loads((self.live / "steer.json").read_text(encoding="utf-8"))
        cfg["port"] = port
        (self.live / "steer.json").write_text(json.dumps(cfg) + "\n", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(self.live / "start.py")],
            cwd=str(self.live),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            ok = False
            for _ in range(40):
                if install_port.page_responds("127.0.0.1", port, "/steer"):
                    ok = True
                    break
                if proc.poll() is not None:
                    break
                threading.Event().wait(0.05)
            if proc.poll() is not None and proc.stderr:
                self.fail(proc.stderr.read())
            self.assertTrue(ok)
        finally:
            install_port.stop_desk_on_port(port)
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)

    def test_install_catalog_honors_and_persists_steer_port(self) -> None:
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
        cfg = json.loads((catalog / "steer.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("port"), port)
        install_port.stop_desk_on_port(port)

    def test_unittest_live_catalog_override(self) -> None:
        os.environ.pop("STEER_UNITTEST_LIVE_CATALOG", None)
        self.assertEqual(
            catalog_paths.live_catalog_path().resolve(),
            catalog_paths.WORKSPACE_STEER_CATALOG.resolve(),
        )
        fake = self._tmp / "fake-live"
        os.environ["STEER_UNITTEST_LIVE_CATALOG"] = str(fake)
        self.assertEqual(catalog_paths.live_catalog_path().resolve(), fake.resolve())


if __name__ == "__main__":
    unittest.main()
