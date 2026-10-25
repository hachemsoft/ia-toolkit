# Kit IA

Un socle pour les CLI d’agent de code (Gemini CLI, Antigravity CLI et Codex CLI intégrées ; état CLI par CLI dans la [matrice des CLI](docs/cli/matrice.md)), Mac et Windows, pour une équipe qui travaille avec un agent de code : contexte global en couches, workflow en six étapes, outils, playbooks métier optionnels, agents de revue et configuration MCP optionnelle. Trois profils : **Data Analyst**, **Développeur Data** et **Général** (le workflow et les outils, sans playbook métier). Le contexte technique et métier appartient à chaque repo projet.

## Pour commencer

1. **Installer** : récupérer le kit avec `git clone <url du dépôt> ai-toolkit` (sans git : bouton « Télécharger ZIP » du dépôt, puis extraire), ouvrir un terminal dans ce dossier, lancer `sh scripts/bootstrap.sh` (Mac) ou `.\scripts\bootstrap.ps1` (Windows). Sous Windows, pour ouvrir le terminal au bon endroit : dans l’Explorateur, taper `powershell` dans la barre d’adresse du dossier. Confirmer l’identité, puis choisir le profil : **Data Analyst** si vous écrivez surtout du SQL, du dbt et des requêtes BigQuery ; **Développeur Data** si vous livrez aussi du code Python ou JavaScript ; **Général** pour tout autre métier.
2. **Vérifier** : l’installation se termine par un appel réel au modèle. Vert, c’est fini. Sinon, le message dit quoi faire ; ne rien chercher ailleurs.
3. **Utiliser** : ouvrir votre repo (`cd` dedans), lancer votre CLI (`gemini` ou `agy`), taper `/guide je dois …` : il dit quelle commande taper. La première fois dans un repo, écrire « Initialise le contexte du projet ».
4. **Quand ça coince** : `sh scripts/bootstrap.sh doctor --live` (Mac) ou `.\scripts\bootstrap.ps1 doctor --live` (Windows), puis la page [Ça coince ?](docs/ca-coince.md).

Pas à pas, avec un exemple par commande : [démarrer](docs/getting-started.md). Le reste de cette page décrit le kit pour qui le déploie ou le maintient.

## Ce que c’est

Un **cadre** d’abord : le kit installe sur le poste un socle qui ne décide rien à la place de l’équipe. Des couches de contexte (pratiques entreprise, pratiques d’équipe, préférences personnelles, contexte du repo), des profils, des agents, des garde-fous, un fichier de surcharges, une revue d’usage, des évaluations. De l’outillage et des règles de priorité, pas une procédure.

Dans ce cadre, un **workflow** : les six étapes du cycle de développement, une commande par étape (`/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`) et une chaîne d’artefacts (`intent.md`, `spec.md`, `plan.md`, constats de revue, description de MR). La structure vient du « AI-native SDLC playbook », les mécanismes des meilleurs packs de skills publics.

Un workflow **à géométrie variable** : la cérémonie suit les enjeux. Une retouche se fait sans commande, une petite fonctionnalité avec `/intent` court puis `/build`, et seuls une grande évolution ou un changement en production déroulent tout. Aucun moteur ne l’impose : ce sont des prompts et des skills que le modèle suit, plus deux garde-fous déterministes pour ce qui doit être garanti.

À côté, les **outils** (`/guide`, `/learn`, `/explain`, `/retro`) et les **playbooks métier** (livrés : SQL, dbt, BigQuery, KPI ; les vôtres s’ajoutent de la même façon) : du savoir-faire activable à tout moment, hors de toute étape.

En une phrase : un cadre d’installation et de personnalisation, qui livre un workflow optionnel et proportionné, plus des playbooks métier. Le cadre est stable ; le workflow et les playbooks sont du contenu qu’on ajuste. C’est ce qui tient les quatre exigences du projet : installation simple, Mac et Windows, extensible sans toucher aux fichiers du kit, et compatible avec plusieurs CLI par un adaptateur chacun.

