# Faire évoluer le kit

1. Modifier les pratiques générales dans practices/ ; le préfixe numérique du fichier (`10-company.md`) fixe sa position dans le contexte de l’agent. Garder les faits métier dans les projets.
2. Ajouter un skill avec un nom unique, un SKILL.md court et son entrée dans skills/catalog.json : sous `skills/contrib/` avec un propriétaire nommé quand c’est une proposition d’équipe, sous `skills/internal/` quand les mainteneurs du kit le prennent en charge ; la marche complète (catalogue, profils, commande, cas d’évaluation) est dans [ajouter ou remplacer un skill](extending.md).
3. Sélectionner les skills dans les profils. Ne pas installer tout le catalogue par défaut.
4. Pour les skills repris d’un dépôt amont, recopier les dossiers tels quels dans skills/internal/common/, retirer les fichiers propres à d’autres outils, conserver le texte de licence (skills/LICENSE-UPSTREAM-MIT) et relancer les tests ; aucun téléchargement automatique.
5. Ajouter un MCP uniquement après validation du serveur, du transport, de l’authentification et de ses prérequis Windows/Mac. Ne pas committer de secrets.
6. Exécuter les tests, faire un essai avec --home dans un dossier temporaire, puis rejouer les évaluations (`python3 evals/run.py`) quand un skill, une commande ou une pratique change. Quand l’agent se trompe, ajouter le prompt fautif comme cas d’évaluation avant de corriger le skill.
7. Valider ensuite sur un vrai Mac et un poste Windows standard sans administrateur, puis dans chaque CLI prise en charge, authentifiée.
8. Publier : la version est dans `VERSION` et dans `pyproject.toml` (un test vérifie qu’elles sont égales) ; commit, tag `v<version>`, push. Les utilisateurs font `git pull` puis `update`. `sh scripts/package.sh` construit une archive hors git si besoin. Pour les développeurs qui préfèrent `pipx` : `pipx install git+<url du dépôt>` fournit la commande `ai-kit` (même chose que le lanceur) ; ce n’est pas la voie documentée pour l’équipe. `python3 -m build` construit le paquet, qui embarque le contenu sous `ai_kit/kit/`. Un nouveau dossier de contenu lu par l’installeur s’ajoute à `[tool.hatch.build.targets.wheel.force-include]` ; le test de paquet échoue sinon. `update` applique la version extraite ou installée.

Les commandes sont écrites une fois dans `commands/<nom>.md` ([format pivot](format.md)). Le contenu ne dépend d’aucune CLI : gabarits dans `templates/` (dont `kit-context.md`, qui devient `00_KIT.md`), agents et leurs réglages par défaut dans `agents/`, profils et annuaire de l’organisation (domaines autorisés, profil par email) dans `profiles/`, scripts installés et exécutés sur le poste (garde-fous, frictions) dans `runtime/`. Seules les données propres à une CLI vivent avec son code (`installer/adapters/gemini_defaults.json`). Le code suit le même découpage : `installer/core.py` pour les briques communes, `installer/cli.py` pour l’orchestration (un plan neutre de ce qu’il faut installer), et un module par CLI dans `installer/adapters/` (`gemini.py`, `agy.py`, `codex.py`), tous avec la même interface, décrite dans `installer/interface.py` : le plan neutre (`Plan`), le contexte de `doctor` et le contrat des adaptateurs (`Adapter`, plus deux capacités facultatives, `ContextHost` et `LiveCheck`). `cli.py` ne nomme aucune CLI : il ne parle qu’à cette interface, et un test vérifie que chaque adaptateur la respecte. Le test photo (`tests/snapshot.py`) garantit qu’un changement de code ne modifie aucun fichier installé sans que la référence soit réécrite exprès ; la [matrice des CLI](cli/matrice.md) dit ce que chacun produit ; la sortie Antigravity (plugin, skills de commande) en fait partie. Une CLI de plus est un module d’adaptateur de plus : voir [ajouter une CLI](#ajouter-une-cli).

Critères de recette : installation sans édition obligatoire, conservation de `30_USER.md`, changement de profil, conflits non destructifs, découverte des skills et connexion des MCP configurés.

Quand une version corrige des frictions remontées, le `CHANGELOG` le dit en une ligne, avec le nombre de signalements.

Règle de support : un ticket ne se règle jamais deux fois à l’oral. Chaque ticket devient un contrôle de `doctor` (avec son remède), une ligne de `docs/ca-coince.md`, ou un cas d’évaluation dans `evals/cases/`. Le kit est corrigé sur les tickets réels, pas sur des suppositions.

Avant une MR : `python3 -m unittest discover -s tests` et `ruff check .` (installé par `pip install -e '.[dev]'`, ou sans installation avec `uvx ruff check .`). La CI lance les deux.

## Ajouter un profil

1. `profiles/<id>.json` : `practices`, `skills` (partir de `general.json`, puis ajouter le playbook métier), `agents`, `mcp.recommended`, et `commands` seulement pour restreindre la liste (sinon toutes celles dont les skills sont installés).
2. Le playbook métier, s’il y en a un : [ajouter un skill](extending.md#pour-lorganisation--dans-le-kit), catégorie `domain` ; le brancher dans `commands/build.md` ou `commands/diagnose.md` « si installé ».
3. Le menu de `setup` : une ligne dans `PROFILE_MENU` (`installer/cli.py`).
4. Les tests : la liste des profils (`tests/test_profiles_general.py`), un scénario dans `tests/snapshot.py` puis `python3 tests/snapshot.py --update`, et la table des profils : `python3 scripts/profile_table.py --write`.
5. Le profil dans le README (table des profils).

## Ajouter une CLI

Voir [ajouter une CLI](cli/matrice.md#ajouter-une-cli) : un module dans `installer/adapters/`, son entrée dans `ADAPTERS`, sa colonne dans la matrice, sa page dans `docs/cli/`.
