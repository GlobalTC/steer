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

If the catalog or review page is missing, or this is a fresh Steer, run [Steer onboarding](sand-workflow:steer-onboarding) first. That installs the stock desk from `https://github.com/GlobalTC/steer` when needed and starts the page. Do not invent a minute-poll. Do not skip onboarding.

## Surfaces

- **Catalog** is the copy of record at `/workspace/steer-catalog`: one asset per document, markdown body in `assets/<id>.md`. Steer writes. Other assistants read.
- **Review page** is the only review surface: Viewing, Editing, Suggesting. Suggesting creates **Comment** and **Replace** marks (`{==phrase==}{>>comment<<}` and `{~~old~>new~~}` plus `id` / `by` / `at`). Insert, delete, and highlight markup (`{++ ++}`, `{-- --}`, `{== ==}` alone) are Editing-mode raw markup only.
- **Voice markup (optional):** In Suggesting, **Talk through edits** resolves dictation into proposed marks (accept/reject each). **Mic** on the selection popover adds a comment immediately. LLM resolution uses the host `XAI_API_KEY` or `STEER_LLM_*` / optional `VOICE_RESOLVE_URL` in `review/.voice.env`; Web Speech or server `VOICE_STT_*` for STT.
- **Product URL** is the local preview: `http://127.0.0.1:8766/steer/` (Learn sandbox: `http://127.0.0.1:8766/steer/?learn=1`). Read **port** and **base_path** from `steer.json`.
- **Optional Tailscale Serve** is supported, not required. If this computer is on a tailnet, you MAY publish the desk tailnet-only with `tailscale serve --bg --set-path=/steer http://127.0.0.1:8766`. Never Funnel. Never `tailscale serve reset`. If Serve is not configured, localhost is enough.
- **Save** writes the asset and records `review/saves/latest.json`. When a webhook is configured, Save also POSTs so the host agent wakes. Without a webhook, use **no-webhook mode** (below).
- Do **not** attach an `.html` file in chat. Do **not** paste the full draft into chat when the page will do.
- Do **not** write another product's or desk's catalog, port, connector, or webhook env.

## No-webhook mode

When `review/.webhook.env` is missing or the review server reports webhook not configured, Save still lands in the catalog. Nothing external wakes automatically. Use one of these — never minute-poll, never keepalive cron:

1. **User ping:** After they Save, they say "saved" (or similar). Read `/workspace/steer-catalog/review/saves/latest.json` against `review/saves/processed.json`. If that generation is already processed, stay quiet.
2. **Blocking wait (preferred when you can run shell):** After sending the review link, run `python3 /workspace/steer-catalog/start.py wait-save --timeout 600` from the catalog directory. It exits when a new unprocessed save appears (or times out). Then run the rewrite loop below.

The Grok Bot webhook path is unchanged when configured: Save POSTs and the save-ping routine runs this skill.

## Start a draft

1. If `/workspace/steer-catalog` or its `app/server.py` is missing, or the review URL from `steer.json` does not answer, run [Steer onboarding](sand-workflow:steer-onboarding) and stop until the page is up.
2. Write the markdown to the Steer catalog asset. Register it in `index.json` (`status: draft`, `text_status: full`).
3. Point the review page at that asset (`review/current.json`).
4. Confirm the review page answers (`curl -sS -m 2 http://127.0.0.1:<port><base_path>/`). If it does not, start `python3 /workspace/steer-catalog/start.py` so the port in `steer.json` (default 8766) is listening. If webhook is configured but someone was not notified, say so plainly; `review/webhook.log` has the reason. Do not send a spinning link.
5. Send the localhost review URL, not a file. One sentence on what to do: mark up, then Save. Optionally run `python3 /workspace/steer-catalog/start.py wait-save --timeout 600` if no webhook.

## While it is in review

1. On Save (webhook ping, user said "saved", or `wait-save` returned), read `review/saves/latest.json` and `review/saves/processed.json` under `/workspace/steer-catalog`.
2. If generation/`saved_at` already processed, stay quiet.
3. If `production_ready`, treat the draft as done: update catalog status, ask what to do with it (leave, publish, another pass). Never delete the save-ping routine on hosts that use one.
4. Otherwise apply CriticMarkup in the **source document's** voice: comments become revisions, substitutions/insertions/deletions apply, strip the markers after they are handled.
5. Write the revised markdown back to the **asset**. The review page reads the asset, so a live tab should update.
6. Record the processed generation in `review/saves/processed.json` so the same Save is not replayed (`generation` and `saved_at` matching `latest.json`).
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
- Handle another desk's mailbox, catalog, or Saves.
- Funnel the review page, or run `tailscale serve reset`.

## Starting the Steer page

Before sending a Steer link, probe the review URL (`http://127.0.0.1:<port><base_path>/` from `steer.json`; default `http://127.0.0.1:8766/steer/`). If it doesn't answer, start it with `python3 /workspace/steer-catalog/start.py`. Stop it after the review if the owner wants that.

