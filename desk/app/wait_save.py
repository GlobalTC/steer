"""Block until a new unprocessed save appears (no webhook required)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from catalog_paths import default_catalog_path


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def unprocessed_save(catalog: Path) -> dict | None:
    latest_path = catalog / "review" / "saves" / "latest.json"
    processed_path = catalog / "review" / "saves" / "processed.json"
    latest = read_json(latest_path)
    if not latest:
        return None
    processed = read_json(processed_path) or {}
    gen = int(latest.get("generation") or 0)
    proc_gen = int(processed.get("generation") or 0)
    if gen > proc_gen:
        return latest
    return None


def wait_for_save(
    catalog: Path,
    *,
    timeout: float,
    poll_interval: float = 0.25,
) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = unprocessed_save(catalog)
        if found is not None:
            return found
        time.sleep(poll_interval)
    return None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Wait for a new unprocessed STEER save")
    ap.add_argument(
        "--catalog",
        default=None,
        help="Catalog directory (default: this start.py folder, not STEER_CATALOG)",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait (default: 300)",
    )
    ap.add_argument(
        "--poll",
        type=float,
        default=0.25,
        help="Poll interval in seconds (default: 0.25)",
    )
    return ap


def main(argv: list[str] | None = None, *, start_py_dir: Path | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    catalog = default_catalog_path(
        args.catalog,
        start_py_dir=start_py_dir,
        honor_env=args.catalog is not None,
    )
    if not catalog.is_dir():
        print(
            json.dumps({"ok": False, "error": "catalog missing", "catalog": str(catalog)}),
            file=sys.stderr,
        )
        return 1
    record = wait_for_save(
        catalog,
        timeout=max(0.0, args.timeout),
        poll_interval=max(0.05, args.poll),
    )
    if record is None:
        print(json.dumps({"ok": False, "reason": "timeout", "catalog": str(catalog)}))
        return 2
    out = {
        "ok": True,
        "catalog": str(catalog),
        "generation": record.get("generation"),
        "saved_at": record.get("saved_at"),
        "asset_id": record.get("asset_id"),
        "production_ready": bool(record.get("production_ready")),
        "event": "ready" if record.get("production_ready") else "save",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
