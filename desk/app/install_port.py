#!/usr/bin/env python3
"""Port / catalog detection for install-desk.sh (testable without bash)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _config_url(host: str, port: int, base_path: str) -> str:
    base = base_path if base_path.startswith("/") else "/" + base_path
    base = base.rstrip("/")
    return "http://%s:%d%s/api/config" % (host, port, base)


def _page_url(host: str, port: int, base_path: str) -> str:
    base = base_path if base_path.startswith("/") else "/" + base_path
    base = base.rstrip("/")
    return "http://%s:%d%s/" % (host, port, base)


def catalog_from_config(host: str, port: int, base_path: str) -> Path | None:
    url = _config_url(host, port, base_path)
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None
    cat = data.get("catalog")
    if isinstance(cat, str) and cat.strip():
        try:
            return Path(cat).resolve()
        except OSError:
            return None
    return None


def _pids_listening_on_port(port: int) -> list[int]:
    pids: list[int] = []
    try:
        out = subprocess.check_output(
            ["ss", "-tlnp"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return pids
    needle = ":%d" % port
    for line in out.splitlines():
        if needle not in line or "pid=" not in line:
            continue
        for chunk in line.split("pid=")[1:]:
            pid_part = chunk.split(",")[0].strip()
            if pid_part.isdigit():
                pids.append(int(pid_part))
    return sorted(set(pids))


def catalog_from_pid(pid: int) -> Path | None:
    try:
        raw = Path("/proc/%d/cmdline" % pid).read_bytes()
    except OSError:
        return None
    args = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
    for i, arg in enumerate(args):
        if arg == "--catalog" and i + 1 < len(args):
            try:
                return Path(args[i + 1]).resolve()
            except OSError:
                return None
        if arg.startswith("--catalog="):
            try:
                return Path(arg.split("=", 1)[1]).resolve()
            except OSError:
                return None
    return None


def listener_catalog(host: str, port: int, base_path: str) -> Path | None:
    from_api = catalog_from_config(host, port, base_path)
    if from_api is not None:
        return from_api
    for pid in _pids_listening_on_port(port):
        cat = catalog_from_pid(pid)
        if cat is not None:
            return cat
    return None


def catalogs_match(left: Path | str, right: Path | str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return False


def page_responds(host: str, port: int, base_path: str) -> bool:
    url = _page_url(host, port, base_path)
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return 200 <= resp.status < 400
    except (OSError, urllib.error.URLError, ValueError):
        return False


def stop_desk_on_port(port: int) -> bool:
    pids = _pids_listening_on_port(port)
    if not pids:
        return True
    ok = True
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            ok = False
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _pids_listening_on_port(port):
            return ok
        time.sleep(0.1)
    for pid in _pids_listening_on_port(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            ok = False
    time.sleep(0.2)
    return ok and not _pids_listening_on_port(port)


def start_desk_background(catalog: Path, log_path: Path | None = None) -> None:
    log = log_path or Path("/tmp/steer-desk.log")
    start_py = catalog / "start.py"
    if not start_py.is_file():
        raise FileNotFoundError("no start.py at %s" % catalog)
    subprocess.Popen(
        [sys.executable, str(start_py)],
        stdout=log.open("a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def wait_for_desk(
    catalog: Path, host: str, port: int, base_path: str, attempts: int = 20
) -> bool:
    for _ in range(attempts):
        if not page_responds(host, port, base_path):
            time.sleep(0.25)
            continue
        listener = listener_catalog(host, port, base_path)
        if listener is not None and catalogs_match(listener, catalog):
            return True
        time.sleep(0.25)
    return False


def ensure_desk(
    catalog: Path, host: str, port: int, base_path: str
) -> tuple[int, str]:
    """Return (exit_code, message). 0 = url printed on stdout path via message."""
    dest = catalog.resolve()
    page = _page_url(host, port, base_path)

    if page_responds(host, port, base_path):
        listener = listener_catalog(host, port, base_path)
        if listener is None:
            return (
                1,
                "Port %d is in use but is not a STEER desk (catalog could not be determined). "
                "Stop the other process or set another port in steer.json."
                % port,
            )
        if not catalogs_match(listener, dest):
            return (
                1,
                "Port %d is already serving a different desk (catalog %s; this install uses %s). "
                "Change port in steer.json or stop the other desk."
                % (port, listener, dest),
            )
        if not stop_desk_on_port(port):
            return (
                1,
                "Restart required: upgraded files on disk but could not stop the review server on port %d. "
                "Stop it manually, then run: python3 %s"
                % (port, dest / "start.py"),
            )
        start_desk_background(dest)
        if wait_for_desk(dest, host, port, base_path):
            return (0, page)
        return (
            1,
            "Restart required: could not start the review server at %s after upgrade. "
            "Run: python3 %s"
            % (page, dest / "start.py"),
        )

    start_py = dest / "start.py"
    if not start_py.is_file():
        return (1, "no start.py at %s" % dest)
    start_desk_background(dest)
    if wait_for_desk(dest, host, port, base_path):
        return (0, page)
    return (1, "server did not answer at %s" % page)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="STEER install port/catalog helpers")
    ap.add_argument("command", choices=["ensure", "listener-catalog"])
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--base-path", default="/steer")
    args = ap.parse_args(argv)

    if args.command == "listener-catalog":
        cat = listener_catalog(args.host, args.port, args.base_path)
        if cat is None:
            return 1
        print(cat)
        return 0

    code, msg = ensure_desk(args.catalog, args.host, args.port, args.base_path)
    if code == 0:
        print(msg)
        return 0
    print(msg, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
