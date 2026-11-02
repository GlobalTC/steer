#!/usr/bin/env bash
# Install STEER catalog from the bundled desk/ next to this script (portable zip).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/desk"
DEST="${STEER_CATALOG:-./steer-catalog}"

if [[ ! -f "$SRC/app/server.py" && -f "$ROOT/../desk/app/server.py" ]]; then
  SRC="$ROOT/../desk"
fi

if [[ ! -f "$SRC/app/server.py" ]]; then
  echo "desk/ missing beside install-catalog.sh" >&2
  exit 1
fi

python3 - "$DEST" "$SRC" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[2])
sys.path.insert(0, str(src / "app"))
from catalog_paths import refuse_live_workspace_catalog, resolve_catalog_path

dest = sys.argv[1]
refuse_live_workspace_catalog(resolve_catalog_path(dest), operation="install")
PY

REAL_DEST="$(python3 - "$DEST" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
)"

mkdir -p "$DEST"
if [[ ! -d "$DEST" ]]; then
  echo "Could not create catalog at $DEST" >&2
  exit 1
fi

if [[ ! -d "$DEST/review" ]]; then
  mkdir -p "$DEST/review/saves"
  cp -R "$SRC/." "$DEST/"
else
  mkdir -p "$DEST/review"
  rm -rf "$DEST/app"
  cp -R "$SRC/app" "$DEST/app"
  cp "$SRC/start.py" "$DEST/start.py"
  python3 - "$DEST" "$SRC" <<'PY'
import json
import sys
from pathlib import Path

dest = Path(sys.argv[1])
src = Path(sys.argv[2])
dest_cfg_path = dest / "steer.json"
src_cfg_path = src / "steer.json"
dest_cfg = json.loads(dest_cfg_path.read_text()) if dest_cfg_path.is_file() else {}
src_cfg = json.loads(src_cfg_path.read_text()) if src_cfg_path.is_file() else {}


def merge(default, existing):
    for key, val in default.items():
        if key not in existing:
            existing[key] = val
        elif isinstance(val, dict) and isinstance(existing.get(key), dict):
            merge(val, existing[key])
    return existing


if src_cfg:
    merge(src_cfg, dest_cfg)
    dest_cfg_path.write_text(json.dumps(dest_cfg, indent=2) + "\n")
PY
fi

read -r DESK_HOST DESK_PORT BASE_PATH <<EOF
$(python3 - "$DEST" <<'PY'
import json
import os
import sys
from pathlib import Path

dest = Path(sys.argv[1])
cfg = json.loads((dest / "steer.json").read_text()) if (dest / "steer.json").is_file() else {}
port = int(os.environ.get("STEER_PORT") or cfg.get("port") or 8766)
host = cfg.get("host") or "127.0.0.1"
base = cfg.get("base_path") or "/steer"
base = "/" + base.strip("/") if base.strip("/") else ""
print(host, port, base, sep="\t")
PY
)
EOF

python3 "$DEST/app/install_port.py" ensure \
  --catalog "$DEST" \
  --host "$DESK_HOST" \
  --port "$DESK_PORT" \
  --base-path "$BASE_PATH"

echo "Catalog: $REAL_DEST"
