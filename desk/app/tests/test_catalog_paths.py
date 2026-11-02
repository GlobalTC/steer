"""Default catalog path resolution."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from catalog_paths import (  # noqa: E402
    CatalogRefusalError,
    catalog_display_default,
    default_catalog_path,
    refuse_live_workspace_catalog,
    resolve_catalog_path,
)


class TestCatalogPaths(unittest.TestCase):
    def test_explicit_flag(self) -> None:
        p = default_catalog_path("/tmp/my-steer")
        self.assertEqual(p, Path("/tmp/my-steer").resolve())

    def test_steer_catalog_env(self) -> None:
        with patch.dict(os.environ, {"STEER_CATALOG": "/tmp/from-env"}, clear=False):
            p = default_catalog_path()
        self.assertEqual(p, Path("/tmp/from-env").resolve())

    def test_start_py_dir_beats_env(self) -> None:
        anchor = Path("/tmp/anchor-catalog")
        with patch.dict(os.environ, {"STEER_CATALOG": "/tmp/from-env"}, clear=False):
            p = default_catalog_path(start_py_dir=anchor)
        self.assertEqual(p, anchor.resolve())

    def test_cwd_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STEER_CATALOG", None)
            with patch("catalog_paths.Path.cwd", return_value=Path("/home/user/project")):
                p = default_catalog_path()
        self.assertEqual(p, (Path("/home/user/project") / "steer-catalog").resolve())

    def test_resolve_follows_symlink(self) -> None:
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        try:
            real = tmp / "real"
            real.mkdir()
            link = tmp / "link"
            link.symlink_to(real, target_is_directory=True)
            self.assertEqual(resolve_catalog_path(link), real.resolve())
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_display_default(self) -> None:
        self.assertEqual(catalog_display_default(), "<package>/steer-catalog")

    def test_refuse_live_catalog(self) -> None:
        import tempfile

        live = Path(tempfile.mkdtemp())
        try:
            os.environ["STEER_UNITTEST_LIVE_CATALOG"] = str(live)
            with self.assertRaises(CatalogRefusalError):
                refuse_live_workspace_catalog(live, operation="test")
        finally:
            os.environ.pop("STEER_UNITTEST_LIVE_CATALOG", None)
            import shutil

            shutil.rmtree(live, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
