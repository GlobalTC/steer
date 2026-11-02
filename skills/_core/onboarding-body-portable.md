# Steer onboarding (portable)

One-time setup so STEER is the desk, not a prompt with no page. Not per document.

Run when the catalog is missing, `app/server.py` is missing, or the review URL from `steer.json` does not answer.

## 1. Install from this package (no network)

Stay in the **unzipped package folder** (where `install-catalog.sh` and `desk/` live). Do not install into your agent's shared skills tree unless you deliberately copy `SKILL.md` there as a separate opt-in step.

Run install (default catalog `<package>/steer-catalog` beside `install-catalog.sh`):

    bash install-catalog.sh

Or set another path outside `/workspace/steer-catalog`:

    STEER_CATALOG="$HOME/steer-catalog" bash install-catalog.sh

Any resolved path under the live `/workspace/steer-catalog` is refused.

Do not `curl | bash` from the network for portable installs.

## 2. Start the page

From the catalog directory:

    python3 start.py

Open `http://127.0.0.1:<port><base_path>/` from `steer.json` (defaults port **8766**, base **/steer/**). Set `STEER_PORT` when running `install-catalog.sh`, or edit `steer.json`.

## 3. Voice (optional)

Browser speech works with no setup. For host LLM resolution, set `XAI_API_KEY` or copy `review/.voice.env.example` to `review/.voice.env`.

{{SAVE_WIRE_SECTION}}

## Never

- Minute-poll or keepalive cron to detect Save.
- Put a webhook URL form on the review page.
- Install into `/workspace/steer-catalog` (including via `..` or symlinks).
