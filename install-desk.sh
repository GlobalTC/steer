#!/usr/bin/env bash
# Install the STEER desk onto a Grok Bot computer.
# Safe to re-run: will not overwrite an existing catalog's drafts.
set -euo pipefail

DEST="${STEER_CATALOG:-/workspace/steer-catalog}"
TARBALL="${STEER_TARBALL:-https://github.com/GlobalTC/steer/archive/refs/heads/main.tar.gz}"
PAGE="http://127.0.0.1:8766/steer/"

need_install=0
if [[ ! -d "$DEST" ]]; then
  need_install=1
elif [[ ! -f "$DEST/review/server.py" ]]; then
  need_install=1
fi

if [[ "$need_install" -eq 1 ]]; then
  tmp=$(mktemp -d)
  cleanup() { rm -rf "$tmp"; }
  trap cleanup EXIT
  curl -fsSL "$TARBALL" -o "$tmp/steer.tgz"
  tar -xzf "$tmp/steer.tgz" -C "$tmp"
  SRC=$(find "$tmp" -maxdepth 2 -type d -name desk | head -1)
  if [[ -z "$SRC" || ! -f "$SRC/review/server.py" ]]; then
    echo "desk/ missing from tarball" >&2
    exit 1
  fi
  if [[ ! -d "$DEST" ]]; then
    mkdir -p "$(dirname "$DEST")"
    cp -R "$SRC" "$DEST"
  else
    mkdir -p "$DEST/review"
    cp "$SRC/review/server.py" "$DEST/review/server.py"
    rm -rf "$DEST/review/static"
    cp -R "$SRC/review/static" "$DEST/review/static"
    cp "$SRC/start.py" "$DEST/start.py"
    if [[ ! -f "$DEST/CONSTITUTION.md" ]]; then
      cp "$SRC/CONSTITUTION.md" "$DEST/CONSTITUTION.md"
    fi
  fi
  if [[ ! -f "$DEST/review/current.json" ]]; then
    mkdir -p "$DEST/review"
    printf '%s\n' '{"asset":"assets/steer-slop-sample.md"}' > "$DEST/review/current.json"
  fi
fi

if ! curl -fsS -m 2 "$PAGE" >/dev/null 2>&1; then
  if [[ ! -f "$DEST/start.py" ]]; then
    echo "no start.py at $DEST" >&2
    exit 1
  fi
  nohup python3 "$DEST/start.py" >/tmp/steer-desk.log 2>&1 &
  for _ in $(seq 1 20); do
    if curl -fsS -m 2 "$PAGE" >/dev/null 2>&1; then
      echo "$PAGE"
      exit 0
    fi
    sleep 0.25
  done
  echo "server did not answer at $PAGE" >&2
  exit 1
fi

echo "$PAGE"
