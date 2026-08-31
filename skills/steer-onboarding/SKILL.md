---
name: Steer onboarding
description: >-
  Use once when first setting up Steer, or only if Save later stops waking the
  desk. Not per document. Collects the save-ping URL and sender key once for
  the whole review page.
---
# Steer onboarding

This is a one-time process for Steer as a desk. Every document that uses the live review page shares the same Save ping. Do not run it when starting a new piece. Do not ask for the URL or key again just because `current.json` changed.

Run it only when Steer has never been wired, or when Save no longer wakes the desk.

Never write another product's `review/.webhook.env`. Overwriting it steals every Save on that desk.

## What must already exist

- Writing catalog on the shared computer (`/workspace/steer-catalog`).
- Live review page on port `8766` at `/steer/`, pointed at `review/current.json`. Switching documents only changes that pointer.
- Review server actually listening at `http://127.0.0.1:8766/steer/`. If it fails, start the review server.
- One webhook routine on **this** Steer bot for the whole page. Not on a backup bot. Not on another product.

Tailscale Serve is optional and not part of Save wiring. If this computer is on a tailnet, you MAY add `tailscale serve --bg --set-path=/steer http://127.0.0.1:8766` so other tailnet devices can open `https://<node-magicdns>/steer/`. Never Funnel. Never `tailscale serve reset`. Users without Tailscale skip this.

Do not put a webhook URL or sender-key form on the review page. Reviewers mark the draft and hit Save.

## Wake path (required)

Steer sleeps between turns. SSE updates the open tab. It cannot wake Steer.

Save must POST to **this bot's** webhook routine:

1. If `/workspace/steer-catalog/review/.webhook.env` already has `WEBHOOK_URL` and `WEBHOOK_KEY`, and the review server reports webhook configured, stop. Do not re-ask. New documents use this same file.
2. If the save-ping webhook routine does not exist on this bot, create it once (trigger: webhook). The prompt is: read `/workspace/steer-catalog` latest vs processed, apply marks to the asset named by `current.json`, stay quiet if nothing new, recap in one or two sentences, never dump the full draft, never publish unless asked, never delete this routine when a piece is ready, never minute-poll, never a keepalive, never put a webhook key form on the page, never name a specific person.
3. You never see the URL or sender key. They live on the routine panel.
4. Prompt for them with secret-request, one at a time, never in chat:
   - label `Steer save webhook URL`, connector `steer-review`, field `webhook_url`
   - label `Steer save sender key`, connector `steer-review`, field `webhook_key`
5. Copy those two fields into `/workspace/steer-catalog/review/.webhook.env` as `WEBHOOK_URL` and `WEBHOOK_KEY`. Header must be `Authorization` with `Bearer <key>` (not `X-Webhook-Secret`). Mode `0600`. Never paste them into chat, memory, or the catalog.
6. Confirm the live review server reports webhook configured (`http://127.0.0.1:8766/steer/api/webhook-status`). A live probe must return success, not 401.
7. Do **not** run a minute poll. The editor knocks on Save. A disk watch is only a temporary crutch while step 4–6 are unfinished, and it must be paused the moment the webhook is configured.

## After onboarding

Follow Steer draft review. Point `current.json` at each new piece. The ping stays the same.

## Never

- Re-ask for URL or key because a different document is on the page.
- Ask a reviewer to invent or type a webhook URL on the page.
- Resume minute polling because SSE exists. SSE is for the tab, not for Steer.
- Store the sender key in the transcript.
- Write another product's `.webhook.env`.
- Create a second save-ping on a backup bot or any other bot.
- Funnel the review page, or run `tailscale serve reset`.
