#!/usr/bin/env python3
"""Assemble Grok Bot skills from _core sources and build steer-skill-portable-<version>.zip."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from zipfile import ZipInfo

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "skills" / "_core"
DESK = ROOT / "desk"
VERSION_FILE = DESK / "app" / "VERSION"
DIST = ROOT / "dist"
PORTABLE_DIR = DIST / "steer-portable"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

GROK = {
    "CATALOG": "/workspace/steer-catalog",
    "START_CMD": "python3 /workspace/steer-catalog/start.py",
    "WAIT_SAVE_CMD": "python3 /workspace/steer-catalog/start.py wait-save --timeout 600",
    "ONBOARDING_REF": "[Steer onboarding](sand-workflow:steer-onboarding)",
    "DRAFT_REVIEW_REF": "[Steer draft review](sand-workflow:steer-draft-review)",
}

ALLOWLIST_FILE = ROOT / "packaging" / "desk-allowlist.txt"


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
    body = substitute(load_core("onboarding-body-grok.md"), mapping)
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
    mapping = dict(GROK)
    mapping["SAVE_WIRE_SECTION"] = substitute(
        load_core("onboarding-save-wire-portable.md"),
        {
            "WAIT_SAVE_CMD": "python3 start.py wait-save --timeout 600",
            "CATALOG": "${STEER_CATALOG:-./steer-catalog}",
        },
    )
    onboarding = substitute(load_core("onboarding-body-portable.md"), mapping)
    draft = load_core("draft-review-body-portable.md")
    return (
        "---\n"
        "name: Steer (portable)\n"
        "description: >-\n"
        "  Human-in-the-loop rewrite desk: install the stock page, mark drafts in\n"
        "  Suggesting, Save, apply CriticMarkup in the source voice. Works without\n"
        "  outbound webhooks (wait-save or user says saved). Ready is not publish.\n"
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


def iter_desk_allowlist() -> list[Path]:
    lines = ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines()
    out: list[Path] = []
    for line in lines:
        rel = line.strip()
        if not rel or rel.startswith("#"):
            continue
        src = DESK / rel
        if not src.is_file():
            raise SystemExit("allowlist missing file: desk/%s" % rel)
        out.append(src)
    return out


def scrub_portable_file(rel: str, data: bytes) -> bytes:
    if rel == "steer.json":
        cfg = json.loads(data.decode("utf-8"))
        cfg.pop("timezone", None)
        cfg.pop("tz_label", None)
        notify = cfg.get("notify")
        if isinstance(notify, list) and notify:
            for item in notify:
                if isinstance(item, dict):
                    item["required"] = False
                    item["why"] = "optional webhook; agent-wait when unset"
        return (json.dumps(cfg, indent=2) + "\n").encode("utf-8")
    if rel == "index.json":
        idx = json.loads(data.decode("utf-8"))
        idx.pop("path", None)
        return (json.dumps(idx, indent=2) + "\n").encode("utf-8")
    if rel in ("README.md", "CONSTITUTION.md"):
        text = data.decode("utf-8")
        text = text.replace("**Grok Bot:**", "Note (Grok Bot hosts):")
        text = text.replace("**Portable:**", "Portable hosts:")
        return text.encode("utf-8")
    if rel == "review/.webhook.env.example":
        text = data.decode("utf-8")
        text = text.replace("/workspace/steer-catalog", "./steer-catalog")
        return text.encode("utf-8")
    return data


def copy_desk_for_zip(dest: Path) -> None:
    desk_dest = dest / "desk"
    if desk_dest.exists():
        shutil.rmtree(desk_dest)
    desk_dest.mkdir(parents=True)
    for src in iter_desk_allowlist():
        rel = src.relative_to(DESK).as_posix()
        target = desk_dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = src.read_bytes()
        target.write_bytes(scrub_portable_file(rel, raw))


def validate_zip_members(names: list[str]) -> list[str]:
    bad: list[str] = []
    for n in names:
        base = Path(n).name
        if base in (".webhook.env", ".voice.env"):
            bad.append(n)
        if base.endswith(".log"):
            bad.append(n)
        if "/saves/" in n.replace("\\", "/") and n.endswith(".json"):
            bad.append(n)
        if "app/tests/" in n.replace("\\", "/"):
            bad.append(n)
    return bad


def write_zip(staging: Path, zip_path: Path) -> list[str]:
    members: list[str] = []
    if zip_path.is_file():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_dir():
                continue
            arc = path.relative_to(staging).as_posix()
            info = ZipInfo(arc)
            info.date_time = FIXED_ZIP_TIME
            info.compress_type = zipfile.ZIP_DEFLATED
            data = path.read_bytes()
            zf.writestr(info, data)
            members.append(arc)
    return members


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
    shutil.copy2(ROOT / "packaging" / "install-catalog.sh", staging / "install-catalog.sh")
    copy_desk_for_zip(staging)
    zip_name = "steer-skill-portable-%s.zip" % version
    zip_path = DIST / zip_name
    members = write_zip(staging, zip_path)
    bad = validate_zip_members(members)
    if bad:
        raise SystemExit("zip contains forbidden paths: %s" % ", ".join(bad))
    return zip_path


def main() -> int:
    write_grok_skills()
    version = read_version()
    zip_path = build_zip(version)
    digest = sha256_file(zip_path)
    print(
        json.dumps(
            {"ok": True, "version": version, "zip": str(zip_path), "sha256": digest}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
