#!/bin/sh
# Builds the release ZIP, dist/ai-kit-<version>.zip, from the committed files: see scripts/build_release.py
# (--worktree to test uncommitted files; such a ZIP is never published).
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$KIT_DIR/scripts/build_release.py" "$@"
