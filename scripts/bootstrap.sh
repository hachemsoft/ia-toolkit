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
PYTHONPATH="$KIT_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$KIT_PYTHON" -m installer "$@"
