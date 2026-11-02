# Install STEER (portable skill)

Work inside the folder where you unzipped this package. Do **not** copy files into your agent's shared skills directory unless you choose to — that is a separate, opt-in step.

1. Unzip to a directory you control (example: `~/steer-portable/`).
2. **Optional — agent skill only:** copy `SKILL.md` into your host's skills folder if you want the agent to load it globally. The desk install stays in step 3.
3. Install the catalog beside this package (default `<unzip-dir>/steer-catalog`):

   ```bash
   cd /path/to/unzipped/package
   bash install-catalog.sh
   ```

   Or choose another path outside `/workspace/steer-catalog`:

   ```bash
   STEER_CATALOG="$HOME/steer-catalog" bash install-catalog.sh
   ```

   Any resolved path under the live `/workspace/steer-catalog` is refused.

4. Open the review URL from `steer.json` (default port **8766**, base **/steer/**). Set `STEER_PORT` when running `install-catalog.sh` to pick a port; it is saved into `steer.json`.

## Save without a webhook

After Save, the agent reads `review/saves/latest.json` vs `processed.json`, or runs from the catalog directory:

```bash
python3 start.py wait-save --timeout 600
```

Optional voice LLM: `XAI_API_KEY` or `review/.voice.env` from the example file.

MIT License — see `LICENSE`.
