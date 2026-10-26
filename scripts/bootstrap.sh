#!/bin/sh
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v python3 >/dev/null 2>&1; then
  KIT_PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  KIT_PYTHON=python
else
  echo 'Python not found. Ask your IT support to make Python available in the terminal.' >&2
  exit 2
fi
# The current folder stays the user's: a relative path (--json, --home) resolves there, not in the kit.
if [ "$#" -eq 0 ]; then set -- setup; fi
# update: first fetch the new version when the kit folder is a git clone without local changes; never blocks the update.
if [ "$1" = "update" ] && [ -d "$KIT_DIR/.git" ] && command -v git >/dev/null 2>&1; then
  if git -C "$KIT_DIR" diff --quiet && git -C "$KIT_DIR" diff --cached --quiet; then
    git -C "$KIT_DIR" pull --ff-only --quiet || echo 'Could not fetch the new version (network or diverging history): updating from the current folder.' >&2
  else
    echo 'Local changes in the kit folder: no git pull; updating from the current folder.' >&2
  fi
fi
PYTHONPATH="$KIT_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$KIT_PYTHON" -m installer "$@"
