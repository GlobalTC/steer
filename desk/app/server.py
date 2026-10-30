#!/usr/bin/env python3
"""STEER review server: one codebase, many desks.

Code lives in /workspace/steer/app. A desk (catalog) is only data:
  <catalog>/steer.json   per-desk settings (name, base_path, port, notify targets, ...)
  <catalog>/index.json, assets/, brand/ (logos, tutorial.md, figures/)
  <catalog>/review/      runtime: current.json, saves/, .webhook.env, logs

Run:  python3 server.py --catalog /workspace/steer-catalog [--port 8766] [--base-path /steer]
Env:  STEER_CATALOG, STEER_PORT, STEER_BASE_PATH, STEER_HOST override steer.json.
"""

from __future__ import annotations

import json
from email import policy
from email.parser import BytesParser
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
from urllib.error import URLError, HTTPError
import argparse

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
STATIC = APP / "static"
VERSION_FILE = APP / "VERSION"

# Defaults reproduce the live STEER desk. configure() overrides them at start.
HOST = "127.0.0.1"
PORT = 8766
CATALOG = Path("/workspace/steer-catalog")
CONFIG: dict = {}


def _paths() -> None:
    global ROOT, SAVES, CURRENT, LATEST, PROCESSED, WEBHOOK_ENV, INDEX, SAVE_LOG
    global WEBHOOK_LOG, WEBHOOK_STATE, BRAND_DIRS
    ROOT = CATALOG / "review"
    SAVES = ROOT / "saves"
    CURRENT = ROOT / "current.json"
    LATEST = SAVES / "latest.json"
    PROCESSED = SAVES / "processed.json"
    WEBHOOK_ENV = ROOT / ".webhook.env"
    INDEX = CATALOG / "index.json"
    SAVE_LOG = ROOT / "save-attempts.log"
    WEBHOOK_LOG = ROOT / "webhook.log"
    WEBHOOK_STATE = ROOT / "webhook-state.json"
    # Data files served under /static/ when the code dir has no such file.
    BRAND_DIRS = [CATALOG / "brand", ROOT / "static"]


_paths()

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
DEFAULT_ASSET = "assets/steer-slop-sample.md"
DESK_NAME = "STEER"


def app_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0"
    except OSError:
        return "0"


def configure(argv=None) -> None:
    """Catalog folder + port + base path from args, env, then <catalog>/steer.json."""
    global HOST, PORT, CATALOG, CONFIG, BASE_PATH, TITLE_FALLBACK, DEFAULT_ASSET, DESK_NAME
    ap = argparse.ArgumentParser(description="STEER review server")
    ap.add_argument("--catalog", default=os.environ.get("STEER_CATALOG"))
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--base-path", default=None)
    ap.add_argument("--host", default=None)
    args = ap.parse_args(argv)
    CATALOG = Path(args.catalog or "/workspace/steer-catalog").resolve()
    cfg = read_json(CATALOG / "steer.json") or {}
    CONFIG = cfg if isinstance(cfg, dict) else {}
    PORT = int(args.port or os.environ.get("STEER_PORT") or CONFIG.get("port") or 8766)
    HOST = args.host or os.environ.get("STEER_HOST") or CONFIG.get("host") or "127.0.0.1"
    base = args.base_path if args.base_path is not None else os.environ.get("STEER_BASE_PATH")
    if base is None:
        base = CONFIG.get("base_path", "/steer")
    base = "/" + base.strip("/") if base.strip("/") else ""
    BASE_PATH = base
    TITLE_FALLBACK = CONFIG.get("title_fallback") or "Draft"
    DEFAULT_ASSET = CONFIG.get("default_asset") or "assets/steer-slop-sample.md"
    DESK_NAME = CONFIG.get("name") or "STEER"
    _paths()
    voice_rel = CONFIG.get("voice_env") or "review/.voice.env"
    voice_path = (CATALOG / voice_rel).resolve()
    os.environ["STEER_VOICE_ENV"] = str(voice_path)


