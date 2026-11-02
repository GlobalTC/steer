"""Resolve STEER catalog directory (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path


def grok_workspace_layout() -> bool:
    """True when this host uses the Grok Bot /workspace catalog default."""
    return Path("/workspace").is_dir()


def default_catalog_path(
    explicit: str | None = None,
    *,
    start_py_dir: Path | None = None,
) -> Path:
    """Catalog path: explicit flag/env, then start.py's folder, Grok /workspace, else ./steer-catalog."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("STEER_CATALOG")
    if env:
        return Path(env).expanduser().resolve()
    if start_py_dir is not None:
        return start_py_dir.resolve()
    if grok_workspace_layout():
        return Path("/workspace/steer-catalog").resolve()
    return (Path.cwd() / "steer-catalog").resolve()


def catalog_display_default() -> str:
    """Human-facing default catalog path for portable docs."""
    if grok_workspace_layout():
        return "/workspace/steer-catalog"
    return "./steer-catalog"
