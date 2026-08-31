<p align="center">
  <img src="assets/steer-logo.svg" alt="STEER" width="480">
</p>

# STEER

**Steer AI drafts with marks, not chat.**

This is the STEER solution: the review desk, the server, and the Grok Bot recipe that runs the rewrite loop. The thing in the video. Not a prompt with no page.

## Grok Bot template

Import STEER as a Grok Bot. On first conversation the bot runs Steer onboarding:

1. If `/workspace/steer-catalog` is missing, it pulls `desk/` from this repo (tarball, not a git clone).
2. It starts the page at [http://127.0.0.1:8766/steer/](http://127.0.0.1:8766/steer/).
3. It wires Save once (webhook URL + sender key via secret-request).

The first open should be the slop sample. Mark it. Save. That is the product.

You can also run the same install yourself:

```bash
curl -fsSL https://raw.githubusercontent.com/GlobalTC/steer/main/install-desk.sh | bash
```

Or, if you already have this repo:

```bash
cp -R desk /workspace/steer-catalog
python3 /workspace/steer-catalog/start.py
```

Learn sandbox (does not write the catalog): [http://127.0.0.1:8766/steer/?learn=1](http://127.0.0.1:8766/steer/?learn=1)

The catalog is the copy of record. Operating law: [`desk/CONSTITUTION.md`](desk/CONSTITUTION.md).

## The bot recipe

The page is the product. The recipe is the rewrite loop that wakes on Save.

| Slot | Path |
| --- | --- |
| Profile | [`profile.json`](profile.json) |
| Memory | [`memory.json`](memory.json) |
| Skills | [`skills/`](skills/) |
| Save-ping | [`routines/draft-review-save-ping.md`](routines/draft-review-save-ping.md) |
| Plugins | [`plugins.json`](plugins.json) |

[`share.json`](share.json) is those slots in one file. Grok Bot's packer still cannot ship the desk files; first-run reconstructs them from this repo.

## Optional Tailscale Serve

Localhost is the product path. If this computer is on a tailnet:

    tailscale serve --bg --set-path=/steer http://127.0.0.1:8766

Tailnet only. Never Funnel. Never `tailscale serve reset`.

## Brand

- Wordmark: [`assets/steer-logo.svg`](assets/steer-logo.svg)
- Square mark: [`assets/steer-mark.svg`](assets/steer-mark.svg)

## License

Apache License, Version 2.0. See [`LICENSE`](LICENSE) (authoritative) and [`LICENSE.md`](LICENSE.md).

Copyright 2026 832 Labs.