def normalize_path(path: str) -> str:
    """Accept both / and /steer so Tailscale path mapping works."""
    if not BASE_PATH:
        return path
    if path == BASE_PATH or path == BASE_PATH + "/":
        return "/"
    prefix = BASE_PATH + "/"
    if path.startswith(prefix):
        rest = path[len(BASE_PATH):]
        return rest if rest else "/"
    return path


def parse_multipart_field(
    body: bytes, content_type: str, field_name: str
) -> tuple[bytes, str]:
    """Extract one named field from multipart/form-data (stdlib; Python 3.13+ safe)."""
    header_block = (
        "Content-Type: %s\r\nMIME-Version: 1.0\r\n\r\n" % content_type
    ).encode("latin-1")
    msg = BytesParser(policy=policy.default).parsebytes(header_block + body)
    if not msg.is_multipart():
        raise ValueError("Expected multipart body")
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            payload = b""
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")
        part_type = part.get_content_type() or "application/octet-stream"
        return payload, part_type
    raise ValueError("%s field is required" % field_name)


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


def log_save_attempt(client: str, outcome: str, **fields) -> None:
    """One line per POST /api/save, to stderr and save-attempts.log (2026-10-18)."""
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    extra = " ".join("%s=%s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in fields.items())
    line = "%s save %s client=%s %s" % (stamp, outcome, client, extra)
    sys.stderr.write(line.rstrip() + "\n")
    try:
        with SAVE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip() + "\n")
    except OSError as exc:
        sys.stderr.write("save log write failed: %s\n" % exc)


def read_json(path: Path):
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def current_spec() -> dict:
    spec = read_json(CURRENT) or {}
    rel = spec.get("asset") or DEFAULT_ASSET
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


def load_webhook_env(path: Path | None = None) -> dict:
    env = {}
    path = path or WEBHOOK_ENV
    if not path.is_file():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


# --- Notify targets (2026-10-18 webhook fix) -------------------------------
# Every save and ready is delivered to each target in steer.json "notify"
# (default: one target, the desk's own .webhook.env). Each delivery is retried,
# logged to review/webhook.log and stderr, and its outcome is kept in
# review/webhook-state.json so the page status bar can say who was NOT notified.

_STATE_LOCK = threading.Lock()
RETRY_DELAYS = tuple(
    float(x) for x in (os.environ.get("STEER_RETRY_DELAYS") or "0,3,10,30").split(",") if x.strip()
) or (0,)


def notify_targets() -> list:
    raw = CONFIG.get("notify")
    if not isinstance(raw, list) or not raw:
        raw = [{"name": DESK_NAME, "env": "review/.webhook.env"}]
    out = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        env_rel = item.get("env") or "review/.webhook.env"
        env_path = (CATALOG / env_rel).resolve()
        env = load_webhook_env(env_path)
        out.append({
            "name": str(item["name"]),
            "env_path": env_path,
            "url": env.get("WEBHOOK_URL") or "",
            "key": env.get("WEBHOOK_KEY") or "",
            "header": env.get("WEBHOOK_HEADER") or "Authorization",
            "required": item.get("required", True) is not False,
            "why": item.get("why") or "",
        })
    return out


def webhook_configured() -> bool:
    return any(t["url"] and t["key"] for t in notify_targets())


def _load_state() -> dict:
    data = read_json(WEBHOOK_STATE) if WEBHOOK_STATE.is_file() else None
    return data if isinstance(data, dict) else {}


