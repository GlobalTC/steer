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

- **Select and speak:** highlight a phrase or tap a paragraph, then tap **Mic** on the popover. The transcript becomes an anchored comment with the same CriticMarkup shape as typed marks (`via="voice"` metadata; **Voice** badge in the drawer).
- **Free dictation:** tap **Talk through edits**, read the draft aloud, tap **Done**. The server turns the transcript into **proposed** marks showing **confidence** and **scope** (phrase, whole paragraph, or unanchored). Accept or reject each one before it is written. Paragraph-wide proposals appear when a paragraph is named but no exact phrase matches.
- **Speech-to-text:** uses the browser Web Speech API when available; otherwise **server STT** (`MediaRecorder` → `POST /steer/api/transcribe-voice`). Configure `VOICE_STT_URL` in `review/.voice.env` (see `.voice.env.example`). Audio is transcribed in memory and discarded; it is never written to saves.
- **Mark resolution:** local heuristics by default; optional `VOICE_RESOLVE_URL` for an LLM resolver. No default URLs or hardcoded keys.
- **Rewrite agent:** saves with voice marks include `revise_hints` in `review/saves/latest.json` (and on the Save webhook). Steer draft review instructs the agent to preserve spoken wording more literally for `via="voice"` marks listed in `revise_hints.voice_mark_ids`.

Tests:

    python3 -m unittest discover -s review/tests -p 'test_*.py'

QA-only proposal preview (no mic): append `?steer_qa=1` and use `window.__steerInjectVoiceProposals` in the console.

## Paths

- `index.json` — machine list. Start here.
- `assets/<id>.md` — one asset per document.
- `CONSTITUTION.md` — how drafts are reviewed.
- `review/` — live review app. `review/current.json` is the active piece.
