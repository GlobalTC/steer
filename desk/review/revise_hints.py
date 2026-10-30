"""Hints for the rewrite agent bundled with saves."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

VOICE_MARKS_LITERAL = (
    'Marks tagged via="voice" were spoken by the reviewer. When applying those '
    "marks, preserve the reviewer's spoken wording from the mark note more "
    "literally—do not polish, expand, or replace with generic editorial advice."
)


def revise_hints_from_comments(comments: List[Any]) -> Optional[Dict[str, Any]]:
    voice = [
        c
        for c in comments
        if isinstance(c, dict) and c.get("via") == "voice"
    ]
    if not voice:
        return None
    ids = [c.get("id") for c in voice if c.get("id")]
    return {
        "voice_marks_literal": VOICE_MARKS_LITERAL,
        "voice_mark_ids": ids,
        "voice_mark_count": len(voice),
    }