def _save_state(state: dict) -> None:
    try:
        atomic_write_text(WEBHOOK_STATE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        sys.stderr.write("WEBHOOK state write failed: %s\n" % exc)


def _webhook_log(line: str) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    text = "%s %s" % (stamp, line)
    sys.stderr.write(text + "\n")
    try:
        with WEBHOOK_LOG.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except OSError as exc:
        sys.stderr.write("WEBHOOK log write failed: %s\n" % exc)


def _record(name: str, **fields) -> None:
    with _STATE_LOCK:
        state = _load_state()
        entry = state.get(name) if isinstance(state.get(name), dict) else {}
        entry.update(fields)
        state[name] = entry
        _save_state(state)


def _post_once(target: dict, body: bytes):
    """Returns (ok, http_code, detail). Never raises. Never logs the key."""
    key = target["key"]
    header = target["header"]
    value = key
    if header.lower() == "authorization" and not key.lower().startswith("bearer "):
        value = "Bearer " + key
    req = Request(target["url"], data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header(header, value)
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read(400).decode("utf-8", "replace")
            code = resp.status
    except HTTPError as exc:
        try:
            raw = exc.read(300).decode("utf-8", "replace")
        except Exception:
            raw = ""
        return False, exc.code, ("HTTP %s %s" % (exc.code, raw)).strip()
    except (URLError, TimeoutError, OSError) as exc:
        return False, 0, "network: %s" % exc
    run = ""
    try:
        run = (json.loads(raw) or {}).get("runUuid") or ""
    except Exception:
        pass
    if 200 <= code < 300:
        if '"success":false' in raw.replace(" ", ""):
            return False, code, "receiver said success=false: %s" % raw[:200]
        return True, code, run
    return False, code, "HTTP %s %s" % (code, raw[:200])


def deliver(target: dict, payload: dict) -> bool:
    name = target["name"]
    event = payload.get("event")
    gen = payload.get("generation")
    now = utc_now_iso()
    if not (target["url"] and target["key"]):
        _webhook_log("WEBHOOK NOT SENT target=%s event=%s generation=%s reason=\"not configured (%s)\""
                     % (name, event, gen, target["env_path"]))
        _record(name, ok=False, event=event, generation=gen, at=now, code=0,
                error="not connected: no webhook URL/key in %s" % target["env_path"].name,
                configured=False, pending=payload)
        return False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    detail = ""
    code = 0
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)
        ok, code, detail = _post_once(target, body)
        if ok:
            _webhook_log("webhook ok target=%s event=%s generation=%s http=%s run=%s attempt=%d"
                         % (name, event, gen, code, detail or "-", attempt))
            _record(name, ok=True, event=event, generation=gen, at=utc_now_iso(), code=code,
                    run=detail, error=None, configured=True, pending=None, attempts=attempt)
            return True
        _webhook_log("WEBHOOK FAILED target=%s event=%s generation=%s attempt=%d/%d %s"
                     % (name, event, gen, attempt, len(RETRY_DELAYS), detail))
    _record(name, ok=False, event=event, generation=gen, at=utc_now_iso(), code=code,
            error=detail, configured=True, pending=payload, attempts=len(RETRY_DELAYS))
    return False


def ping_webhook(payload: dict, only: str | None = None) -> None:
    for target in notify_targets():
        if only and target["name"] != only:
            continue
        threading.Thread(target=deliver, args=(target, payload), daemon=True).start()


def notify_summary() -> dict:
    state = _load_state()
    targets = []
    for t in notify_targets():
        last = state.get(t["name"]) if isinstance(state.get(t["name"]), dict) else {}
        configured = bool(t["url"] and t["key"])
        targets.append({
            "name": t["name"],
            "configured": configured,
            "required": t["required"],
            "why": t["why"],
            "ok": last.get("ok"),
            "event": last.get("event"),
            "generation": last.get("generation"),
            "at": last.get("at"),
            "code": last.get("code"),
            "error": last.get("error") if not last.get("ok") else None,
            "pending": bool(last.get("pending")),
        })
    failing = [
        x["name"]
        for x in targets
        if x["required"] and x["ok"] is False
    ]
    return {"healthy": not failing, "not_notified": failing, "targets": targets}


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
        "notify": notify_summary(),
        "id": current_id,
        "idle": spec_is_idle(spec),
    }


