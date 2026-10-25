#!/bin/sh
set -eu
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v python3 >/dev/null 2>&1; then
  KIT_PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  KIT_PYTHON=python
else
  echo 'Python introuvable. Demander à votre support IT de rendre Python accessible dans le terminal.' >&2
  exit 2
fi
# Le dossier courant reste celui de l'utilisateur : un chemin relatif (--json, --home) se résout chez lui, pas dans le kit.
if [ "$#" -eq 0 ]; then set -- setup; fi
PYTHONPATH="$KIT_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$KIT_PYTHON" -m installer "$@"
