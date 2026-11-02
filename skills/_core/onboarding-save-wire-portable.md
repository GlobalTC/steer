## 4. Save without a webhook

Save writes `review/saves/latest.json`. After Save, either the user says **saved** or run:

    {{WAIT_SAVE_CMD}}

Optional outbound webhook: copy `review/.webhook.env.example` to `review/.webhook.env` (mode `0600`).
