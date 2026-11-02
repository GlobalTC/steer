# Install STEER (portable skill)

1. Unzip this package anywhere you keep agent skills.
2. Copy `SKILL.md` into your agent's skills folder (Cursor: `.cursor/skills/` or the path your host documents). Keep `desk/` beside it or set `STEER_CATALOG` to where you install the catalog.
3. Install the catalog (data + server):

   ```bash
   export STEER_CATALOG="${STEER_CATALOG:-./steer-catalog}"
   cp -R desk "$STEER_CATALOG"
   # or from the product repo:
   curl -fsSL https://raw.githubusercontent.com/GlobalTC/steer/main/install-desk.sh | bash
   ```

4. Start the review page:

   ```bash
   cd "$STEER_CATALOG"
   python3 start.py
   ```

5. Open `http://127.0.0.1:8766/steer/` (port and path from `steer.json`).

No webhook is required. After Save, the agent reads `review/saves/latest.json` vs `processed.json`, or runs:

```bash
python3 start.py wait-save --timeout 600
```

Optional voice LLM: set `XAI_API_KEY` or copy `review/.voice.env.example` to `review/.voice.env`.

License: MIT — see `LICENSE`.
