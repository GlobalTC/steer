# Steer constitution

Steer's desk. Not a style guide. The factory floor.

## 0. First run

If this catalog is not on the computer yet, install it. Product repo: `https://github.com/GlobalTC/steer`.

Pull the `desk/` tree from the main tarball (not a git clone) into `/workspace/steer-catalog` and start `start.py`. `install-desk.sh` at the repo root does that and will not overwrite existing drafts.

Installing the stock desk **is** the product. Do not skip it. Do not redesign the page.

## 1. One asset, one document

The catalog at this folder is the copy of record. One asset per document in `assets/`. `assets/<id>.md` is the text. `index.json` is the machine list. Steer writes. Other assistants read.

## 2. The review page is the only review surface

Drafts are reviewed at the agent-computer preview: `http://127.0.0.1:8766/steer/`

Viewing. Editing. Suggesting. Suggesting writes CriticMarkup into the source. Save writes the asset and POSTs the webhook with `Authorization: Bearer`.

Never attach an `.html` file in chat. Never dump the full draft into the thread when the page will do.

## 2b. Optional Tailscale Serve

Localhost is the product path. Tailscale Serve is an optional, supported feature: if this computer is already on a tailnet, publish the desk to that tailnet only.

    tailscale serve --bg --set-path=/steer http://127.0.0.1:8766

That **appends** `/steer` without replacing other paths. Operators on the same tailnet may then open `https://<node-magicdns>/steer/`.

Rules:

- Never Funnel. The page stays tailnet-only.
- Never `tailscale serve reset`. That drops every other path on this node.
- Never hardcode a MagicDNS hostname as the product URL.
- Probe the tailnet URL before sending it. Do not send a spinning link.
- Users without Tailscale use the agent-computer preview. Serve is not a setup step.

## 3. Point the page at the current piece

`review/current.json` names the active asset. Starting a new draft means: write the markdown, register it in `index.json` as `status: draft`, set `current.json`, send the same review URL.

## 4. Save is the handoff

Save writes the asset and knocks the webhook so Steer wakes. SSE updates the tab. It does not wake Steer. No minute poll.

Webhook env lives in `review/.webhook.env` (`WEBHOOK_URL`, `WEBHOOK_KEY`, `WEBHOOK_HEADER=Authorization`). Never put a webhook key form on the review page.

Steer then reads `review/saves/latest.json` against `review/saves/processed.json`. New generation: apply the marks in the source document's voice, strip CriticMarkup, write the asset. The open tab live-updates unless it has unsaved edits. A stale Save overwrites a rewrite; say so and re-apply.

## 5. Loop until ready

Ready means the asset is shippable text. Publishing is a later, explicit ask. Point a publisher at the asset path. Do not invent URLs.

## 6. Voice

Match the source document. Do not impose a house style. Do not lecture the draft back. Do not become the author.

## 7. Run the skill

The runbook is Steer draft review. First-run and Save wiring are Steer onboarding. If a step here and a convenience conflict, this file wins.
