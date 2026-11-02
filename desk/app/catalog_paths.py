"""Resolve STEER catalog directory (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_STEER_CATALOG = Path("/workspace/steer-catalog")


class CatalogRefusalError(ValueError):
    """Portable install or implicit default must not touch a live catalog."""


def default_catalog_path(
    explicit: str | None = None,
    *,
    start_py_dir: Path | None = None,
    honor_env: bool = True,
) -> Path:
    """Catalog path: explicit flag, start.py folder, optional env, else ./steer-catalog."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    if start_py_dir is not None:
        return start_py_dir.resolve()
    if honor_env:
        env = os.environ.get("STEER_CATALOG")
        if env:
            return Path(env).expanduser().resolve()
    return (Path.cwd() / "steer-catalog").resolve()


def catalog_display_default() -> str:
    return "./steer-catalog"


def is_workspace_steer_catalog(catalog: Path) -> bool:
    try:
        return catalog.resolve() == WORKSPACE_STEER_CATALOG.resolve()
    except OSError:
        return False


def refuse_portable_workspace_install(catalog: Path, *, steer_catalog_env: str | None) -> None:
    """Block portable installs that would land in the live Grok catalog by accident."""
    if steer_catalog_env is not None and steer_catalog_env.strip():
        return
    if is_workspace_steer_catalog(catalog):
        raise CatalogRefusalError(
            "Refusing to install into /workspace/steer-catalog without an explicit "
            "STEER_CATALOG. Pick another directory for portable STEER."
        )
