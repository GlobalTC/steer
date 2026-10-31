"""app_version() reflects the version loaded at configure() time."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import server as steer_server  # noqa: E402


class TestAppVersionCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._catalog_dir = tempfile.mkdtemp(prefix="steer-version-cache-")
        cls.catalog = Path(cls._catalog_dir)
        (cls.catalog / "review").mkdir(parents=True)
        (cls.catalog / "steer.json").write_text("{}\n", encoding="utf-8")
        (cls.catalog / "assets").mkdir()
        sample = cls.catalog / "assets" / "steer-slop-sample.md"
        sample.write_text("# Sample\n", encoding="utf-8")
        (cls.catalog / "review" / "current.json").write_text(
            '{"id":"steer-slop-sample","asset":"assets/steer-slop-sample.md"}\n',
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._catalog_dir, ignore_errors=True)

    def test_version_not_reread_after_disk_change(self) -> None:
        version_path = APP / "VERSION"
        original = version_path.read_text(encoding="utf-8")
        steer_server.configure(["--catalog", str(self.catalog)])
        cached = steer_server.app_version()
        version_path.write_text("9999.99.99-test\n", encoding="utf-8")
        try:
            self.assertEqual(steer_server.app_version(), cached)
            self.assertNotEqual(steer_server.app_version(), "9999.99.99-test")
        finally:
            version_path.write_text(original, encoding="utf-8")
            steer_server.configure(["--catalog", str(self.catalog)])

    def test_config_includes_catalog_path(self) -> None:
        steer_server.configure(["--catalog", str(self.catalog)])
        cfg = steer_server.client_config()
        self.assertEqual(cfg.get("catalog"), str(self.catalog.resolve()))


if __name__ == "__main__":
    unittest.main()
