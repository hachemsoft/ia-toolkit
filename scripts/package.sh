#!/bin/sh
# Builds the release ZIP, dist/ai-kit-<version>.zip, from the committed files (git archive): uncommitted changes are not in it,
# nor the maintainer files marked export-ignore in .gitattributes. No top folder inside: extracting it with Windows Explorer
# or the macOS Archive Utility gives a single folder ai-kit-<version>, with Installer.cmd at its root.
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=$(tr -d '[:space:]' < "$KIT_DIR/VERSION")
OUT="$KIT_DIR/dist/ai-kit-$VERSION.zip"
mkdir -p "$KIT_DIR/dist"
rm -f "$OUT"
git -C "$KIT_DIR" archive --format=zip -o "$OUT" HEAD
echo "$OUT"
