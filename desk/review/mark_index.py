"""Map rendered-visible text back to markdown source offsets (CriticMarkup-aware)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class VisibleIndex:
    vis: str
    map: List[int]
    used: List[bool]


@dataclass(frozen=True)
class ParagraphSpan:
    index: int  # 0-based among body paragraphs
    start: int  # source offset inclusive
    end: int  # source offset exclusive
    text: str  # visible text in paragraph


def build_visible_index(src: str) -> VisibleIndex:
    vis: List[str] = []
    mapping: List[int] = []
    used: List[bool] = []
    i = 0
    cm_depth = 0
    n = len(src)

    def starts(s: str) -> bool:
        return src[i : i + len(s)] == s

    while i < n:
        if starts("{id="):
            brace = src.find("}", i)
            if brace != -1:
                i = brace + 1
                continue
        if starts("{>>"):
            cend = src.find("<<}", i)
            if cend != -1:
                i = cend + 3
                continue
        if starts("{==") or starts("{++") or starts("{--") or starts("{~~"):
            cm_depth += 1
            i += 3
            continue
        if starts("==}") or starts("++}") or starts("--}") or starts("~~}"):
            cm_depth = max(0, cm_depth - 1)
            i += 3
            continue
        if starts("~>") and cm_depth > 0:
            i += 2
            continue
        if (i == 0 or src[i - 1] == "\n") and src[i] == "#":
            while i < n and src[i] == "#":
                i += 1
            if i < n and src[i] == " ":
                i += 1
            continue
        if src[i] == "\\" and i + 1 < n:
            i += 1
            vis.append(src[i])
            mapping.append(i)
            used.append(cm_depth > 0)
            i += 1
            continue
        if starts("**") or starts("__"):
            i += 2
            continue
        ch = src[i]
        if ch in "*_`":
            i += 1
            continue
        vis.append(ch)
        mapping.append(i)
        used.append(cm_depth > 0)
        i += 1

    return VisibleIndex("".join(vis), mapping, used)


def find_unused_spans(
    vis: str, used: List[bool], needle: str
) -> List[int]:
    hits: List[int] = []
    if not needle:
        return hits
    pos = 0
    while pos <= len(vis) - len(needle):
        at = vis.find(needle, pos)
        if at < 0:
            break
        blocked = any(used[at + k] for k in range(len(needle)))
        if not blocked:
            hits.append(at)
        pos = at + 1
    return hits


def vis_block_range(vis: str, index: int) -> Tuple[int, int]:
    a = vis.rfind("\n\n", 0, index)
    a = 0 if a == -1 else a + 2
    b = vis.find("\n\n", index)
    b = len(vis) if b == -1 else b
    return a, b


def expand_markup(src: str, start: int, end: int) -> Tuple[int, int]:
    pairs = ("**", "__", "*", "_", "`")
    for w in pairs:
        if start >= len(w) and src[start - len(w) : start] == w:
            if w in src[start:end]:
                start -= len(w)
        if src[end : end + len(w)] == w:
            if w in src[start:end]:
                end += len(w)
    return start, end


def map_phrase(
    src: str,
    phrase: str,
    *,
    paragraph_index: Optional[int] = None,
    idx: Optional[VisibleIndex] = None,
) -> Optional[Tuple[int, int, str]]:
    """Return (start, end, text) in source, or None if not mappable."""
    if idx is None:
        idx = build_visible_index(src)
    raw = phrase
    trimmed = " ".join(phrase.split())
    needle = raw
    hits = find_unused_spans(idx.vis, idx.used, raw)
    if not hits and trimmed and trimmed != raw:
        needle = trimmed
        hits = find_unused_spans(idx.vis, idx.used, trimmed)
    if not hits and trimmed:
        alt = trimmed.replace("\n", "\n\n")
        hits = find_unused_spans(idx.vis, idx.used, alt)
        if hits:
            needle = alt
    if not hits:
        return None

    if paragraph_index is not None:
        paras = list_paragraphs(src, idx)
        if 0 <= paragraph_index < len(paras):
            p = paras[paragraph_index]
            p_start_vis = idx.vis.find(p.text[: min(20, len(p.text))])
            if p_start_vis >= 0:
                filtered = [
                    h
                    for h in hits
                    if p_start_vis <= h < p_start_vis + len(p.text) + 2
                ]
                if filtered:
                    hits = filtered

    if len(hits) > 1 and paragraph_index is None:
        # Prefer first hit when ambiguous — caller should lower confidence.
        pass

    at = hits[0]
    if at >= len(idx.map):
        return None
    src_start = idx.map[at]
    last_vis = at + len(needle) - 1
    if last_vis >= len(idx.map):
        return None
    src_end = idx.map[last_vis] + 1
    start, end = expand_markup(src, src_start, src_end)
    return start, end, src[start:end]


def list_paragraphs(src: str, idx: Optional[VisibleIndex] = None) -> List[ParagraphSpan]:
    if idx is None:
        idx = build_visible_index(src)
    vis = idx.vis
    spans: List[ParagraphSpan] = []
    start = 0
    para_num = 0
    while start <= len(vis):
        end = vis.find("\n\n", start)
        if end == -1:
            end = len(vis)
        block = vis[start:end].strip()
        if block:
            # Map visible start to source
            if start < len(idx.map):
                src_start = idx.map[start]
                last = min(start + len(block) - 1, len(idx.map) - 1)
                src_end = idx.map[last] + 1
                spans.append(
                    ParagraphSpan(
                        index=para_num,
                        start=src_start,
                        end=src_end,
                        text=block,
                    )
                )
                para_num += 1
        if end >= len(vis):
            break
        start = end + 2
    return spans


def paragraph_by_index(src: str, n: int, idx: Optional[VisibleIndex] = None) -> Optional[ParagraphSpan]:
    paras = list_paragraphs(src, idx)
    if n < 0 or n >= len(paras):
        return None
    return paras[n]