def client_config() -> dict:
    return {
        "name": DESK_NAME,
        "base": BASE_PATH,
        "version": app_version(),
        "title_fallback": TITLE_FALLBACK,
        "timezone": CONFIG.get("timezone") or "America/Denver",
        "tz_label": CONFIG.get("tz_label") or "MT",
        "features": CONFIG.get("features") or {"catalog": True, "learn": True},
    }


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _desk_origin_bases() -> list[str]:
    """Allowed Origin / Referer prefixes for this desk (loopback + configured host)."""
    bases: list[str] = []
    hosts = {HOST, "127.0.0.1", "localhost"}
    for host in hosts:
        for scheme in ("http", "https"):
            root = "%s://%s:%d" % (scheme, host, PORT)
            bases.append(root + (BASE_PATH or ""))
            if BASE_PATH:
                bases.append(root + "/")
    return bases


def _post_allowed(handler: BaseHTTPRequestHandler, *, allow_multipart: bool) -> tuple[bool, int, str]:
    """Browser POST CSRF guard: JSON content-type and same-origin Origin/Referer."""
    ct = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if allow_multipart:
        if ct not in ("application/json", "multipart/form-data"):
            return False, 415, "Content-Type must be application/json or multipart/form-data"
    elif ct != "application/json":
        return False, 415, "Content-Type must be application/json"

    origin = handler.headers.get("Origin")
    referer = handler.headers.get("Referer")
    if not origin and not referer:
        addr = handler.client_address[0]
        if addr in ("127.0.0.1", "::1"):
            return True, 0, ""
        return False, 403, "Forbidden"

    allowed_origins = set()
    for host in (HOST, "127.0.0.1", "localhost"):
        for scheme in ("http", "https"):
            allowed_origins.add("%s://%s:%d" % (scheme, host, PORT))

    host_hdr = handler.headers.get("Host")
    if host_hdr:
        for scheme in ("http", "https"):
            allowed_origins.add("%s://%s" % (scheme, host_hdr))
    if origin:
        if origin.rstrip("/") not in {o.rstrip("/") for o in allowed_origins}:
            return False, 403, "Forbidden"
    if referer:
        ref = urlparse(referer)
        ref_origin = "%s://%s" % (ref.scheme, ref.netloc)
        if ref_origin.rstrip("/") not in {o.rstrip("/") for o in allowed_origins}:
            return False, 403, "Forbidden"
    return True, 0, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "DraftReview/1.0"

    def log_message(self, fmt: str, *args) -> None:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        sys.stderr.write("%s %s - %s\n" % (stamp, self.address_string(), fmt % args))

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
        if BASE_PATH and path == BASE_PATH:
            self.send_response(302)
            self.send_header("Location", BASE_PATH + "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        path = normalize_path(path)

        if path == "/":
            self._serve_index()
            return

        if path == "/api/config":
            self._send_json(200, client_config())
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
            summary = notify_summary()
            summary["configured"] = webhook_configured()
            self._send_json(200, summary)
            return

        if path == "/api/voice-config":
            self._api_voice_config()
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
        allow_multipart = path == "/api/transcribe-voice"
        ok_sec, sec_code, sec_msg = _post_allowed(self, allow_multipart=allow_multipart)
        if not ok_sec:
            self._send_json(sec_code, {"ok": False, "error": sec_msg})
            return
        try:
            if path == "/api/save":
                try:
                    self._api_save()
                except json.JSONDecodeError:
                    log_save_attempt(self.address_string(), "rejected", reason="invalid JSON")
                    raise
                except Exception as exc:
                    log_save_attempt(self.address_string(), "error", reason=str(exc))
                    raise
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
            if path == "/api/webhook-test":
                self._api_webhook_test()
                return
            if path == "/api/webhook-retry":
                self._api_webhook_retry()
                return
            if path == "/api/resolve-voice":
                self._api_resolve_voice()
                return
            if path == "/api/reanchor-voice":
                self._api_reanchor_voice()
                return
            if path == "/api/transcribe-voice":
                self._api_transcribe_voice()
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
        # Code first (app/static), then desk data (brand/, legacy review/static).
        candidate = None
        for base in [STATIC] + BRAND_DIRS:
            probe = (base / rel).resolve()
            try:
                probe.relative_to(base.resolve())
            except ValueError:
                self._send(403, b"Forbidden\n", "text/plain; charset=utf-8")
                return
            if probe.is_file():
                candidate = probe
                break
        if candidate is None:
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

    def _serve_index(self) -> None:
        try:
            html = (STATIC / "index.html").read_text(encoding="utf-8")
        except OSError:
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        cfg = client_config()
        html = html.replace("{{BASE}}", BASE_PATH).replace("{{VERSION}}", cfg["version"])
        html = html.replace("{{NAME}}", cfg["name"])
        brand = CONFIG.get("brand") if isinstance(CONFIG.get("brand"), dict) else {}
        html = html.replace("{{LOGO_TOOLBAR}}", brand.get("toolbar_logo") or "steer-mark-toolbar.png")
        fav = brand.get("favicon")
        html = html.replace("{{FAVICON}}", ('  <link rel="icon" href="%s/static/%s">\n' % (BASE_PATH, fav)) if fav else "")
        html = html.replace("{{CONFIG_JSON}}", json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/"))
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def _api_voice_config(self) -> None:
        from voice_llm import host_chat_configured
        from voice_stt import stt_configured

        self._send_json(
            200,
            {
                "browser_stt": True,
                "server_stt_configured": stt_configured(),
                "llm_resolve": host_chat_configured(),
                "transcribe_path": BASE_PATH + "/api/transcribe-voice",
            },
        )

    def _api_transcribe_voice(self) -> None:
        from voice_stt import stt_configured, transcribe_audio

        if not stt_configured():
            self._send_json(
                503,
                {
                    "ok": False,
                    "error": (
                        "Server speech-to-text is not configured. "
                        "Set VOICE_STT_URL in review/.voice.env or steer.json voice_env."
                    ),
                },
            )
            return
        content_type = self.headers.get("Content-Type") or ""
        audio_bytes = b""
        audio_type = "application/octet-stream"
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw_body = self.rfile.read(length) if length else b""
            if content_type.startswith("multipart/form-data"):
                audio_bytes, audio_type = parse_multipart_field(
                    raw_body, content_type, "audio"
                )
            else:
                audio_bytes = raw_body
                audio_type = content_type.split(";")[0].strip() or audio_type
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        try:
            transcript = transcribe_audio(audio_bytes, content_type=audio_type)
        except (RuntimeError, ValueError) as exc:
            self._send_json(502, {"ok": False, "error": str(exc)})
            return
        self._send_json(200, {"ok": True, "transcript": transcript})

    def _api_resolve_voice(self) -> None:
        from voice_llm import resolve_dictation_primary
        from voice_resolve import proposals_to_json

        body = self._read_json_body()
        transcript = body.get("transcript")
        markdown = body.get("markdown")
        if not isinstance(transcript, str) or not transcript.strip():
            self._send_json(400, {"ok": False, "error": "transcript is required"})
            return
        if not isinstance(markdown, str):
            self._send_json(400, {"ok": False, "error": "markdown is required"})
            return
        try:
            proposals, resolver = resolve_dictation_primary(
                transcript.strip(), markdown
            )
        except Exception:
            from voice_resolve import resolve_dictation_heuristic

            proposals = resolve_dictation_heuristic(transcript.strip(), markdown)
            resolver = "heuristic"
        self._send_json(
            200,
            {
                "ok": True,
                "proposals": proposals_to_json(proposals),
                "resolver": resolver,
            },
        )

    def _api_reanchor_voice(self) -> None:
        from voice_resolve import reanchor_proposal_dicts

        body = self._read_json_body()
        markdown = body.get("markdown")
        raw = body.get("proposals")
        if not isinstance(markdown, str):
            self._send_json(400, {"ok": False, "error": "markdown is required"})
            return
        if not isinstance(raw, list):
            self._send_json(400, {"ok": False, "error": "proposals is required"})
            return
        updated = reanchor_proposal_dicts(markdown, raw)
        self._send_json(200, {"ok": True, "proposals": updated})

    def _api_webhook_test(self) -> None:
        """Clearly-marked test ping. Body: {"target": "<name>"} (optional)."""
        body = self._read_json_body()
        only = body.get("target") if isinstance(body.get("target"), str) else None
        names = [t["name"] for t in notify_targets() if not only or t["name"] == only]
        if not names:
            self._send_json(404, {"ok": False, "error": "No such notify target"})
            return
        payload = {
            "event": "test",
            "test": True,
            "note": "TEST ONLY: STEER webhook check. Not a save; nothing to process. Stay quiet.",
            "desk": DESK_NAME,
            "generation": None,
            "production_ready": False,
            "sent_at": utc_now_iso(),
        }
        results = {}
        for t in notify_targets():
            if t["name"] in names:
                results[t["name"]] = deliver(t, payload)
        self._send_json(200, {"ok": all(results.values()), "results": results, "notify": notify_summary()})

    def _api_webhook_retry(self) -> None:
        """Resend the last undelivered save/ready to each target that missed it."""
        state = _load_state()
        sent = {}
        for t in notify_targets():
            last = state.get(t["name"]) if isinstance(state.get(t["name"]), dict) else {}
            pending = last.get("pending")
            if not isinstance(pending, dict) or pending.get("event") == "test":
                continue
            if not t["required"] and not (t["url"] and t["key"]):
                continue
            sent[t["name"]] = deliver(t, pending)
        ok = all(sent.values()) if sent else True
        self._send_json(200, {"ok": ok, "retried": sent, "notify": notify_summary()})

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

    def _api_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = None
        try:
            while True:
                snap = doc_snapshot()
                stamp = (
                    snap.get("asset_mtime"),
                    snap.get("generation"),
                    snap.get("processed_generation"),
                    snap.get("id"),
                    json.dumps(snap.get("notify"), sort_keys=True),
                )
                if stamp != last:
                    last = stamp
                    light = {
                        "generation": snap.get("generation"),
                        "saved_at": snap.get("saved_at"),
                        "asset_mtime": snap.get("asset_mtime"),
                        "processed_generation": snap.get("processed_generation"),
                        "production_ready": snap.get("production_ready"),
                        "id": snap.get("id"),
                        "notify": snap.get("notify"),
                    }
                    chunk = "data: %s\n\n" % json.dumps(light, ensure_ascii=False)
                    self.wfile.write(chunk.encode("utf-8"))
                    self.wfile.flush()
                time.sleep(0.6)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _api_webhook_config(self) -> None:
        body = self._read_json_body()
        url = body.get("url") if isinstance(body.get("url"), str) else ""
        key = body.get("key") if isinstance(body.get("key"), str) else ""
        header = body.get("header") if isinstance(body.get("header"), str) else "Authorization"
        target_name = body.get("target") if isinstance(body.get("target"), str) else ""
        url, key, header = url.strip(), key.strip(), (header or "Authorization").strip()
        target_name = target_name.strip()
        if not url or not key:
            self._send_json(400, {"ok": False, "error": "url and key are required"})
            return
        env_path = WEBHOOK_ENV
        if target_name:
            match = None
            for t in notify_targets():
                if t["name"] == target_name:
                    match = t["env_path"]
                    break
            if match is None:
                self._send_json(404, {"ok": False, "error": "No such notify target"})
                return
            env_path = match
        text_env = (
            "WEBHOOK_URL=%s\nWEBHOOK_KEY=%s\nWEBHOOK_HEADER=%s\n" % (url, key, header)
        )
        atomic_write_text(env_path, text_env)
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass
        self._send_json(200, {"ok": True, "configured": True, "target": target_name or DESK_NAME})

    def _api_save(self) -> None:
        client = self.address_string()
        body = self._read_json_body()
        markdown = body.get("markdown")
        spec = current_spec()
        body_id = body.get("id") if isinstance(body.get("id"), str) else ""
        if not isinstance(markdown, str):
            log_save_attempt(client, "rejected", reason="markdown missing", id=body_id)
            self._send_json(400, {"ok": False, "error": "markdown is required"})
            return
        mode = body.get("mode") if isinstance(body.get("mode"), str) else "viewing"
        comments = body.get("comments") if isinstance(body.get("comments"), list) else []
        info = {"id": body_id, "desk": spec.get("id"), "chars": len(markdown), "marks": len(comments)}
        # Never write one piece's text into another (tab opened before the desk switched).
        if spec_is_idle(spec):
            log_save_attempt(client, "rejected", reason="desk idle", **info)
            self._send_json(409, {"ok": False, "error": "Nothing is on the desk, so there is no piece to save into."})
            return
        if body_id and body_id != spec.get("id"):
            log_save_attempt(client, "rejected", reason="piece mismatch", **info)
            self._send_json(409, {
                "ok": False,
                "error": "This tab has \"%s\" but the desk now has \"%s\". Not saved, so neither piece was overwritten." % (body_id, spec.get("id")),
            })
            return

        previous = read_json(LATEST) or {}
        generation = int(previous.get("generation") or 0) + 1
        saved_at = utc_now_iso()
        record = {
            "saved_at": saved_at,
            "markdown": markdown,
            "mode": mode,
            "comments": comments,
            "production_ready": False,
            "generation": generation,
            "asset_id": spec.get("id"),
        }

        # Article file first (source of truth), then the save record.
        if not markdown.endswith("\n"):
            asset_text = markdown + "\n"
        else:
            asset_text = markdown
        atomic_write_text(current_asset(), asset_text)
        atomic_write_text(
            LATEST,
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        )
        threading.Thread(
            target=ping_webhook,
            args=({
                "event": "save",
                "id": spec.get("id"),
                "generation": generation,
                "saved_at": saved_at,
                "mode": mode,
                "comment_count": len(comments),
                "production_ready": False,
            },),
            daemon=True,
        ).start()
        log_save_attempt(client, "ok", generation=generation, saved_at=saved_at, **info)
        self._send_json(200, {
            "ok": True,
            "id": spec.get("id"),
            "saved_at": saved_at,
            "generation": generation,
            "asset_mtime": asset_mtime(),
        })

    def _api_ready(self) -> None:
        latest = read_json(LATEST)
        if latest is None:
            self._send_json(400, {"ok": False, "error": "Save once before marking ready"})
            return
        latest["production_ready"] = True
        if "markdown" not in latest:
            latest["markdown"] = read_asset()
        atomic_write_text(
            LATEST,
            json.dumps(latest, ensure_ascii=False, indent=2) + "\n",
        )
        threading.Thread(
            target=ping_webhook,
            args=({
                "event": "ready",
                "id": latest.get("asset_id"),
                "generation": latest.get("generation"),
                "saved_at": latest.get("saved_at"),
                "production_ready": True,
            },),
            daemon=True,
        ).start()
        self._send_json(200, {"ok": True})


def main(argv=None) -> int:
    configure(argv)
    SAVES.mkdir(parents=True, exist_ok=True)
    if not current_asset().is_file():
        sys.stderr.write("Article markdown is missing: %s\n" % current_asset())
        return 1
    try:
        server = ThreadedHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        sys.stderr.write(
            "Port %s is already in use on %s. Not killing any process. %s\n"
            % (PORT, HOST, exc)
        )
        return 1
    sys.stderr.write(
        "%s %s review at http://%s:%s%s/\nCatalog: %s\nArticle: %s\nNotify: %s\n"
        % (DESK_NAME, app_version(), HOST, PORT, BASE_PATH, CATALOG, current_asset(),
           ", ".join("%s(%s)" % (t["name"], "on" if t["url"] and t["key"] else "NOT CONNECTED")
                     for t in notify_targets()))
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nStopped.\n")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
