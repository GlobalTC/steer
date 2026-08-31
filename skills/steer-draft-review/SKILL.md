---
name: Steer draft review
description: >-
  Use when starting, reviewing, revising, or finishing a draft on the Steer
  desk. The live review page is the only review surface. If the catalog or page
  is missing, run Steer onboarding first (that installs the stock desk). Never
  attach HTML.
---
# Steer draft review

This is the central loop for every draft on the Steer desk, not a special case.

Steer is a rewrite desk, not a writer. The human (or the dropping agent) stays the author. Marks are the spec. Ready is not publish.

If Save does not wake Steer, the catalog is missing, the review server is missing, or this is a fresh Steer, run [Steer onboarding](sand-workflow:steer-onboarding) first. That installs the stock desk from `https://github.com/GlobalTC/steer` when needed, starts the page, and wires Save. Do not invent a poll. Do not skip it.

## Surfaces

- **Catalog** is the copy of record at `/workspace/steer-catalog`: one asset per document, markdown body in `assets/<id>.md`. Steer writes. Other assistants read.
- **Review page** is the only review surface: Viewing, Editing, Suggesting. Suggesting writes CriticMarkup (`{>>comment<<}`, `{~~old~>new~~}`, `{++ ++}`, `{-- --}`, `{== ==}` plus `id` / `by` / `at`).
- **Product URL** is the agent-computer preview: `http://127.0.0.1:8766/steer/` (Learn sandbox: `http://127.0.0.1:8766/steer/?learn=1`).
- **Optional Tailscale Serve** is a supported feature, not a dependency. If this computer is on a tailnet, publish the desk tailnet-only with `tailscale serve --bg --set-path=/steer http://127.0.0.1:8766`. That appends `/steer`; it does not replace other paths. Operators may then use `https://<node-magicdns>/steer/`. Never Funnel. Never `tailscale serve reset`. Never hardcode a MagicDNS hostname as the product URL.
- **Save** writes the asset and POSTs the webhook so Steer wakes. The open tab live-updates when the rewrite lands, unless it has unsaved edits.
- Do **not** attach an `.html` file in chat. Do **not** paste the full draft into chat when the page will do.
- Do **not** write another product's catalog, port, or webhook env.

## Start a draft

1. If `/workspace/steer-catalog` or `review/server.py` is missing, or `http://127.0.0.1:8766/steer/` does not answer, run [Steer onboarding](sand-workflow:steer-onboarding) and stop until the page is up.
2. Write the markdown to the Steer catalog asset. Register it in `index.json` (`status: draft`, `text_status: full`).
3. Point the review page at that asset (`review/current.json`).
4. Confirm the review page answers (`curl -sS -m 2 http://127.0.0.1:8766/steer/`). If it does not, start `python3 /workspace/steer-catalog/start.py` so port 8766 is listening. Do not send a spinning link.
5. Send the localhost review URL, not a file. If Serve `/steer` is configured, probe the tailnet URL too and you MAY also send that as a convenience for operators on the tailnet. One sentence on what to do: mark up, then Save. Do not require Tailscale.

## While it is in review

1. On Save (webhook ping), read `review/saves/latest.json` and `review/saves/processed.json` under `/workspace/steer-catalog`.
2. If generation/`saved_at` already processed, stay quiet.
3. If `production_ready`, treat the draft as done: update catalog status, ask what to do with it (leave, publish, another pass). Never delete the save-ping routine.
4. Otherwise apply CriticMarkup in the **source document's** voice: comments become revisions, substitutions/insertions/deletions apply, strip the markers after they are handled.
5. Write the revised markdown back to the **asset**. The review page reads the asset, so a live tab should update.
6. Record the processed generation so the same Save is not replayed.
7. Recap the changes in a sentence or two and keep the same review URL.

A stale tab that Saves will overwrite a rewrite. If that happens, re-apply any still-valid marks and tell them to let the page update before the next Save.

If the review page is down, take the same marks in chat and apply them the same way. Still do not dump the full draft when a recap will do.

## Done

Ready means the asset is shippable text. Publishing is a separate, explicit ask. Point a publisher at the asset path. Do not invent URLs.

## Voice

Match the source document. Do not impose a house style. Do not write as a particular person unless the source already is that person. Do not lecture the draft back. When the source is AI-generated, treat the human marks as the spec: remove slop, keep load-bearing claims, make obtuse lines readable, stop when they say it is ready.

## Never

- Become the author. Do not draft original essays on this desk unless asked to load someone else's text.
- Redesign, restyle, or rewrite the review app. If the desk is missing, install the stock copy from the product repo via onboarding. That is first-run, not product-engineering chat.
- Minute-poll, keepalive cron, or a webhook key form on the review page.
- Name a specific person in the save-ping prompt.
- Funnel the review page, or run `tailscale serve reset`.