## Démarrage en deux minutes

1. Récupérer le kit dans un dossier durable, par exemple `Documents` :

   ```sh
   git clone <url du dépôt> ai-toolkit
   cd ai-toolkit
   ```

   Sans git sur le poste : bouton « Télécharger ZIP » (ou « Code › Download ZIP ») sur la page du dépôt, puis extraire dans `Documents/ai-toolkit`.
2. Ouvrir un terminal dans ce dossier, celui qui contient ce README.
3. Lancer la commande de votre système, confirmer l’identité détectée et choisir un profil.

**Mac**

```sh
sh scripts/bootstrap.sh
```

**Windows — PowerShell**

```powershell
.\scripts\bootstrap.ps1
```

Si la politique de votre entreprise bloque les scripts PowerShell, utiliser Python directement depuis ce dossier, sans modifier la politique :

```powershell
py -3 -m installer setup
```

Si `py` est absent mais `python` fonctionne : `python -m installer setup`.

Prérequis : Python 3.9+ utilisable dans le terminal. Le kit n’installe aucune dépendance.
La CLI et son authentification doivent être disponibles via la procédure IT approuvée ; le kit peut préparer les fichiers avant leur installation. Si votre organisation impose un projet Google Cloud (Code Assist sous licence, Vertex AI) ou un modèle, une ligne dans `~/.ai-toolkit/overrides.json` suffit ; sinon rien à déclarer. Versions vérifiées et particularités de chaque CLI : [matrice des CLI](docs/cli/matrice.md).

## Utilisation

| Action | Mac | Windows PowerShell |
| --- | --- | --- |
| Installer / changer de profil | `sh scripts/bootstrap.sh setup` | `.\scripts\bootstrap.ps1 setup` |
| Appliquer une nouvelle version (après `git pull`) | `sh scripts/bootstrap.sh update` | `.\scripts\bootstrap.ps1 update` |
| Diagnostiquer | `sh scripts/bootstrap.sh doctor --live` | `.\scripts\bootstrap.ps1 doctor --live` |
| Relevé d’usage | `sh scripts/bootstrap.sh usage` | `.\scripts\bootstrap.ps1 usage` |

Exemple non interactif : `python3 -m installer setup --profile data-analyst --user prenom.nom@societe.fr`.
`setup` termine par un appel réel au modèle et donne le remède si l’agent ne répond pas. Dans la CLI, ouvrir un repo et taper `/guide` pour savoir par quoi commencer ; les commandes de vérification propres à chaque CLI sont sur sa page (voir la [matrice des CLI](docs/cli/matrice.md)).

## Ce que le kit installe

**Contexte global en couches**, dans le dossier de la CLI, chargé dans tous vos projets dans cet ordre :

| Fichier | Propriétaire | Contenu |
| --- | --- | --- |
| `00_KIT.md` | kit | profil, priorité entre les couches, étapes du workflow et skills installés |
| `10_COMPANY.md` | kit | pratiques entreprise |
| `20_TEAM.md` | kit | pratiques d’équipe |
| `30_USER.md` | vous | langue, style, niveau, domaines, workflow par défaut ; créé une fois, jamais réécrit |

L’`AGENTS.md` de chaque repo est lu ensuite et l’emporte sur `30_USER.md`. Les fichiers sont lus les uns après les autres ; la priorité est écrite dans `00_KIT.md`.

**Commandes**, une par étape du cycle de développement : `/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`, trois pour les développeurs : `/design`, `/map`, `/triage`, et des outils hors flux : `/guide`, `/learn`, `/explain`, `/retro`, `/friction`, plus en option `/ask`, `/handoff`, `/research`, `/wizard`, `/audit`. Chaque étape produit un artefact que la suivante lit (`intent.md`, `spec.md`, `plan.md`, diff et tests, description de MR) ; `spec.md` est versionné, `intent.md` et `plan.md` sont des notes locales. La cérémonie suit les enjeux : une retouche se fait sans artefact. Voir [workflow](docs/workflow.md) et [outils](docs/tools.md).

