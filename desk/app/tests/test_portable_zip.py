"""Portable skill zip must not ship secrets or runtime data."""

from __future__ import annotations

import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "scripts" / "build-steer-portable.py"


class TestPortableZip(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        proc = subprocess.run(
            [sys.executable, str(BUILD)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        import json

        info = json.loads(proc.stdout.strip())
        cls.zip_path = Path(info["zip"])

    def test_zip_exists(self) -> None:
        self.assertTrue(self.zip_path.is_file())

    def test_required_entries(self) -> None:
        with zipfile.ZipFile(self.zip_path) as zf:
            names = set(zf.namelist())
        for required in ("SKILL.md", "INSTALL.md", "LICENSE", "desk/start.py", "desk/app/server.py"):
            self.assertIn(required, names)

    def test_no_secrets_or_runtime(self) -> None:
        forbidden_fragments = (
            "review/.webhook.env",
            "review/.voice.env",
            "/saves/latest.json",
            "/saves/processed.json",
            "webhook.log",
            "save-attempts.log",
            "__pycache__",
        )
        with zipfile.ZipFile(self.zip_path) as zf:
            for name in zf.namelist():
                for frag in forbidden_fragments:
                    if frag in name and ".example" not in name:
                        self.fail("forbidden zip member: %s (matched %s)" % (name, frag))


if __name__ == "__main__":
    unittest.main()
