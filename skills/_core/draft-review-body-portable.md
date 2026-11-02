# Steer draft review

Central loop for every draft on the STEER desk. Marks are the spec. Ready is not publish.

## Surfaces

- **Catalog** at `${STEER_CATALOG:-./steer-catalog}`: assets in `assets/<id>.md`.
- **Review page:** Viewing, Editing, Suggesting (CriticMarkup comments and replacements).
- **Save** writes `review/saves/latest.json`. With no webhook, use **no-webhook mode** below.

## No-webhook mode

Never minute-poll. After Save:

1. User says **saved** — read `latest.json` vs `review/saves/processed.json`, or
2. Run `python3 start.py wait-save --timeout 600` from the catalog directory (uses this catalog, not `STEER_CATALOG` when run via `start.py`).

## While in review

Apply CriticMarkup in the source voice, write the asset, update `processed.json`, recap briefly.

## Never

- Become the author.
- Redesign the review app.
- Publish unless asked.
