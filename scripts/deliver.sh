#!/usr/bin/env bash
# Copy a finished Growcline set to the delivery folder:
#   $DELIVERY_DIR/growcline/<topic>/<date>/   (replaces an older copy of that date)
# Usage: deliver.sh <topic> <YYYY-MM-DD>      source = <project>/output/<topic>/<date>/
# DELIVERY_DIR comes from <project>/config.env. If it is empty, nothing is copied.
set -euo pipefail
T="${1:?topic}"; DT="${2:?date YYYY-MM-DD}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DELIVERY_DIR=""
[ -f "$ROOT/config.env" ] && DELIVERY_DIR="$(grep -E '^DELIVERY_DIR=' "$ROOT/config.env" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"
SRC="$ROOT/output/${T}/${DT}"
[ -d "$SRC" ] || { echo "error: $SRC not found" >&2; exit 1; }
if [ -z "$DELIVERY_DIR" ]; then
  echo "DELIVERY_DIR not set in $ROOT/config.env; files stay at: $SRC"
  exit 0
fi
DEST="${DELIVERY_DIR%/}/growcline/${T}"
mkdir -p "$DEST"
rm -rf "${DEST:?}/${DT:?}"
cp -r "$SRC" "$DEST/"
if command -v wslpath >/dev/null 2>&1 && [[ "$DEST" == /mnt/* ]]; then
  echo "delivered: $(wslpath -w "$DEST/$DT")"
else
  echo "delivered: $DEST/$DT"
fi
