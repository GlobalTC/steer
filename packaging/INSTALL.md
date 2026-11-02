# Install STEER (portable skill)

Work entirely inside the folder where you unzipped this package. Do **not** copy files into your agent's shared skills directory unless you choose to — that is a separate, opt-in step.

1. Unzip to a directory you control (example: `~/steer-portable/`).
2. **Optional — agent skill only:** copy `SKILL.md` into your host's skills folder if you want the agent to load it globally. The desk itself stays in step 3.
3. Pick a catalog directory **outside** `/workspace/steer-catalog` (example: `~/steer-portable/catalog`):

   ```bash
   cd /path/to/unzipped/package
   STEER_CATALOG="$PWD/catalog" bash install-catalog.sh
   ```

   If you omit `STEER_CATALOG`, the catalog defaults to `./steer-catalog` relative to the package directory (not your login directory). The installer refuses any path that resolves to the live `/workspace/steer-catalog` catalog.

4. Open the review URL from `steer.json` (default port **8766**, base **/steer/**). Override port with `STEER_PORT` when running `install-catalog.sh`, or edit `steer.json`.

## Save without a webhook

After Save, the agent reads `review/saves/latest.json` vs `processed.json`, or runs from the catalog directory:

```bash
python3 start.py wait-save --timeout 600
```

Optional voice LLM: `XAI_API_KEY` or `review/.voice.env` from the example file.

MIT License — see `LICENSE`.
