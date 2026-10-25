"""Un module par CLI. Le contrat que chaque module respecte est dans installer/interface.py :
Adapter (obligatoire), ContextHost et LiveCheck (capacités facultatives).

Le premier de ADAPTERS est la CLI par défaut, installée quand aucune CLI n'est détectée.
Ajouter une CLI = écrire un module ici et l'ajouter à ADAPTERS ; voir docs/cli/matrice.md.
"""
from . import gemini, agy, codex

ADAPTERS = (gemini, agy, codex)
