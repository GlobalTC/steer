## 4. Wire Save (Grok Bot webhook)

Steer sleeps between turns. SSE updates the open tab. It cannot wake Steer. Save must POST to **this bot's** webhook routine when you use Grok Bot.

1. If `{{CATALOG}}/review/.webhook.env` already has `WEBHOOK_URL` and `WEBHOOK_KEY`, and the review server reports webhook configured, stop. Do not re-ask. New documents use this same file.
2. If the save-ping webhook routine does not exist on this bot, create it once (trigger: webhook). The prompt is: read the catalog latest vs processed, apply marks to the asset named by `current.json`, stay quiet if nothing new, recap in one or two sentences, never dump the full draft, never publish unless asked, never delete this routine when a piece is ready, never minute-poll, never a keepalive, never put a webhook key form on the page, never name a specific person.
3. You never see the URL or sender key. They live on the routine panel.
4. Prompt for them with secret-request, one at a time, never in chat:
   - label `Steer save webhook URL`, connector `steer-review`, field `webhook_url`
   - label `Steer save sender key`, connector `steer-review`, field `webhook_key`
5. Copy those two fields into `{{CATALOG}}/review/.webhook.env` as `WEBHOOK_URL` and `WEBHOOK_KEY`. Header must be `Authorization` with `Bearer <key>` (not `X-Webhook-Secret`). Mode `0600`. Never paste them into chat, memory, or the catalog.
6. Confirm the live review server reports webhook configured (`http://127.0.0.1:8766/steer/api/webhook-status`). A live probe must return success, not 401.
7. Do **not** run a minute poll. The editor knocks on Save. A disk watch is only a temporary crutch while step 4–6 are unfinished, and it must be paused the moment the webhook is configured.

One ping on this Steer bot for the whole page. Never a second save-ping on another bot.

If webhook wiring is impossible, use no-webhook mode from {{DRAFT_REVIEW_REF}} (`wait-save` or user says "saved").
