"""Portable skill zip must not ship secrets or runtime data."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "scripts" / "build-steer-portable.py"


def run_build() -> dict:
    proc = subprocess.run(
        [sys.executable, str(BUILD)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout.strip())


class TestPortableZip(unittest.TestCase):
    def test_zip_reproducible_sha256(self) -> None:
        first = run_build()
        second = run_build()
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertTrue(first["sha256"])

    def test_required_entries(self) -> None:
        info = run_build()
        zip_path = Path(info["zip"])
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
        for required in (
            "SKILL.md",
            "INSTALL.md",
            "LICENSE",
            "install-catalog.sh",
            "desk/start.py",
            "desk/app/server.py",
            "desk/app/wait_save.py",
        ):
            self.assertIn(required, names)

    def test_no_secrets_runtime_or_tests(self) -> None:
        info = run_build()
        zip_path = Path(info["zip"])
        forbidden_fragments = (
            "review/.webhook.env",
            "review/.voice.env",
            "/saves/latest.json",
            "/saves/processed.json",
            "webhook.log",
            "app/tests/",
            "__pycache__",
        )
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                for frag in forbidden_fragments:
                    if frag in name and ".example" not in name:
                        self.fail("forbidden zip member: %s (matched %s)" % (name, frag))

    def test_portable_scrub_and_no_network_install_doc(self) -> None:
        info = run_build()
        zip_path = Path(info["zip"])
        with zipfile.ZipFile(zip_path) as zf:
            install = zf.read("INSTALL.md").decode("utf-8")
            steer = json.loads(zf.read("desk/steer.json").decode("utf-8"))
            index = json.loads(zf.read("desk/index.json").decode("utf-8"))
            skill = zf.read("SKILL.md").decode("utf-8")
        self.assertIn("install-catalog.sh", install)
        self.assertNotIn("curl", install.lower())
        self.assertNotIn("path", index)
        self.assertNotIn("timezone", steer)
        self.assertNotIn("Grok Bot", skill)
        notify = steer.get("notify") or []
        if notify:
            self.assertFalse(notify[0].get("required"))

    def test_grok_onboarding_pinned_and_guards(self) -> None:
        run_build()
        text = (ROOT / "skills" / "steer-onboarding" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("v2026.11.02-1/install-desk.sh", text)
        self.assertIn("app code lives outside the catalog", text)
        self.assertIn("Create a second save-ping on another bot", text)
        self.assertNotIn("GlobalTC/steer/main/install-desk.sh", text)


if __name__ == "__main__":
    unittest.main()
