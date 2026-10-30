"""Host LLM resolver for voice dictation (OpenAI-compatible chat API)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from voice_resolve import (
    ANCHOR_CONFIDENCE_MIN,
    Anchor,
    MarkProposal,
    build_visible_index,
    list_paragraphs,
    load_voice_llm_env,
    map_phrase,
    voice_llm_configured,
    resolve_dictation_llm,
)

SYSTEM_PROMPT = """You resolve spoken edit instructions on a markdown draft into mark proposals.
Return ONLY JSON: {"proposals": [{"kind":"comment"|"replace"|"general","body":"...","confidence":0.0-1.0,"phrase":"optional exact substring from draft","replace_with":"for replace","source_clause":"..."}]}
Rules: anchor only when phrase is an exact unique substring. If only a paragraph is named with no exact phrase, use kind general. Never invent phrases."""


def _read_env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def host_chat_configured(env: Optional[Dict[str, str]] = None) -> bool:
    if voice_llm_configured(env):
        return True
    key = _resolve_api_key(env)
    return bool(key and _resolve_base_url(env))


def _resolve_api_key(env: Optional[Dict[str, str]] = None) -> str:
    env = env or load_voice_llm_env()
    for name in (
        "STEER_LLM_API_KEY",
        "VOICE_LLM_API_KEY",
        "XAI_API_KEY",
        "OPENAI_API_KEY",
        "API_KEY",
    ):
        val = env.get(name) or _read_env(name)
        if val:
            return val
    return ""


def _resolve_base_url(env: Optional[Dict[str, str]] = None) -> str:
    env = env or load_voice_llm_env()
    explicit = env.get("STEER_LLM_BASE_URL") or _read_env("STEER_LLM_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    if env.get("XAI_API_KEY") or _read_env("XAI_API_KEY"):
        return "https://api.x.ai/v1"
    if env.get("OPENAI_API_KEY") or _read_env("OPENAI_API_KEY"):
        return "https://api.openai.com/v1"
    return ""


def _resolve_model(env: Optional[Dict[str, str]] = None) -> str:
    env = env or load_voice_llm_env()
    return (
        env.get("STEER_LLM_MODEL")
        or _read_env("STEER_LLM_MODEL")
        or env.get("VOICE_LLM_MODEL")
        or _read_env("VOICE_LLM_MODEL")
        or "grok-2-latest"
    )


def _chat_completions_url(base: str) -> str:
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _proposals_from_llm_items(
    items: List[Any], markdown: str
) -> List[MarkProposal]:
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
        replace_with = str(item.get("replace_with") or "")
        anchor = None
        excerpt = ""
        scope = "general"
        if kind in ("comment", "replace") and phrase:
            mapped = map_phrase(markdown, str(phrase), idx=idx)
            if mapped and conf >= ANCHOR_CONFIDENCE_MIN:
                start, end, text = mapped
                anchor = Anchor(start, end, text)
                excerpt = text
                scope = "phrase"
            else:
                kind = "general"
                conf = min(conf, 0.4)
                anchor = None
        if kind == "general":
            anchor = None
            scope = "general"
        out.append(
            MarkProposal(
                kind=kind,
                body=body_text,
                confidence=conf,
                anchor=anchor,
                excerpt=excerpt,
                replace_with=replace_with,
                source_clause=str(item.get("source_clause") or ""),
                anchor_scope=scope,
                paragraph_index=None,
            )
        )
    return out


def resolve_dictation_host_chat(
    transcript: str, markdown: str, env: Optional[Dict[str, str]] = None
) -> Optional[List[MarkProposal]]:
    env = env or load_voice_llm_env()
    base = _resolve_base_url(env)
    key = _resolve_api_key(env)
    if not base or not key:
        return None
    paras = list_paragraphs(markdown)
    outline = [{"index": p.index, "preview": p.text[:200]} for p in paras[:40]]
    user_msg = json.dumps(
        {
            "transcript": transcript,
            "outline": outline,
            "markdown_excerpt": markdown[:8000],
        },
        ensure_ascii=False,
    )
    payload = {
        "model": _resolve_model(env),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
    }
    req = Request(
        _chat_completions_url(base),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    try:
        with urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not choices:
        return None
    content = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(content, str):
        return None
    parsed = _extract_json(content)
    if not parsed:
        return None
    items = parsed.get("proposals")
    if not isinstance(items, list) or not items:
        return None
    proposals = _proposals_from_llm_items(items, markdown)
    return proposals if proposals else None


def resolve_dictation_primary(
    transcript: str, markdown: str, env: Optional[Dict[str, str]] = None
) -> tuple[List[MarkProposal], str]:
    """Returns (proposals, resolver_used: llm|heuristic)."""
    env = env or load_voice_llm_env()
    if voice_llm_configured(env):
        llm = resolve_dictation_llm(transcript, markdown, env)
        if llm:
            return llm, "llm"
    if host_chat_configured(env):
        chat = resolve_dictation_host_chat(transcript, markdown, env)
        if chat:
            return chat, "llm"
    from voice_resolve import resolve_dictation_heuristic

    return resolve_dictation_heuristic(transcript, markdown), "heuristic"
