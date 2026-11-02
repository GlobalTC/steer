"""Default catalog path resolution."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from catalog_paths import catalog_display_default, default_catalog_path  # noqa: E402


class TestCatalogPaths(unittest.TestCase):
    def test_explicit_flag(self) -> None:
        p = default_catalog_path("/tmp/my-steer")
        self.assertEqual(p, Path("/tmp/my-steer").resolve())

    def test_steer_catalog_env(self) -> None:
        with patch.dict(os.environ, {"STEER_CATALOG": "/tmp/from-env"}, clear=False):
            p = default_catalog_path()
        self.assertEqual(p, Path("/tmp/from-env").resolve())

    def test_start_py_dir(self) -> None:
        anchor = Path("/tmp/anchor-catalog")
        p = default_catalog_path(start_py_dir=anchor)
        self.assertEqual(p, anchor.resolve())

    def test_cwd_default_without_workspace(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STEER_CATALOG", None)
            with patch("catalog_paths.grok_workspace_layout", return_value=False):
                with patch("catalog_paths.Path.cwd", return_value=Path("/home/user/project")):
                    p = default_catalog_path()
        self.assertEqual(p, (Path("/home/user/project") / "steer-catalog").resolve())

    def test_workspace_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STEER_CATALOG", None)
            with patch("catalog_paths.grok_workspace_layout", return_value=True):
                p = default_catalog_path()
        self.assertEqual(p, Path("/workspace/steer-catalog").resolve())

    def test_display_default_on_workspace_host(self) -> None:
        with patch("catalog_paths.grok_workspace_layout", return_value=True):
            self.assertEqual(catalog_display_default(), "/workspace/steer-catalog")

    def test_display_default_elsewhere(self) -> None:
        with patch("catalog_paths.grok_workspace_layout", return_value=False):
            self.assertEqual(catalog_display_default(), "./steer-catalog")


if __name__ == "__main__":
    unittest.main()
