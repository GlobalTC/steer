## 4. Save without a webhook (default outside Grok Bot)

You do not need a webhook URL. Save writes `review/saves/latest.json` in the catalog.

Tell the owner: after Save, either say **"saved"** so you read `latest.json` vs `processed.json`, or let you run a blocking wait:

    {{WAIT_SAVE_CMD}}

Optional: if the host supports outbound webhooks, copy `review/.webhook.env.example` to `review/.webhook.env` and set `WEBHOOK_URL` and `WEBHOOK_KEY` (mode `0600`). That path is unchanged for Grok Bot installs. Never put a webhook form on the review page.
