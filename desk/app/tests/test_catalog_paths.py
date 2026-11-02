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
    refuse_portable_workspace_install,
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

    def test_not_implicit_workspace_on_this_host(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STEER_CATALOG", None)
            p = default_catalog_path()
        if Path("/workspace/steer-catalog").is_dir():
            self.assertNotEqual(p, Path("/workspace/steer-catalog").resolve())

    def test_display_default(self) -> None:
        self.assertEqual(catalog_display_default(), "./steer-catalog")

    def test_refuse_implicit_workspace_install(self) -> None:
        with self.assertRaises(CatalogRefusalError):
            refuse_portable_workspace_install(
                Path("/workspace/steer-catalog"),
                steer_catalog_env=None,
            )

    def test_allow_explicit_workspace_env(self) -> None:
        refuse_portable_workspace_install(
            Path("/workspace/steer-catalog"),
            steer_catalog_env="/workspace/steer-catalog",
        )


if __name__ == "__main__":
    unittest.main()
