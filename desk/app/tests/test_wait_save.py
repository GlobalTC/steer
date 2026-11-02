"""wait-save and unprocessed save detection."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
DESK = APP.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402
from wait_save import unprocessed_save, wait_for_save  # noqa: E402


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


class TestWaitSave(unittest.TestCase):
    def setUp(self) -> None:
        self._catalog_dir = tempfile.mkdtemp(prefix="steer-wait-")
        self.catalog = Path(self._catalog_dir)
        _write_min_catalog(self.catalog)

    def tearDown(self) -> None:
        shutil.rmtree(self._catalog_dir, ignore_errors=True)

    def test_unprocessed_none_when_no_latest(self) -> None:
        self.assertIsNone(unprocessed_save(self.catalog))

    def test_unprocessed_after_save(self) -> None:
        latest = self.catalog / "review" / "saves" / "latest.json"
        latest.write_text(
            json.dumps({"generation": 1, "saved_at": "t", "asset_id": "piece"}) + "\n",
            encoding="utf-8",
        )
        found = unprocessed_save(self.catalog)
        self.assertIsNotNone(found)
        self.assertEqual(found.get("generation"), 1)

    def test_unprocessed_none_when_processed(self) -> None:
        saves = self.catalog / "review" / "saves"
        saves.mkdir(parents=True, exist_ok=True)
        (saves / "latest.json").write_text(
            json.dumps({"generation": 2, "saved_at": "t"}) + "\n",
            encoding="utf-8",
        )
        (saves / "processed.json").write_text(
            json.dumps({"generation": 2, "saved_at": "t"}) + "\n",
            encoding="utf-8",
        )
        self.assertIsNone(unprocessed_save(self.catalog))

    def test_wait_timeout(self) -> None:
        result = wait_for_save(self.catalog, timeout=0.3, poll_interval=0.05)
        self.assertIsNone(result)

    def test_wait_returns_on_save(self) -> None:
        steer_server.configure(["--catalog", str(self.catalog)])
        httpd = steer_server.ThreadedHTTPServer(("127.0.0.1", 0), steer_server.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:

            def post_save() -> None:
                import time
                from urllib.request import Request, urlopen

                time.sleep(0.15)
                body = json.dumps({"markdown": "# Piece\n\nSaved.\n", "id": "piece"}).encode()
                url = "http://127.0.0.1:%d/steer/api/save" % port
                req = Request(
                    url,
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "http://127.0.0.1:%d" % port,
                        "Referer": "http://127.0.0.1:%d/steer/" % port,
                    },
                )
                with urlopen(req, timeout=5):
                    pass

            threading.Thread(target=post_save, daemon=True).start()
            record = wait_for_save(self.catalog, timeout=3.0, poll_interval=0.05)
            self.assertIsNotNone(record)
            self.assertEqual(record.get("generation"), 1)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_start_py_wait_save_cli_timeout(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(DESK / "start.py"),
                "wait-save",
                "--catalog",
                str(self.catalog),
                "--timeout",
                "0.2",
            ],
            capture_output=True,
            text=True,
            cwd=str(DESK),
        )
        self.assertEqual(proc.returncode, 2)
        data = json.loads(proc.stdout.strip())
        self.assertFalse(data.get("ok"))

    def test_start_py_wait_save_cli_success(self) -> None:
        latest = self.catalog / "review" / "saves" / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(
            json.dumps(
                {
                    "generation": 5,
                    "saved_at": "2026-01-01T00:00:00.000Z",
                    "asset_id": "piece",
                    "production_ready": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(DESK / "start.py"),
                "wait-save",
                "--catalog",
                str(self.catalog),
                "--timeout",
                "1",
            ],
            capture_output=True,
            text=True,
            cwd=str(DESK),
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout.strip())
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("generation"), 5)


if __name__ == "__main__":
    unittest.main()
