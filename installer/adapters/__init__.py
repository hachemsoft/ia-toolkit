"""One module per CLI. The contract each module follows is in installer/interface.py:
Adapter (required), ContextHost and LiveCheck (optional capabilities).

The first of ADAPTERS is the default CLI, installed when no CLI is detected.
Adding a CLI = writing a module here and adding it to ADAPTERS; see docs/cli/matrice.md.
"""
from . import gemini, agy, codex, claude

ADAPTERS = (gemini, agy, codex, claude)
