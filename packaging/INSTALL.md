# Install STEER (portable skill)

1. Unzip the package to a directory you control.
2. Copy `SKILL.md` into your agent's skills folder.
3. Choose a catalog path (default `./steer-catalog`):

   ```bash
   export STEER_CATALOG="${STEER_CATALOG:-$PWD/steer-catalog}"
   ```

4. Install from the bundled desk (no network):

   ```bash
   bash install-catalog.sh
   ```

   The script copies `desk/` into `STEER_CATALOG` and starts the review server only if that catalog is not already listening. It refuses to install into `/workspace/steer-catalog` unless you set `STEER_CATALOG` explicitly.

5. Open the review URL from `steer.json` (default `http://127.0.0.1:8766/steer/`). Change port in `steer.json` or with `STEER_PORT`.

## Save without a webhook

After Save, the agent reads `review/saves/latest.json` vs `processed.json`, or runs from the catalog directory:

```bash
python3 start.py wait-save --timeout 600
```

Optional voice LLM: `XAI_API_KEY` or `review/.voice.env` from the example file.

MIT License — see `LICENSE`.
