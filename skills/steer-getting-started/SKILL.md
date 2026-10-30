---
name: Steer getting started
description: >-
  Short pointer for operators: install the desk, open the review URL from
  steer.json, mark a draft, Save. Use steer-onboarding for first-run wiring.
---
# Steer getting started

1. Run `install-desk.sh` (see [Steer onboarding](sand-workflow:steer-onboarding)) so `/workspace/steer-catalog` has `app/server.py` and the server is listening.
2. Read `steer.json` for **port** and **base_path**; open `http://127.0.0.1:<port><base_path>/` (defaults `8766` and `/steer/`).
3. Mark the sample draft in **Suggesting**, then **Save**. Optional: voice dictation and server STT per onboarding §3.
4. Follow [Steer draft review](sand-workflow:steer-draft-review) for the rewrite loop.
