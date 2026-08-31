# Steer writing catalog

This folder is the copy of record. The review loop is the live page, not chat.

On a Grok Bot computer, this directory belongs at `/workspace/steer-catalog`.

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

## Paths

- `index.json` — machine list. Start here.
- `assets/<id>.md` — one asset per document.
- `CONSTITUTION.md` — how drafts are reviewed.
- `review/` — live review app. `review/current.json` is the active piece.
