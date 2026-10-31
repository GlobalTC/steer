#!/usr/bin/env bash
# Install or upgrade the STEER desk onto a Grok Bot computer.
set -euo pipefail

DEST="${STEER_CATALOG:-/workspace/steer-catalog}"
STEER_TAG="${STEER_TAG:-v2026.10.31-1}"
TARBALL="${STEER_TARBALL:-https://github.com/GlobalTC/steer/archive/refs/tags/${STEER_TAG}.tar.gz}"

tmp=$(mktemp -d)
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

curl -fsSL "$TARBALL" -o "$tmp/steer.tgz"
tar -xzf "$tmp/steer.tgz" -C "$tmp"
SRC=$(find "$tmp" -maxdepth 2 -type d -name desk | head -1)
if [[ -z "$SRC" || ! -f "$SRC/app/server.py" ]]; then
  echo "desk/ missing from tarball (tag ${STEER_TAG})" >&2
  exit 1
fi

if [[ ! -d "$DEST" ]]; then
  mkdir -p "$(dirname "$DEST")"
  cp -R "$SRC" "$DEST"
else
  mkdir -p "$DEST/review"
  rm -rf "$DEST/app"
  cp -R "$SRC/app" "$DEST/app"
  cp "$SRC/start.py" "$DEST/start.py"
  if [[ -f "$DEST/review/server.py" ]]; then
    mv "$DEST/review/server.py" "$DEST/review/server.py.pre-app"
  fi
  if [[ ! -f "$DEST/CONSTITUTION.md" ]]; then
    cp "$SRC/CONSTITUTION.md" "$DEST/CONSTITUTION.md"
  fi
  if [[ ! -d "$DEST/brand" ]]; then
    cp -R "$SRC/brand" "$DEST/brand"
  else
    for f in "$SRC/brand"/*; do
      [[ -f "$f" ]] || continue
      base=$(basename "$f")
      [[ -f "$DEST/brand/$base" ]] || cp "$f" "$DEST/brand/$base"
    done
  fi
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

if [[ ! -f "$DEST/review/current.json" ]]; then
  mkdir -p "$DEST/review"
  printf '%s\n' '{"id":"steer-slop-sample","asset":"assets/steer-slop-sample.md"}' > "$DEST/review/current.json"
fi

read -r DESK_HOST DESK_PORT BASE_PATH DESK_NAME APP_VERSION <<EOF
$(python3 - "$DEST" <<'PY'
import json
import sys
from pathlib import Path

dest = Path(sys.argv[1])
cfg = json.loads((dest / "steer.json").read_text()) if (dest / "steer.json").is_file() else {}
port = int(cfg.get("port") or 8766)
host = cfg.get("host") or "127.0.0.1"
base = cfg.get("base_path") or "/steer"
base = "/" + base.strip("/") if base.strip("/") else ""
name = cfg.get("name") or "STEER"
ver = (dest / "app" / "VERSION").read_text().strip() if (dest / "app" / "VERSION").is_file() else "0"
print(host, port, base, name, ver, sep="\t")
PY
)
EOF

PAGE="http://${DESK_HOST}:${DESK_PORT}${BASE_PATH}/"
CONFIG_URL="${PAGE}api/config"

desk_identity_ok() {
  python3 - "$CONFIG_URL" "$DESK_NAME" "$APP_VERSION" <<'PY'
import json
import sys
import urllib.request

url, name, version = sys.argv[1:4]
try:
    with urllib.request.urlopen(url, timeout=2) as resp:
        data = json.loads(resp.read().decode())
except Exception:
    sys.exit(1)
sys.exit(0 if data.get("name") == name and data.get("version") == version else 1)
PY
}

if curl -fsS -m 2 "$PAGE" >/dev/null 2>&1; then
  if desk_identity_ok; then
    echo "$PAGE"
    exit 0
  fi
  echo "Port ${DESK_PORT} is serving another desk (expected name ${DESK_NAME}, version ${APP_VERSION})." >&2
  exit 1
fi

if [[ ! -f "$DEST/start.py" ]]; then
  echo "no start.py at $DEST" >&2
  exit 1
fi

nohup python3 "$DEST/start.py" >/tmp/steer-desk.log 2>&1 &
for _ in $(seq 1 20); do
  if curl -fsS -m 2 "$PAGE" >/dev/null 2>&1 && desk_identity_ok; then
    echo "$PAGE"
    exit 0
  fi
  sleep 0.25
done

echo "server did not answer at $PAGE" >&2
exit 1
