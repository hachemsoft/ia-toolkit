#!/bin/sh
# AI Kit launcher for macOS and Linux: finds Python 3.9 or newer, then runs the installer (setup when no argument is given).
# No sudo, no change to the system, to the PATH or to the shell startup files.
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KIT_PYTHON=
KIT_FOUND=
for candidate in python3 python; do
  path=$(command -v "$candidate" 2>/dev/null) || continue
  # macOS: /usr/bin/python3 without the developer tools only offers to install them (an administrator step): treated as absent.
  if [ "$path" = /usr/bin/python3 ] && [ "$(uname)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then
    continue
  fi
  status=0
  "$path" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 3)' >/dev/null 2>&1 || status=$?
  case "$status" in
    0) KIT_PYTHON=$path; break ;;
    3) KIT_FOUND=old ;;
    *) KIT_FOUND=${KIT_FOUND:-blocked} ;;
  esac
done
if [ -z "$KIT_PYTHON" ]; then
  case "$KIT_FOUND" in
    old) echo 'The Python found is older than 3.9: the AI Kit needs Python 3.9 or newer (3.11 recommended).' >&2 ;;
    blocked) echo 'Python is present but could not be started: a security policy or an incomplete installation may prevent it.' >&2 ;;
    *) echo 'Python 3.9 or newer was not found (commands python3, python).' >&2 ;;
  esac
  echo 'What to ask IT support: Python 3.9 or newer (3.11 recommended), usable by your standard account from the Terminal,' >&2
  echo 'as provided or approved by the company (software centre). Then run this command again.' >&2
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
