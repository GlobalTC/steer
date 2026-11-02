#!/usr/bin/env python3
"""Assemble Grok Bot skills from _core sources and build steer-skill-portable-<version>.zip."""

from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "skills" / "_core"
DESK = ROOT / "desk"
VERSION_FILE = DESK / "app" / "VERSION"
DIST = ROOT / "dist"
PORTABLE_DIR = DIST / "steer-portable"

GROK = {
    "CATALOG": "/workspace/steer-catalog",
    "START_CMD": "python3 /workspace/steer-catalog/start.py",
    "WAIT_SAVE_CMD": "python3 /workspace/steer-catalog/start.py wait-save --timeout 600",
    "ONBOARDING_REF": "[Steer onboarding](sand-workflow:steer-onboarding)",
    "DRAFT_REVIEW_REF": "[Steer draft review](sand-workflow:steer-draft-review)",
}

PORTABLE = {
    "CATALOG": "${STEER_CATALOG:-./steer-catalog}",
    "START_CMD": "python3 start.py",
    "WAIT_SAVE_CMD": "python3 start.py wait-save --timeout 600",
    "ONBOARDING_REF": "**Steer onboarding** (below)",
    "DRAFT_REVIEW_REF": "**Steer draft review** (below)",
}


def read_version() -> str:
    if VERSION_FILE.is_file():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0"


def substitute(text: str, mapping: dict[str, str]) -> str:
    out = text
    for key, val in mapping.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def load_core(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def grok_draft_review() -> str:
    body = substitute(load_core("draft-review-body.md"), GROK)
    return (
        "---\n"
        "name: Steer draft review\n"
        "description: >-\n"
        "  Use when starting, reviewing, revising, or finishing a draft on the Steer\n"
        "  desk. The live review page is the only review surface. If the catalog or page\n"
        "  is missing, run Steer onboarding first (that installs the stock desk). Never\n"
        "  attach HTML.\n"
        "---\n"
        + body
        + "\n"
    )


def grok_onboarding() -> str:
    mapping = dict(GROK)
    mapping["SAVE_WIRE_SECTION"] = substitute(
        load_core("onboarding-save-wire-grok.md"), GROK
    )
    body = substitute(load_core("onboarding-body.md"), mapping)
    return (
        "---\n"
        "name: Steer onboarding\n"
        "description: >-\n"
        "  Use once when first setting up Steer, when the catalog or review page is\n"
        "  missing, or only if Save later stops waking the desk. Not per document.\n"
        "  Installs the stock desk from the product repo if needed, then wires Save.\n"
        "---\n"
        + body
        + "\n"
    )


def portable_skill() -> str:
    mapping = dict(PORTABLE)
    mapping["SAVE_WIRE_SECTION"] = substitute(
        load_core("onboarding-save-wire-portable.md"), PORTABLE
    )
    onboarding = substitute(load_core("onboarding-body.md"), mapping)
    draft = substitute(load_core("draft-review-body.md"), PORTABLE)
    return (
        "---\n"
        "name: Steer (portable)\n"
        "description: >-\n"
        "  Human-in-the-loop rewrite desk: install the stock page, mark drafts in\n"
        "  Suggesting, Save, apply CriticMarkup in the source voice. Works without\n"
        "  Grok Bot webhooks (wait-save or user says saved). Ready is not publish.\n"
        "---\n"
        + onboarding
        + "\n\n---\n\n"
        + draft
        + "\n"
    )


def write_grok_skills() -> None:
    (ROOT / "skills" / "steer-draft-review" / "SKILL.md").write_text(
        grok_draft_review(), encoding="utf-8"
    )
    (ROOT / "skills" / "steer-onboarding" / "SKILL.md").write_text(
        grok_onboarding(), encoding="utf-8"
    )


SECRET_PATTERNS = [
    re.compile(r"\.webhook\.env$"),
    re.compile(r"\.voice\.env$"),
    re.compile(r"webhook\.env\.example$"),  # allow example
]
ALLOW_EXAMPLE = re.compile(r"\.example$")
RUNTIME_JSON_IN_SAVES = re.compile(r"review/saves/.+\.json$")
FORBIDDEN_NAMES = {
    ".webhook.env",
    ".voice.env",
    "webhook-state.json",
}
FORBIDDEN_SUFFIXES = (".log",)
RUNTIME_DIRS = {"__pycache__", "webhooks"}


def desk_zip_member(rel: str) -> bool:
    parts = Path(rel).parts
    if parts and parts[0] == "desk":
        rel = str(Path(*parts[1:])) if len(parts) > 1 else ""
    if not rel:
        return True
    name = Path(rel).name
    if name in FORBIDDEN_NAMES:
        return False
    if name.endswith(FORBIDDEN_SUFFIXES):
        return False
    if any(part in RUNTIME_DIRS for part in Path(rel).parts):
        return False
    if RUNTIME_JSON_IN_SAVES.match(rel.replace("\\", "/")):
        return False
    if name == ".webhook.env" or name == ".voice.env":
        return False
    return True


def validate_zip_members(names: list[str]) -> list[str]:
    bad: list[str] = []
    for n in names:
        base = Path(n).name
        if base in FORBIDDEN_NAMES and not ALLOW_EXAMPLE.search(n):
            bad.append(n)
        if base.endswith(".log"):
            bad.append(n)
        if "/saves/" in n.replace("\\", "/") and n.endswith(".json"):
            bad.append(n)
        if n.endswith(".webhook.env") and ".example" not in n:
            bad.append(n)
        if n.endswith(".voice.env") and ".example" not in n:
            bad.append(n)
    return bad


def copy_desk_for_zip(dest: Path) -> None:
    desk_dest = dest / "desk"
    if desk_dest.exists():
        shutil.rmtree(desk_dest)
    shutil.copytree(
        DESK,
        desk_dest,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".webhook.env",
            ".voice.env",
            "*.log",
        ),
    )
    saves = dest / "desk" / "review" / "saves"
    if saves.is_dir():
        for p in saves.glob("*.json"):
            p.unlink()


def build_zip(version: str) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    staging = PORTABLE_DIR
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "SKILL.md").write_text(portable_skill(), encoding="utf-8")
    (staging / "LICENSE").write_text((ROOT / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    (staging / "INSTALL.md").write_text(
        (ROOT / "packaging" / "INSTALL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    copy_desk_for_zip(staging)
    zip_name = "steer-skill-portable-%s.zip" % version
    zip_path = DIST / zip_name
    if zip_path.is_file():
        zip_path.unlink()
    members: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_dir():
                continue
            arc = path.relative_to(staging).as_posix()
            members.append(arc)
            zf.write(path, arc)
    bad = validate_zip_members(members)
    if bad:
        raise SystemExit("zip contains forbidden paths: %s" % ", ".join(bad))
    return zip_path


def main() -> int:
    write_grok_skills()
    version = read_version()
    zip_path = build_zip(version)
    print(json.dumps({"ok": True, "version": version, "zip": str(zip_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
