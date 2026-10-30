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

In **Suggesting** mode the desk can capture marks by speech (browser Web Speech API where supported).

- **Select and speak:** highlight a phrase or tap a paragraph, then tap **Mic** on the popover. The transcript becomes an anchored comment with the same CriticMarkup shape as typed marks (`via="voice"` on the mark metadata for a small badge in the drawer).
- **Free dictation:** tap **Talk through edits** at the bottom, read the draft aloud, then **Resolve marks**. The server turns the transcript into **proposed** marks; accept or reject each one before it is written. Instructions that cannot be anchored confidently stay as unanchored general notes — nothing is applied silently.

Speech-to-text and resolution are behind small interfaces (`static/speech.js`, `review/voice_resolve.py`). Optional LLM resolution: copy `review/.voice.env.example` to `review/.voice.env` and set `VOICE_RESOLVE_URL` (and key/header). When unset, heuristic anchoring runs locally. Audio is not stored in saves.

Run resolution tests:

    python3 -m unittest discover -s review/tests -p 'test_*.py'

## Paths

- `index.json` — machine list. Start here.
- `assets/<id>.md` — one asset per document.
- `CONSTITUTION.md` — how drafts are reviewed.
- `review/` — live review app. `review/current.json` is the active piece.
