<p align="center">
  <img src="assets/steer-logo.svg" alt="STEER" width="480">
</p>

# STEER

**Steer AI drafts with marks, not chat.**

This is the STEER solution: the review desk, the server, and the Grok Bot recipe that runs the rewrite loop. The thing in the video. Not a prompt with no page.

## Run the desk

On a Grok Bot computer:

```bash
cp -R desk /workspace/steer-catalog
python3 /workspace/steer-catalog/start.py
```

Then open [http://127.0.0.1:8766/steer/](http://127.0.0.1:8766/steer/). Mark the draft. Save.

Learn sandbox (does not write the catalog): [http://127.0.0.1:8766/steer/?learn=1](http://127.0.0.1:8766/steer/?learn=1)

The catalog is the copy of record. Operating law: [`desk/CONSTITUTION.md`](desk/CONSTITUTION.md).

## The bot

After the desk is up, import or recreate the Grok Bot from the recipe in this repo (profile, memory, skills, save-ping job text). Wire Save once with Steer onboarding. The bot rewrites; the page is where humans mark.

| Slot | Path |
| --- | --- |
| Profile | [`profile.json`](profile.json) |
| Memory | [`memory.json`](memory.json) |
| Skills | [`skills/`](skills/) |
| Save-ping | [`routines/draft-review-save-ping.md`](routines/draft-review-save-ping.md) |
| Plugins | [`plugins.json`](plugins.json) |

[`share.json`](share.json) is those slots in one file. Grok Bot's packer still cannot ship the desk; that is why the desk lives in [`desk/`](desk/) in this repo instead of inside a template.

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
