# Steer writing catalog

This folder is the copy of record. The review loop is the live page, not chat.

**Grok Bot:** this catalog usually lives at `/workspace/steer-catalog`. First-run uses repo-root `install-desk.sh` or Steer onboarding (release tarball, not git clone).

**Portable:** install with `install-catalog.sh` from the skill zip into a path outside `/workspace/steer-catalog`.

Review URL: `http://127.0.0.1:<port><base_path>/` from `steer.json` (defaults `8766` and `/steer/`).

Tutorial (sandbox, does not write the catalog): `http://127.0.0.1:8766/steer/?learn=1` — source `TUTORIAL.md`.

Operating law: `CONSTITUTION.md`.

## Run

    python3 start.py

Then open `http://127.0.0.1:8766/steer/`.

## Optional Tailscale Serve

If this computer is on a tailnet, you may publish the desk to that tailnet only (no Funnel):

    tailscale serve --bg --set-path=/steer http://127.0.0.1:8766

That command **adds** the path. Never `tailscale serve reset`. Never Funnel. Localhost stays the product path; Serve is not required to install Steer.

## Voice markup

In **Suggesting** mode the desk can capture marks by speech (keyboard optional; large touch targets).

- **Select and speak:** highlight a phrase or tap a paragraph, then tap **Mic** on the popover. The transcript becomes a normal CriticMarkup comment (same shape as typed marks).
- **Free dictation:** tap **Talk through edits**, read the draft aloud, tap **Done**. Resolution prefers the host **LLM** (Grok Bot: `XAI_API_KEY` or `STEER_LLM_*` / optional `VOICE_RESOLVE_URL` in `review/.voice.env`). If no model is reachable, local heuristics apply. Proposals show **confidence** and **scope** (phrase anchor vs general note). Paragraph names without an exact phrase become **unanchored general notes**—never paragraph-wide anchors. Accept or reject each proposal before it is written.
- **Speech-to-text:** Web Speech API when available; otherwise **server STT** (`MediaRecorder` → `POST /steer/api/transcribe-voice`, configure `VOICE_STT_URL`). Audio is discarded after transcription; never stored in saves.

Tests:

    python3 -m unittest discover -s app/tests -p 'test_*.py'

## Paths

- `index.json` — machine list. Start here.
- `assets/<id>.md` — one asset per document.
- `CONSTITUTION.md` — how drafts are reviewed.
- `steer.json` — desk settings: name, port, base path, logos, who gets notified on Save.
- `brand/` — logos, tutorial text, figures (data).
- `app/` — the STEER app (server + page). Built from one codebase; an update replaces this folder only, never your drafts.
- `review/` — runtime only. `review/current.json` is the active piece; `review/webhook.log` says whether each Save notified the bot.

## License

STEER is released under the [MIT License](../LICENSE) at the repo root. Copyright (c) 2026 Bill French (832Labs).
