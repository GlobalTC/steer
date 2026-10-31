"""Resolve free-form voice dictation into anchored mark proposals."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from mark_index import (
    VisibleIndex,
    build_visible_index,
    find_unused_spans,
    map_phrase,
    list_paragraphs,
    paragraph_by_index,
)

ProposalKind = Literal["comment", "replace", "general"]
ANCHOR_CONFIDENCE_MIN = 0.72


@dataclass
class Anchor:
    start: int
    end: int
    text: str


@dataclass
class MarkProposal:
    kind: ProposalKind
    body: str
    confidence: float
    anchor: Optional[Anchor] = None
    excerpt: str = ""
    replace_with: str = ""
    source_clause: str = ""
    anchor_scope: Literal["phrase", "paragraph", "general"] = "general"
    paragraph_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": self.kind,
            "body": self.body,
            "confidence": self.confidence,
            "excerpt": self.excerpt,
            "replace_with": self.replace_with,
            "source_clause": self.source_clause,
            "anchor_scope": self.anchor_scope,
            "paragraph_index": self.paragraph_index,
        }
        if self.anchor:
            d["anchor"] = asdict(self.anchor)
        else:
            d["anchor"] = None
        return d


_ORDINALS = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
    "sixth": 5,
    "seventh": 6,
    "eighth": 7,
    "ninth": 8,
    "tenth": 9,
    "1st": 0,
    "2nd": 1,
    "3rd": 2,
    "4th": 3,
    "5th": 4,
}


def _split_clauses(transcript: str) -> List[str]:
    text = transcript.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.;!?])\s+|\s+and then\s+|\s+also\s+|\s+next\s+", text, flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def _paragraph_ref(clause: str) -> Optional[int]:
    m = re.search(
        r"(?:(\d+)(?:st|nd|rd|th)?|(" + "|".join(_ORDINALS.keys()) + r"))\s+paragraph",
        clause,
        re.I,
    )
    if not m:
        m = re.search(r"paragraph\s+(\d+)", clause, re.I)
        if m:
            return max(0, int(m.group(1)) - 1)
        return None
    if m.group(1):
        return max(0, int(m.group(1)) - 1)
    word = m.group(2).lower()
    return _ORDINALS.get(word)


def _quoted_phrases(clause: str) -> List[str]:
    out: List[str] = []
    for m in re.finditer(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”|‘([^’]+)’', clause):
        out.append(next(g for g in m.groups() if g))
    return out


def _replace_match(clause: str) -> Optional[tuple[str, str]]:
    patterns = [
        r"replace\s+(?:the\s+)?(.+?)\s+with\s+(.+)",
        r"swap\s+(?:the\s+)?(.+?)\s+for\s+(.+)",
        r"change\s+(?:the\s+)?(.+?)\s+to\s+(.+)",
        r"substitute\s+(.+?)\s+for\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, clause, re.I)
        if m:
            return m.group(1).strip(" ."), m.group(2).strip(" .")
    return None


def _cut_phrase(clause: str) -> Optional[str]:
    for pat in (
        r"(?:cut|remove|delete|drop)\s+(?:the\s+)?(?:bit\s+about\s+)?(.+)",
        r"(?:cut|remove|delete|drop)\s+(.+?)\s+from",
    ):
        m = re.search(pat, clause, re.I)
        if m:
            return m.group(1).strip(" .\"'")
    return None


def _subtitle_ref(clause: str) -> bool:
    return bool(re.search(r"\bsubtitle\b|\bheadline\b|\btitle\b", clause, re.I))


def _unique_phrase_confidence(
    src: str, phrase: str, idx: VisibleIndex, para: Optional[int]
) -> float:
    trimmed = " ".join(phrase.split())
    hits = find_unused_spans(idx.vis, idx.used, trimmed)
    if not hits and trimmed != phrase:
        hits = find_unused_spans(idx.vis, idx.used, phrase)
    if not hits:
        return 0.0
    if para is not None:
        p = paragraph_by_index(src, para, idx)
        if p and trimmed.lower() in p.text.lower():
            return 0.88 if len(hits) == 1 else 0.76
    if len(hits) == 1:
        return 0.92
    return 0.55


def resolve_clause_heuristic(
    clause: str, src: str, idx: VisibleIndex
) -> MarkProposal:
    para = _paragraph_ref(clause)
    quotes = _quoted_phrases(clause)
    repl = _replace_match(clause)
    cut = _cut_phrase(clause)

    if repl:
        old_p, new_p = repl
        conf = _unique_phrase_confidence(src, old_p, idx, para)
        mapped = map_phrase(src, old_p, paragraph_index=para, idx=idx)
        if mapped and conf >= ANCHOR_CONFIDENCE_MIN:
            start, end, text = mapped
            return MarkProposal(
                kind="replace",
                body=new_p,
                confidence=conf,
                anchor=Anchor(start, end, text),
                excerpt=text,
                replace_with=new_p,
                source_clause=clause,
                anchor_scope="phrase",
                paragraph_index=para,
            )
        return MarkProposal(
            kind="general",
            body=clause.strip(),
            confidence=0.35,
            source_clause=clause,
            anchor_scope="general",
        )

    target_phrase = quotes[0] if quotes else (cut or "")
    if cut and not quotes:
        note = f"Cut: {cut}"
    elif quotes:
        note = clause.strip()
    else:
        note = clause.strip()

    if _subtitle_ref(clause) and not target_phrase:
        # Title is first # line — treat as low-confidence general unless quoted.
        return MarkProposal(
            kind="general",
            body=clause.strip(),
            confidence=0.4,
            source_clause=clause,
            anchor_scope="general",
        )

    if target_phrase:
        conf = _unique_phrase_confidence(src, target_phrase, idx, para)
        mapped = map_phrase(src, target_phrase, paragraph_index=para, idx=idx)
        if mapped and conf >= ANCHOR_CONFIDENCE_MIN:
            start, end, text = mapped
            kind: ProposalKind = "comment"
            body = note if cut else (note or f"Revise: {target_phrase}")
            if cut:
                body = f"Remove or shorten: {target_phrase}"
            return MarkProposal(
                kind=kind,
                body=body,
                confidence=conf,
                anchor=Anchor(start, end, text),
                excerpt=text,
                source_clause=clause,
                anchor_scope="phrase",
                paragraph_index=para,
            )

    if para is not None and not target_phrase:
        return MarkProposal(
            kind="general",
            body=note,
            confidence=0.35,
            source_clause=clause,
            anchor_scope="general",
        )

    return MarkProposal(
        kind="general",
        body=note,
        confidence=0.3,
        source_clause=clause,
        anchor_scope="general",
    )


def resolve_dictation_heuristic(transcript: str, markdown: str) -> List[MarkProposal]:
    idx = build_visible_index(markdown)
    clauses = _split_clauses(transcript)
    if not clauses and transcript.strip():
        clauses = [transcript.strip()]
    return [resolve_clause_heuristic(c, markdown, idx) for c in clauses]


def load_voice_llm_env(env_path: Optional[str] = None) -> Dict[str, str]:
    path = env_path or os.environ.get("STEER_VOICE_ENV", "")
    if not path:
        root = os.path.dirname(__file__)
        path = os.path.join(root, ".voice.env")
    env: Dict[str, str] = {}
    if not os.path.isfile(path):
        return env
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def voice_llm_configured(env: Optional[Dict[str, str]] = None) -> bool:
    env = env or load_voice_llm_env()
    return bool(env.get("VOICE_RESOLVE_URL"))


def resolve_dictation_llm(
    transcript: str, markdown: str, env: Optional[Dict[str, str]] = None
) -> Optional[List[MarkProposal]]:
    env = env or load_voice_llm_env()
    url = env.get("VOICE_RESOLVE_URL")
    if not url:
        return None
    key = env.get("VOICE_RESOLVE_KEY", "")
    header = env.get("VOICE_RESOLVE_HEADER") or "Authorization"
    paras = list_paragraphs(markdown)
    outline = [
        {"index": p.index, "preview": p.text[:200]}
        for p in paras[:40]
    ]
    payload = {
        "transcript": transcript,
        "outline": outline,
        "markdown_length": len(markdown),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        value = key
        if header.lower() == "authorization" and not key.lower().startswith("bearer "):
            value = "Bearer " + key
        req.add_header(header, value)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None
    items = raw.get("proposals") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return None
    idx = build_visible_index(markdown)
    out: List[MarkProposal] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind not in ("comment", "replace", "general"):
            continue
        body_text = str(item.get("body") or "").strip()
        if not body_text:
            continue
        conf = float(item.get("confidence") or 0.5)
        phrase = item.get("phrase") or item.get("excerpt") or ""
        para = item.get("paragraph_index")
        anchor = None
        excerpt = ""
        replace_with = str(item.get("replace_with") or "")
        if kind in ("comment", "replace") and phrase:
            mapped = map_phrase(
                markdown,
                str(phrase),
                paragraph_index=int(para) if para is not None else None,
                idx=idx,
            )
            if mapped and conf >= ANCHOR_CONFIDENCE_MIN:
                start, end, text = mapped
                anchor = Anchor(start, end, text)
                excerpt = text
            elif conf >= ANCHOR_CONFIDENCE_MIN:
                kind = "general"
                conf = min(conf, 0.4)
        if kind == "general":
            anchor = None
        out.append(
            MarkProposal(
                kind=kind,
                body=body_text,
                confidence=conf,
                anchor=anchor,
                excerpt=excerpt,
                replace_with=replace_with,
                source_clause=str(item.get("source_clause") or ""),
            )
        )
    return out if out else None


def resolve_dictation(
    transcript: str, markdown: str, *, allow_llm: bool = True
) -> List[MarkProposal]:
    if allow_llm:
        from voice_llm import resolve_dictation_primary

        proposals, _used = resolve_dictation_primary(transcript, markdown)
        return proposals
    return resolve_dictation_heuristic(transcript, markdown)


def proposals_to_json(proposals: List[MarkProposal]) -> List[Dict[str, Any]]:
    return [p.to_dict() for p in proposals]


def reanchor_proposal_dicts(
    markdown: str, proposals: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Re-map phrase anchors after earlier accepts changed the markdown."""
    idx = build_visible_index(markdown)
    out: List[Dict[str, Any]] = []
    for raw in proposals:
        if not isinstance(raw, dict):
            out.append({"pid": None, "stale": True})
            continue
        p = dict(raw)
        pid = p.get("_pid") or p.get("pid")
        if pid is not None:
            p["pid"] = pid
            p["_pid"] = pid
        kind = p.get("kind")
        anchor = p.get("anchor")
        if kind in ("comment", "replace") and isinstance(anchor, dict):
            phrase = anchor.get("text") or p.get("excerpt") or ""
            mapped = map_phrase(markdown, str(phrase), idx=idx) if phrase else None
            if mapped:
                start, end, text = mapped
                p["anchor"] = {"start": start, "end": end, "text": text}
                p["excerpt"] = text
                p["anchor_scope"] = "phrase"
            else:
                p["anchor"] = None
                p["excerpt"] = ""
                p["kind"] = "general"
                p["anchor_scope"] = "general"
                p["stale"] = True
        out.append(p)
    return out
