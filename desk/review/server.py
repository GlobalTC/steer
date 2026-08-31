#!/usr/bin/env python3
"""Local draft-review server. Serves the review UI and writes saves to disk."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

HOST = "127.0.0.1"
PORT = 8766

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT.parent
STATIC = ROOT / "static"
SAVES = ROOT / "saves"
CURRENT = ROOT / "current.json"
LATEST = SAVES / "latest.json"
PROCESSED = SAVES / "processed.json"
WEBHOOK_ENV = ROOT / ".webhook.env"
INDEX = CATALOG / "index.json"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

TITLE_FALLBACK = "Draft"
BASE_PATH = "/steer"


def normalize_path(path: str) -> str:
    """Accept both / and /steer so Tailscale path mapping works."""
    if path == BASE_PATH or path == BASE_PATH + "/":
        return "/"
    prefix = BASE_PATH + "/"
    if path.startswith(prefix):
        rest = path[len(BASE_PATH):]
        return rest if rest else "/"
    return path



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def title_from_markdown(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return TITLE_FALLBACK


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text if text.endswith("\n") or text == "" else text
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".partial", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path):
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def current_spec() -> dict:
    spec = read_json(CURRENT) or {}
    rel = spec.get("asset") or "assets/steer-slop-sample.md"
    return {
        "id": spec.get("id") or Path(rel).stem,
        "asset": CATALOG / rel,
        "rel": rel,
    }


def current_asset() -> Path:
    return current_spec()["asset"]


def read_asset() -> str:
    path = current_asset()
    with path.open(encoding="utf-8") as handle:
        return handle.read()


def asset_mtime() -> int:
    try:
        return current_asset().stat().st_mtime_ns
    except OSError:
        return 0


def load_index() -> dict:
    data = read_json(INDEX)
    return data if isinstance(data, dict) else {}


def all_assets() -> list:
    assets = load_index().get("assets") or []
    return [a for a in assets if isinstance(a, dict) and a.get("id")]


def find_asset(asset_id: str):
    if not asset_id:
        return None
    for asset in all_assets():
        if asset.get("id") == asset_id:
            return asset
    return None