**Skills**, sous les commandes : un socle repris d’un dépôt amont et des playbooks Data en français. Les utilisateurs n’ont pas à connaître leurs noms ; la liste est dans [la référence](docs/skills-reference.md).

- **data-analyst** : sept commandes, `/guide`, `/intent`, `/build`, `/test`, `/ship`, `/diagnose`, `/learn`, plus `/friction` pour noter ce qui coince, et les playbooks SQL, dbt, BigQuery et KPI.
- **data-developer** : les mêmes plus `/spec`, `/review`, `/design`, `/map`, `/triage`, `/explain`, `/retro`, les mêmes playbooks et la modification Python/JS.
- **general** : `/guide`, `/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`, `/learn`, `/explain`, `/retro`, sans playbook métier ; les playbooks s’ajoutent avec `extra_skills`.
- Une commande en plus ou en moins : `extra_commands` / `disabled_commands` dans `~/.ai-toolkit/overrides.json`, puis `update`.

**Agents** : exploration du repo, revue SQL, revue dbt et revue Python/JS en lecture seule, un vérificateur qui lance les checks du repo en fin de `/build`, et pour les développeurs un agent de doute appelé par `/review full`. Voir [agents](docs/agents.md).

**Garde-fous**, désactivés par défaut : refus d’une commande dbt sur un target de production, refus d’écriture sous des chemins protégés. Voir [garde-fous](docs/hooks.md).

**Réglages** : seuls les réglages par défaut manquants sont ajoutés aux réglages de la CLI ; où chaque élément est posé, CLI par CLI : [matrice des CLI](docs/cli/matrice.md).

## Ce que fait l’installeur

