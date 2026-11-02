"""Resolve STEER catalog directory (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_STEER_CATALOG = Path("/workspace/steer-catalog")


def live_catalog_path() -> Path:
    override = os.environ.get("STEER_LIVE_CATALOG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return WORKSPACE_STEER_CATALOG


class CatalogRefusalError(ValueError):
    """Portable paths must not touch the live workspace catalog."""


def resolve_catalog_path(raw: str | Path) -> Path:
    """Follow symlinks and ``..`` to the real catalog directory."""
    return Path(raw).expanduser().resolve()


def default_catalog_path(
    explicit: str | None = None,
    *,
    start_py_dir: Path | None = None,
    honor_env: bool = True,
) -> Path:
    """Catalog path: explicit flag, start.py folder, optional env, else ./steer-catalog."""
    if explicit:
        return resolve_catalog_path(explicit)
    if start_py_dir is not None:
        return resolve_catalog_path(start_py_dir)
    if honor_env:
        env = os.environ.get("STEER_CATALOG")
        if env:
            return resolve_catalog_path(env)
    return resolve_catalog_path(Path.cwd() / "steer-catalog")


def catalog_display_default() -> str:
    return "./steer-catalog"


def is_live_workspace_catalog(catalog: Path) -> bool:
    try:
        return resolve_catalog_path(catalog) == live_catalog_path().resolve()
    except OSError:
        return False


def refuse_live_workspace_catalog(catalog: Path, *, operation: str) -> None:
    """Always block portable installs and accidental binds to the live Grok catalog."""
    if is_live_workspace_catalog(catalog):
        raise CatalogRefusalError(
            "Refusing %s into the live catalog %s. Pick another directory "
            "(or use Grok Bot install-desk.sh on that host)."
            % (operation, live_catalog_path())
        )


def ensure_server_catalog_allowed(catalog: Path) -> Path:
    """Server may use the live catalog only when the host explicitly allows it."""
    resolved = resolve_catalog_path(catalog)
    if is_live_workspace_catalog(resolved) and os.environ.get("STEER_ALLOW_LIVE_CATALOG") != "1":
        raise CatalogRefusalError(
            "Refusing to serve the live catalog %s. Start via that catalog's start.py "
            "or set STEER_ALLOW_LIVE_CATALOG=1 for Grok Bot install-desk.sh."
            % live_catalog_path()
        )
    return resolved


def live_catalog_allowed_for_start_py(catalog_dir: Path) -> None:
    """start.py from the live catalog may launch the server there."""
    if is_live_workspace_catalog(catalog_dir):
        os.environ["STEER_ALLOW_LIVE_CATALOG"] = "1"
