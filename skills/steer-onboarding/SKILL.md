---
name: Steer onboarding
description: >-
  Use once when first setting up Steer, when the catalog or review page is
  missing, or only if Save later stops waking the desk. Not per document.
  Installs the stock desk from the product repo if needed, then wires Save.
---
# Steer onboarding

One-time setup so a new Steer actually is the desk, not a prompt with no page. Do not run it when starting a new piece. Do not ask for the URL or key again just because `current.json` changed.

Run it when any of these is true:

- This Steer has never been wired.
- `/workspace/steer-catalog` is missing, or `review/server.py` is missing.
- `http://127.0.0.1:8766/steer/` does not answer.
- Save no longer wakes the desk.

Installing the stock desk from the product repo **is** the product. Do not skip it. Do not redesign the page.

Never write another product's `review/.webhook.env`. Overwriting it steals every Save on that desk.

## 1. First run: install the desk

Product repo (source of the page, server, sample draft, logos): `https://github.com/GlobalTC/steer`

Catalog path: `/workspace/steer-catalog`

If the catalog is already present **and** `review/server.py` exists, skip the download. Do not overwrite someone else's drafts.

If the catalog is missing, or the server file is missing:

1. Download the repo tarball (do not `git clone` onto the computer):

       curl -fsSL https://github.com/GlobalTC/steer/archive/refs/heads/main.tar.gz -o /tmp/steer.tgz

2. Unpack and copy only `desk/` :

       mkdir -p /tmp/steer-unpack
       tar -xzf /tmp/steer.tgz -C /tmp/steer-unpack
       SRC=$(find /tmp/steer-unpack -maxdepth 2 -type d -name desk | head -1)

3. If `/workspace/steer-catalog` does not exist:

       cp -R "$SRC" /workspace/steer-catalog

   If it exists but `review/server.py` is missing, copy `review/server.py`, `review/static/`, `start.py`, and `CONSTITUTION.md` from `$SRC` into the catalog. Leave `assets/` and `index.json` alone.

4. Confirm `steer-slop-sample` is the current draft (`review/current.json`) so the first open is something to mark, not an empty parking page. If `current.json` is missing, write it pointing at `assets/steer-slop-sample.md`.

Or run `install-desk.sh` from this repo (same steps). Do not start a second server if the page already answers.

## 2. Start the page

Probe `http://127.0.0.1:8766/steer/` (2 second timeout).

If it fails, start the server in the background:

    python3 /workspace/steer-catalog/start.py

Probe again. Do not send a spinning link. When it answers, tell the user to open [http://127.0.0.1:8766/steer/](http://127.0.0.1:8766/steer/) and mark the sample, then Save. Learn sandbox: [http://127.0.0.1:8766/steer/?learn=1](http://127.0.0.1:8766/steer/?learn=1).

Tailscale Serve is optional and not part of first-run. If this computer is on a tailnet, you MAY add `tailscale serve --bg --set-path=/steer http://127.0.0.1:8766` so other tailnet devices can open `https://<node-magicdns>/steer/`. Never Funnel. Never `tailscale serve reset`. Users without Tailscale skip this.

Do not put a webhook URL or sender-key form on the review page.

## 3. Wire Save

Steer sleeps between turns. SSE updates the open tab. It cannot wake Steer. Save must POST to **this bot's** webhook routine.

1. If `/workspace/steer-catalog/review/.webhook.env` already has `WEBHOOK_URL` and `WEBHOOK_KEY`, and the review server reports webhook configured, stop. Do not re-ask. New documents use this same file.
2. If the save-ping webhook routine does not exist on this bot, create it once (trigger: webhook). The prompt is: read `/workspace/steer-catalog` latest vs processed, apply marks to the asset named by `current.json`, stay quiet if nothing new, recap in one or two sentences, never dump the full draft, never publish unless asked, never delete this routine when a piece is ready, never minute-poll, never a keepalive, never put a webhook key form on the page, never name a specific person.
3. You never see the URL or sender key. They live on the routine panel.
4. Prompt for them with secret-request, one at a time, never in chat:
   - label `Steer save webhook URL`, connector `steer-review`, field `webhook_url`
   - label `Steer save sender key`, connector `steer-review`, field `webhook_key`
5. Copy those two fields into `/workspace/steer-catalog/review/.webhook.env` as `WEBHOOK_URL` and `WEBHOOK_KEY`. Header must be `Authorization` with `Bearer <key>` (not `X-Webhook-Secret`). Mode `0600`. Never paste them into chat, memory, or the catalog.
6. Confirm the live review server reports webhook configured (`http://127.0.0.1:8766/steer/api/webhook-status`). A live probe must return success, not 401.
7. Do **not** run a minute poll. The editor knocks on Save. A disk watch is only a temporary crutch while step 4–6 are unfinished, and it must be paused the moment the webhook is configured.

One ping on this Steer bot for the whole page. Never a second save-ping on another bot.

## After onboarding

Follow [Steer draft review](sand-workflow:steer-draft-review). Point `current.json` at each new piece. The ping stays the same.

## Never

- Skip first-run because the catalog is empty. Empty is the reason to install.
- Redesign, restyle, or rewrite the review app. Install the stock desk.
- Re-ask for URL or key because a different document is on the page.
- Ask a reviewer to invent or type a webhook URL on the page.
- Resume minute polling because SSE exists. SSE is for the tab, not for Steer.
- Store the sender key in the transcript.
- Write another desk's `.webhook.env`.
- Create a second save-ping on another bot.
- Funnel the review page, or run `tailscale serve reset`.
- `git clone` the product repo onto the computer. Use the tarball.
