"""Un module par CLI, tous avec la même interface :

- NAME, LABEL, COMMAND, HOME_DIR : nom, libellé, exécutable, dossier de la CLI dans le dossier personnel ;
- context_dir(home), facultatif : la CLI ne lit son contexte que dans ce dossier ; s'il est actif, les couches et 30_USER.md y sont écrits
  (sinon dans ~/.ai-toolkit/context, que les autres CLI incluent ou recopient). Le premier de ADAPTERS est la CLI par défaut ;
- present(home) : la CLI est-elle sur le poste ; is_managed(rel) : chemin qu'il peut retirer s'il est intact ; active_account(home) : compte actif connu, ou None ;
- install(p) : fichiers de la CLI, écrits par p.managed_write à partir du plan neutre p ;
- finalize(p) : réglages ou blocs gérés, une fois les garde-fous et MCP connus ;
- summary(p) : une ligne pour la fin de l'installation, ou None ;
- doctor(home, state, status, ctx), doctor_hint() : contrôles et ligne de fin de doctor ;
- history(home, state) : événements d'usage neutres (prompt, skill, agent, erreur) lus dans les journaux de la CLI ;
- live(home), facultatif : appel réel au modèle.

Ajouter une CLI = écrire un module ici et l'ajouter à ADAPTERS ; voir docs/cli/matrice.md.
"""
from . import gemini, agy, codex

ADAPTERS = (gemini, agy, codex)
