#!/bin/sh
# Builds the kit distribution archive: dist/ai-kit-<version>.zip, without caches or local files.
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=$(tr -d '[:space:]' < "$KIT_DIR/VERSION")
OUT="$KIT_DIR/dist/ai-kit-$VERSION.zip"
mkdir -p "$KIT_DIR/dist"
rm -f "$OUT"
cd "$KIT_DIR/.."
zip -qr "$OUT" "$(basename "$KIT_DIR")" \
  -x "*/.git/*" "*/dist/*" "*/__pycache__/*" "*/.pytest_cache/*" "*/.codegraph/*" "*/.DS_Store" "*/sandbox-*/*" "*/.claude/*"
echo "$OUT"
