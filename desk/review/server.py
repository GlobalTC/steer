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


def is_parking_stub(asset: dict | None) -> bool:
    if not isinstance(asset, dict):
        return False
    if asset.get("kind") == "desk":
        return True
    if asset.get("id") == "empty-desk":
        return True
    if asset.get("status") == "idle":
        return True
    return False


def spec_is_idle(spec: dict) -> bool:
    asset = find_asset(spec.get("id"))
    if asset is not None:
        return is_parking_stub(asset)
    aid = spec.get("id") or ""
    rel = spec.get("rel") or ""
    return aid == "empty-desk" or Path(rel).stem == "empty-desk"


def public_catalog_asset(asset: dict) -> dict:
    return {
        "id": asset.get("id"),
        "title": asset.get("title"),
        "dek": asset.get("dek"),
        "date": asset.get("date"),
        "status": asset.get("status"),
        "tags": asset.get("tags") or [],
        "kind": asset.get("kind"),
        "body": asset.get("body"),
    }


def load_webhook_env() -> dict:
    env = {}
    if not WEBHOOK_ENV.is_file():
        return env
    for raw in WEBHOOK_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def webhook_configured() -> bool:
    env = load_webhook_env()
    return bool(env.get("WEBHOOK_URL") and env.get("WEBHOOK_KEY"))


def ping_webhook(payload: dict) -> None:
    env = load_webhook_env()
    url = env.get("WEBHOOK_URL")
    key = env.get("WEBHOOK_KEY")
    header = env.get("WEBHOOK_HEADER") or "Authorization"
    if not url or not key:
        return
    value = key
    if header.lower() == "authorization" and not key.lower().startswith("bearer "):
        value = "Bearer " + key
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header(header, value)
    try:
        with urlopen(req, timeout=8) as resp:
            resp.read()
    except (URLError, TimeoutError, OSError) as exc:
        sys.stderr.write("webhook ping failed: %s\n" % exc)


def doc_snapshot() -> dict:
    spec = current_spec()
    latest = read_json(LATEST) or {}
    processed = read_json(PROCESSED) or {}
    markdown = read_asset()
    current_id = spec.get("id")
    same_asset = latest.get("asset_id") == current_id
    return {
        "markdown": markdown,
        "title": title_from_markdown(markdown),
        "saved_at": latest.get("saved_at") if same_asset else None,
        "production_ready": bool(latest.get("production_ready", False)) if same_asset else False,
        "generation": latest.get("generation", 0) if same_asset else 0,
        "mode": latest.get("mode") if same_asset else None,
        "comments": (latest.get("comments") or []) if same_asset else [],
        "asset_mtime": asset_mtime(),
        "processed_generation": processed.get("generation"),
        "webhook_configured": webhook_configured(),
        "id": current_id,
        "idle": spec_is_idle(spec),
    }


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "DraftReview/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == BASE_PATH:
            self.send_response(302)
            self.send_header("Location", BASE_PATH + "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        path = normalize_path(path)

        if path == "/":
            self._serve_file(STATIC / "index.html", "text/html; charset=utf-8")
            return

        if path == "/api/doc":
            self._api_doc()
            return

        if path == "/api/catalog":
            self._api_catalog()
            return

        if path == "/api/events":
            self._api_events()
            return

        if path == "/api/webhook-status":
            self._send_json(200, {"configured": webhook_configured()})
            return

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            self._serve_static(rel)
            return

        self._send(404, b"Not found\n", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        path = normalize_path(path)
        try:
            if path == "/api/save":
                self._api_save()
                return
            if path == "/api/ready":
                self._api_ready()
                return
            if path == "/api/current":
                self._api_current()
                return
            if path == "/api/webhook-config":
                self._api_webhook_config()
                return
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid JSON"})
            return
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send(404, b"Not found\n", "text/plain; charset=utf-8")

    def _serve_static(self, rel: str) -> None:
        if not rel or rel.endswith("/"):
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        # Reject path escape.
        candidate = (STATIC / rel).resolve()
        try:
            candidate.relative_to(STATIC.resolve())
        except ValueError:
            self._send(403, b"Forbidden\n", "text/plain; charset=utf-8")
            return
        if not candidate.is_file():
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        ext = candidate.suffix.lower()
        content_type = MIME.get(ext, "application/octet-stream")
        self._serve_file(candidate, content_type)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        data = path.read_bytes()
        self._send(200, data, content_type)

    def _api_doc(self) -> None:
        self._send_json(200, doc_snapshot())

    def _api_catalog(self) -> None:
        spec = current_spec()
        assets = [public_catalog_asset(a) for a in all_assets() if not is_parking_stub(a)]
        self._send_json(200, {
            "current_id": spec.get("id"),
            "assets": assets,
        })

    def _api_current(self) -> None:
        body = self._read_json_body()
        asset_id = body.get("id") if isinstance(body.get("id"), str) else ""
        asset_id = asset_id.strip()
        if not asset_id:
            self._send_json(400, {"ok": False, "error": "id is required"})
            return
        asset = find_asset(asset_id)
        if asset is None or is_parking_stub(asset):
            self._send_json(404, {"ok": False, "error": "Unknown asset"})
            return
        rel = asset.get("body")
        if not isinstance(rel, str) or not rel:
            self._send_json(404, {"ok": False, "error": "Unknown asset"})
            return
        path = CATALOG / rel
        if not path.is_file():
            self._send_json(404, {"ok": False, "error": "Unknown asset"})
            return
        record = {"id": asset_id, "asset": rel}
        atomic_write_text(
            CURRENT,
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        )
        snap = doc_snapshot()
        payload = {"ok": True, "id": asset_id, "asset": rel}
        payload.update(snap)
        self._send_json(200, payload)
