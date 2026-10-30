"""Server-side speech-to-text via configurable HTTP provider."""

from __future__ import annotations

import json
import mimetypes
import uuid
from typing import Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_resolve import load_voice_llm_env

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def stt_configured(env: Optional[Dict[str, str]] = None) -> bool:
    env = env or load_voice_llm_env()
    return bool(env.get("VOICE_STT_URL"))


def _auth_header(env: Dict[str, str]) -> Tuple[str, str]:
    key = env.get("VOICE_STT_KEY", "")
    header = env.get("VOICE_STT_HEADER") or "Authorization"
    if not key:
        return header, ""
    value = key
    if header.lower() == "authorization" and not key.lower().startswith("bearer "):
        value = "Bearer " + key
    return header, value


def _encode_multipart(
    fields: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]]
) -> Tuple[bytes, str]:
    boundary = "----SteerVoice" + uuid.uuid4().hex
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        lines.append(value.encode("utf-8"))
        lines.append(b"\r\n")
    for name, (filename, data, content_type) in files.items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        lines.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        lines.append(data)
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    body = b"".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def transcribe_audio(
    audio_bytes: bytes,
    *,
    content_type: str = "application/octet-stream",
    env: Optional[Dict[str, str]] = None,
) -> str:
    env = env or load_voice_llm_env()
    url = env.get("VOICE_STT_URL")
    if not url:
        raise RuntimeError(
            "Server speech-to-text is not configured. "
            "Set VOICE_STT_URL in review/.voice.env."
        )
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("Audio clip is too large.")
    if not audio_bytes:
        raise ValueError("Empty audio.")

    mode = (env.get("VOICE_STT_MODE") or "multipart").strip().lower()
    header_name, header_value = _auth_header(env)

    if mode == "json":
        import base64

        payload = {
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "content_type": content_type,
        }
        body = json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
    else:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".webm"
        filename = "clip" + ext
        body, ct = _encode_multipart(
            {},
            {"audio": (filename, audio_bytes, content_type.split(";")[0].strip())},
        )
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", ct)

    if header_value:
        req.add_header(header_name, header_value)

    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError("Transcription provider error: %s" % detail) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Transcription request failed.") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Transcription provider returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Transcription provider returned invalid JSON.")
    text = data.get("transcript") or data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Transcription provider returned no transcript.")
    return text.strip()
