# Steer writing catalog

This folder is the copy of record. The review loop is the live page, not chat.

On a Grok Bot computer, this directory belongs at `/workspace/steer-catalog`.

If that path is missing, first-run installs this folder from `https://github.com/GlobalTC/steer` (see `install-desk.sh` at the repo root, or Steer onboarding). Do not git clone. Do not redesign the page.

Live review (product path): `http://127.0.0.1:8766/steer/`

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

    python3 -m unittest discover -s review/tests -p 'test_*.py'

## Paths

- `index.json` — machine list. Start here.
- `assets/<id>.md` — one asset per document.
- `CONSTITUTION.md` — how drafts are reviewed.
- `review/` — live review app. `review/current.json` is the active piece.