- Ne choisit ni le mode d’authentification ni le modèle : connexion Google, Code Assist sous licence (`code_assist`), Vertex AI (`vertex`) ou clé API, et `model` seulement si vous le déclarez dans `overrides.json`. Voir [personnalisation](docs/customization.md#authentification-et-modèle).
- Détecte une identité déclarative (compte actif de la CLI, git, session OS), la fait confirmer et l’écrit en tête de `30_USER.md` à sa création. Voir [identité](docs/identity.md).
- Stocke profil, identité, surcharges, empreintes et sauvegardes dans `~/.ai-toolkit`.
- Refuse d’écraser les couches, skills, agents ou MCP gérés qui ont été modifiés à la main.
- Retire les anciens fichiers gérés lors d’un changement de profil ou de version s’ils sont intacts.
- Prévalide les conflits, sauvegarde, puis écrit les fichiers ; tente une restauration en cas d’erreur d’écriture.
- Ne touche à aucun repo projet, ne lance aucun serveur MCP, ne télécharge rien.

Les réglages existants doivent être du JSON strict. Un fichier JSON invalide ou contenant des commentaires est refusé sans modification. Les liens symboliques sur les chemins gérés ne sont pas pris en charge.

## Dans un repo

Première fois : « Initialise le contexte du projet ». Le skill `init-project-context` propose un `AGENTS.md` d’une page, un `GLOSSARY.md` pré-rempli avec le vocabulaire Data, un `REVIEW.md` et la règle git des notes locales, avec confirmation par fichier. Plus tard, si l’équipe veut que l’agent lise et crée des tickets : `setup-workflow` (demande `glab` ou `gh`). Voir [couche projet](docs/project-context.md).

## MCP

Le catalogue propose documentation, BigQuery et dbt. Aucun serveur n’est activé par défaut : vos endpoints, transports et authentifications ne sont pas connus. Voir [la configuration MCP](docs/mcp.md).

## Essai sans toucher à son compte

```sh
python3 -m installer setup --profile data-analyst --home ./sandbox-user --dry-run
python3 -m installer setup --profile data-analyst --home ./sandbox-user
python3 -m installer doctor --home ./sandbox-user
```

Sous Windows remplacer `python3` par `py -3`. `--home` ne s’applique qu’au kit, pas à la configuration réellement chargée par une CLI lancée normalement. `setup` et `update` finissent par un appel réel au modèle ; `--no-live` (ou `AI_KIT_NO_LIVE=1`) le saute, par exemple en CI.

## Mise à jour

Depuis le dossier du kit :

```sh
git pull
sh scripts/bootstrap.sh update        # Windows : .\scripts\bootstrap.ps1 update
```

Sans git : télécharger à nouveau le ZIP, remplacer le dossier, puis lancer `update`. `update` applique les fichiers du dossier ; il ne télécharge rien. Une version précise se prend par son tag : `git checkout v0.16.0`. Ne pas modifier les fichiers générés : personnaliser `30_USER.md` et `overrides.json`.

## Limites

- Chaque CLI a ses limites, décrites sur sa page : [Gemini CLI](docs/cli/gemini.md), [Antigravity CLI](docs/cli/agy.md), [Codex CLI](docs/cli/codex.md).
- Pratiques entreprise/Data proposées, à faire approuver avant diffusion.
- Les skills du socle sont repris d’un dépôt amont sous licence MIT (`skills/LICENSE-UPSTREAM-MIT`), en anglais ; leur mise à jour est manuelle.
- `research` et `implement-spec` (en option) délèguent à des sous-agents de la CLI ; sans eux, fonctionnement dégradé. `/map`, `/triage` et `to-tickets` attendent un gestionnaire de tickets déclaré par repo avec `setup-workflow`.
- Les skills du socle ont été écrits pour un autre outil : `00_KIT.md` donne au modèle la table de correspondance (sous-agents, `CLAUDE.md`, PR) ; leur marque « sur commande seulement » n’est comprise par aucune des CLI actuelles ; le kit la rappelle en contexte sans pouvoir la garantir.
- Pas de secrets embarqués, de gestion de parc ou de politique administrateur. L’identité détectée ne donne aucun droit.
- Pas de configuration de rôle, dataset, target dbt ou KPI spécifique aux projets.
- `doctor` vérifie fichiers, réglages, identité et exécutables, pas l’authentification, les droits IAM ou les appels MCP.
- Tests automatisés exécutables sur Mac/Windows/Linux ; cette version a été testée sous macOS. Découverte des couches et des skills vérifiée sur chaque CLI en bac à sable (versions dans la [matrice des CLI](docs/cli/matrice.md)) ; la recette sur vos postes reste à faire.
- Le contexte utilisateur global est chargé dans tous vos projets : utiliser un compte professionnel.

Tests : `python3 -m unittest discover -s tests -v`. Évaluations du comportement de l’agent : `python3 evals/run.py`, voir [évaluations](docs/evals.md).

Ça coince ? [docs/ca-coince.md](docs/ca-coince.md).

Documentation : [démarrer](docs/getting-started.md), [pilote](docs/pilote.md), [guide de bascule](docs/cli/gemini-vers-agy.md), [Antigravity](docs/cli/agy.md), [workflow](docs/workflow.md), [outils](docs/tools.md), [garde-fous](docs/hooks.md), [évaluations](docs/evals.md), [revue d’usage](docs/usage-review.md), [référence des skills](docs/skills-reference.md), [couche projet](docs/project-context.md), [personnalisation](docs/customization.md), [ajouter ou remplacer un skill](docs/extending.md), [format pivot des commandes](docs/format.md), [identité](docs/identity.md), [agents](docs/agents.md), [dépannage](docs/troubleshooting.md), [contribution](docs/contributing.md), [portabilité](docs/portability-report.md), [sources](docs/sources.md), [historique](CHANGELOG.md).

## Licence

MIT, voir [LICENSE](LICENSE). Les skills du socle repris d’un dépôt amont gardent leur propre licence MIT, dans `skills/LICENSE-UPSTREAM-MIT`.
