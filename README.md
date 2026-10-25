# Kit IA

Un socle pour travailler avec un agent de code en équipe, sur Mac et Windows. Il configure les CLI d’agent présentes sur le poste (**Gemini CLI**, **Antigravity CLI** et **Codex CLI**) avec le même contenu : un contexte en couches, un workflow en commandes, des playbooks métier, des agents de revue et des garde-fous. Le contexte technique et métier reste dans chaque repo.

## Pour commencer

1. **Installer** : `git clone <url du dépôt> ai-toolkit` (sans git : « Télécharger ZIP » sur la page du dépôt, puis extraire). Ouvrir un terminal dans ce dossier, puis lancer `sh scripts/bootstrap.sh` (Mac) ou `.\scripts\bootstrap.ps1` (Windows). Confirmer l’identité, puis choisir le profil le plus proche de votre métier ; en cas de doute, **Général**.
2. **Vérifier** : l’installation se termine par un appel réel au modèle. Vert, c’est fini. Sinon, le message dit quoi faire.
3. **Utiliser** : ouvrir votre repo (`cd` dedans), lancer votre CLI (`gemini`, `agy` ou `codex`), taper `/guide je dois …` (`$guide` dans Codex) : il dit quelle commande taper. La première fois dans un repo : « Initialise le contexte du projet ».
4. **Quand ça coince** : `sh scripts/bootstrap.sh doctor --live` (Mac) ou `.\scripts\bootstrap.ps1 doctor --live` (Windows), puis la page [Ça coince ?](docs/ca-coince.md).

Prérequis : Python 3.9 ou plus récent. Le kit n’installe aucune dépendance. La CLI et son authentification viennent de la procédure de votre organisation ; si elle impose un projet cloud ou un modèle, c’est une ligne dans `~/.ai-toolkit/overrides.json`. Le pas-à-pas complet : [démarrer](docs/getting-started.md).

Mise à jour : `git pull` dans le dossier du kit, puis `sh scripts/bootstrap.sh update` (Windows : `.\scripts\bootstrap.ps1 update`).

## Profils

| Profil | Pour | Ajoute au socle |
| --- | --- | --- |
| **Général** | tout métier du développement | — (workflow, outils, revue de code) |
| **Développeur Java** | Maven ou Gradle, Spring, JUnit | playbook `java-change`, revue de sécurité |
| **DevOps** | Terraform, Kubernetes, Helm, CI/CD | playbook `infra-change`, revues d’infrastructure et de sécurité |
| **Architecte** | décisions d’architecture, conception | playbook `architecture-decision` (ADR), revue d’architecture |
| **Data Analyst** | SQL, dbt, BigQuery, indicateurs | playbooks SQL, dbt, BigQuery et KPI, revues SQL et dbt |
| **Développeur Data** | les mêmes, plus Python et JavaScript | les mêmes, plus `python-js-change` et la revue de code |

Commandes et agents installés par profil : [démarrer](docs/getting-started.md#3-travailler--une-commande-par-étape). Tout s’ajuste par personne dans `~/.ai-toolkit/overrides.json` (un skill, une commande ou un agent d’un autre profil, des garde-fous, des MCP) : [personnalisation](docs/customization.md).

## Ce que c’est

Un **cadre** d’abord : le kit installe sur le poste un socle qui ne décide rien à la place de l’équipe. Il pose des couches de contexte (pratiques entreprise, pratiques d’équipe, préférences personnelles), lues avant le contexte du repo. Il fournit des profils, des agents, des garde-fous, un fichier de surcharges, une revue d’usage et des évaluations. C’est de l’outillage et des règles de priorité, pas une procédure.

Dans ce cadre, un **workflow** : une commande par étape du cycle de développement (`/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`) et une chaîne d’artefacts (`intent.md`, `spec.md`, `plan.md`, constats de revue, description de MR). La cérémonie suit les enjeux : une retouche se fait sans commande, une petite fonctionnalité avec `/intent` court puis `/build`, et seuls une grande évolution ou un changement en production déroulent tout. Ce sont des prompts et des skills que le modèle suit, plus deux garde-fous déterministes pour ce qui doit être garanti. Voir [workflow](docs/workflow.md).

À côté, des **outils** (`/guide`, `/learn`, `/explain`, `/retro`, `/friction`) et des **playbooks métier** activés quand la tâche s’y prête ; les vôtres s’ajoutent de la même façon. Voir [outils](docs/tools.md) et [ajouter un skill](docs/extending.md).

Les quatre exigences du projet : une installation simple, Mac et Windows, une extension sans toucher aux fichiers du kit, et plusieurs CLI, avec un adaptateur chacune.

## CLI prises en charge

| CLI | État | Commandes |
| --- | --- | --- |
| Gemini CLI | ✅ | `/guide` |
| Antigravity CLI (`agy`) | ✅ | `/guide` |
| Codex CLI | ✅ | `$guide` |

Versions vérifiées, où chaque fichier est posé et ce qui diffère d’une CLI à l’autre : [matrice des CLI](docs/cli/matrice.md).

## Documentation

- **Utiliser** : [démarrer](docs/getting-started.md), [workflow](docs/workflow.md), [outils](docs/tools.md), [agents](docs/agents.md), [couche projet](docs/project-context.md), [Ça coince ?](docs/ca-coince.md).
- **Personnaliser** : [personnalisation](docs/customization.md), [ajouter ou remplacer un skill](docs/extending.md), [garde-fous](docs/hooks.md), [MCP](docs/mcp.md), [identité](docs/identity.md).
- **Par CLI** : [matrice](docs/cli/matrice.md), [Gemini CLI](docs/cli/gemini.md), [Antigravity CLI](docs/cli/agy.md), [Codex CLI](docs/cli/codex.md), [passer de Gemini à agy](docs/cli/gemini-vers-agy.md).
- **Déployer et maintenir** : [l’installeur](docs/installeur.md), [contribution](docs/contributing.md), [format des commandes](docs/format.md), [référence des skills](docs/skills-reference.md), [évaluations](docs/evals.md), [revue d’usage](docs/usage-review.md), [pilote](docs/pilote.md), [sources](docs/sources.md), [historique](CHANGELOG.md).

## Licence

MIT, voir [LICENSE](LICENSE). Les skills du socle repris d’un dépôt amont gardent leur propre licence MIT, dans `skills/LICENSE-UPSTREAM-MIT`.
