# Steer onboarding (portable)

One-time setup so STEER is the desk, not a prompt with no page. Not per document.

Run when the catalog is missing, `app/server.py` is missing, or the review URL from `steer.json` does not answer.

## 1. Install from this package (no network)

Set where the catalog should live (default `./steer-catalog`):

    export STEER_CATALOG="${STEER_CATALOG:-./steer-catalog}"

From the directory that contains `install-catalog.sh` and `desk/` (the unzipped package root):

    bash install-catalog.sh

That copies the bundled `desk/` into `STEER_CATALOG`, merges `steer.json` keys without clobbering drafts, and starts the server only if nothing is already listening for that catalog on the configured port. It **refuses** to install into `/workspace/steer-catalog` unless you set `STEER_CATALOG` explicitly.

Do not `curl | bash` from the network for portable installs. Do not nest `desk/desk` — the script copies contents into the catalog root.

## 2. Start the page

From the catalog directory:

    python3 start.py

Open `http://127.0.0.1:<port><base_path>/` from `steer.json` (defaults port **8766**, base path **/steer/**). Override port with `STEER_PORT` or `steer.json` `port`.

## 3. Voice (optional)

Browser speech works with no setup. For host LLM resolution, set `XAI_API_KEY` or copy `review/.voice.env.example` to `review/.voice.env`.

{{SAVE_WIRE_SECTION}}

## Never

- Minute-poll or keepalive cron to detect Save.
- Put a webhook URL form on the review page.
- Install into `/workspace/steer-catalog` by accident on shared hosts.
