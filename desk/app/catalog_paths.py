"""Resolve STEER catalog directory (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_STEER_CATALOG = Path("/workspace/steer-catalog")

# Set only by unit tests (see desk/app/tests/test_live_catalog_guard.py).
_UNITTEST_LIVE_CATALOG_ENV = "STEER_UNITTEST_LIVE_CATALOG"


class CatalogRefusalError(ValueError):
    """Portable paths must not touch the live workspace catalog."""


def live_catalog_path() -> Path:
    override = os.environ.get(_UNITTEST_LIVE_CATALOG_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return WORKSPACE_STEER_CATALOG


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


def package_catalog_default(package_root: Path) -> Path:
    """Default catalog beside a portable package (install-catalog.sh location)."""
    return resolve_catalog_path(package_root / "steer-catalog")


def catalog_display_default() -> str:
    return "<package>/steer-catalog"


def touches_live_workspace_catalog(catalog: Path) -> bool:
    """True when the resolved path is the live catalog or anything beneath it."""
    try:
        resolved = resolve_catalog_path(catalog)
        live = live_catalog_path().resolve()
    except OSError:
        return False
    if resolved == live:
        return True
    try:
        resolved.relative_to(live)
        return True
    except ValueError:
        return False


def refuse_live_workspace_catalog(catalog: Path, *, operation: str) -> None:
    """Block portable installs that touch the live Grok catalog tree."""
    if touches_live_workspace_catalog(catalog):
        raise CatalogRefusalError(
            "Refusing %s under the live catalog %s. Pick another directory."
            % (operation, live_catalog_path())
        )


def refuse_implicit_live_server_catalog(catalog: Path) -> Path:
    """Refuse implicit server resolution that lands on or under the live catalog."""
    resolved = resolve_catalog_path(catalog)
    if touches_live_workspace_catalog(resolved):
        raise CatalogRefusalError(
            "Refusing to serve under the live catalog %s. Pick another directory."
            % live_catalog_path()
        )
    return resolved


def catalog_flag_passed_on_cli(argv: list[str] | None) -> bool:
    if not argv:
        return False
    for arg in argv:
        if arg == "--catalog":
            return True
        if arg.startswith("--catalog="):
            return True
    return False
