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
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
DESK = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP))

import catalog_paths  # noqa: E402
import install_port  # noqa: E402
import server as steer_server  # noqa: E402

_INHERITED_BYPASS_ENV = {
    "STEER_UNITTEST_LIVE_CATALOG": "/tmp/steer-qa-fake-live",
    "STEER_LIVE_CATALOG_PATH": "/tmp/steer-qa-fake-live",
    "STEER_TESTING": "1",
    "STEER_ALLOW_LIVE_CATALOG": "1",
}


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


@contextmanager
def _live_catalog_is(path: Path):
    resolved = path.resolve()
    with patch.object(catalog_paths, "live_catalog_path", return_value=resolved):
        yield


class TestLiveCatalogGuard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="steer-live-guard-"))
        self.live = self._tmp / "live-catalog"
        self.live.mkdir()
        self._workspace_targets: list[Path] = []
        for key in _INHERITED_BYPASS_ENV:
            os.environ.pop(key, None)
        os.environ.pop("STEER_CATALOG", None)

    def tearDown(self) -> None:
        for key in _INHERITED_BYPASS_ENV:
            os.environ.pop(key, None)
        os.environ.pop("STEER_CATALOG", None)
        for p in self._workspace_targets:
            shutil.rmtree(p, ignore_errors=True)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _workspace_target(self, suffix: str) -> Path:
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        name = "qa-guard-%s-%s" % (suffix, uuid.uuid4().hex[:8])
        path = catalog_paths.WORKSPACE_STEER_CATALOG / name
        path.mkdir(parents=True, exist_ok=True)
        self._workspace_targets.append(path)
        return path

    def _install_env(self, catalog: str, *, extra: dict | None = None) -> dict:
        env = {k: v for k, v in os.environ.items() if k != "STEER_CATALOG"}
        env["STEER_CATALOG"] = catalog
        if extra:
            env.update(extra)
        return env

    def test_refuse_dotdot_traversal_install(self) -> None:
        raw = "%s/../%s" % (self.live, self.live.name)
        with _live_catalog_is(self.live):
            with self.assertRaises(catalog_paths.CatalogRefusalError):
                catalog_paths.refuse_live_workspace_catalog(
                    catalog_paths.resolve_catalog_path(raw),
                    operation="install",
                )

    def test_refuse_symlink_to_live_install(self) -> None:
        link = self._tmp / "link"
        link.symlink_to(self.live, target_is_directory=True)
        with _live_catalog_is(self.live):
            with self.assertRaises(catalog_paths.CatalogRefusalError):
                catalog_paths.refuse_live_workspace_catalog(link, operation="install")

    def test_install_catalog_script_refuses_live(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env=self._install_env(str(catalog_paths.WORKSPACE_STEER_CATALOG)),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)

    def test_install_catalog_script_refuses_subdirectory_of_live(self) -> None:
        sub = self._workspace_target("sub")
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env=self._install_env(str(sub)),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)
        self.assertFalse((sub / "app").exists())

    def test_refuse_subdirectory_of_live_install(self) -> None:
        sub = self._workspace_target("nested")
        with self.assertRaises(catalog_paths.CatalogRefusalError):
            catalog_paths.refuse_live_workspace_catalog(sub, operation="install")

    def test_install_ignores_inherited_allow_env(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env=self._install_env(
                str(catalog_paths.WORKSPACE_STEER_CATALOG),
                extra={"STEER_ALLOW_LIVE_CATALOG": "1"},
            ),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_inherited_bypass_env_vars_do_not_redefine_live_path(self) -> None:
        with patch.dict(os.environ, _INHERITED_BYPASS_ENV, clear=False):
            self.assertEqual(
                catalog_paths.live_catalog_path().resolve(),
                catalog_paths.WORKSPACE_STEER_CATALOG.resolve(),
            )

    def test_inherited_bypass_env_cannot_install_into_live(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        sub = self._workspace_target("inherit-install")
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env=self._install_env(str(sub), extra=_INHERITED_BYPASS_ENV),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Refusing", proc.stderr + proc.stdout)
        self.assertFalse((sub / "app").exists())

    def test_inherited_bypass_env_cannot_install_into_live_root(self) -> None:
        script = ROOT / "packaging" / "install-catalog.sh"
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT / "packaging"),
            env=self._install_env(
                str(catalog_paths.WORKSPACE_STEER_CATALOG),
                extra=_INHERITED_BYPASS_ENV,
            ),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((catalog_paths.WORKSPACE_STEER_CATALOG / "app").exists())

    def test_server_implicit_cwd_refuses_live(self) -> None:
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        ws = self._tmp / "workspace"
        ws.mkdir()
        (ws / "steer-catalog").symlink_to(
            catalog_paths.WORKSPACE_STEER_CATALOG, target_is_directory=True
        )
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
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        ws = self._tmp / "workspace2"
        ws.mkdir()
        (ws / "steer-catalog").symlink_to(
            catalog_paths.WORKSPACE_STEER_CATALOG, target_is_directory=True
        )
        prev = os.getcwd()
        try:
            os.chdir(ws)
            with patch.dict(os.environ, {"STEER_ALLOW_LIVE_CATALOG": "1"}, clear=False):
                with self.assertRaises(SystemExit):
                    steer_server.configure([])
        finally:
            os.chdir(prev)

    def test_inherited_bypass_env_cannot_serve_live_implicitly(self) -> None:
        catalog_paths.WORKSPACE_STEER_CATALOG.mkdir(parents=True, exist_ok=True)
        sub = self._workspace_target("inherit-serve")
        prev = os.getcwd()
        try:
            os.chdir(self._tmp)
            with patch.dict(
                os.environ,
                {**_INHERITED_BYPASS_ENV, "STEER_CATALOG": str(sub)},
                clear=False,
            ):
                with self.assertRaises(SystemExit):
                    steer_server.configure([])
        finally:
            os.chdir(prev)

    def test_shipped_catalog_paths_has_no_live_override_env_reads(self) -> None:
        source = (APP / "catalog_paths.py").read_text(encoding="utf-8")
        for name in (
            "STEER_UNITTEST_LIVE_CATALOG",
            "STEER_LIVE_CATALOG_PATH",
            "STEER_TESTING",
            "STEER_ALLOW_LIVE_CATALOG",
        ):
            self.assertNotIn(name, source, "catalog_paths.py must not reference %s" % name)

    def test_subprocess_app_outside_catalog_restart_command(self) -> None:
        """Documented Grok restart: python3 <app-outside>/server.py --catalog <live>."""
        _minimal_live_catalog(self.live)
        marker = "qa-catalog-marker-%s" % uuid.uuid4().hex
        (self.live / ".qa-catalog-marker").write_text(marker, encoding="utf-8")
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
            served = install_port.catalog_from_config("127.0.0.1", port, "/steer")
            self.assertIsNotNone(served)
            assert served is not None
            self.assertEqual(served.resolve(), self.live.resolve())
            self.assertEqual(
                (served / ".qa-catalog-marker").read_text(encoding="utf-8"),
                marker,
            )
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
            served = install_port.catalog_from_config("127.0.0.1", port, "/steer")
            self.assertEqual(served.resolve() if served else None, self.live.resolve())
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
            env=self._install_env(str(catalog), extra={"STEER_PORT": str(port)}),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        cfg = json.loads((catalog / "steer.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("port"), port)
        install_port.stop_desk_on_port(port)


if __name__ == "__main__":
    unittest.main()
