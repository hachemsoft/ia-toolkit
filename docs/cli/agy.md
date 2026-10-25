# Antigravity CLI (agy)

Le kit vise Gemini CLI et Antigravity CLI avec une seule source. Quand `agy` est présent sur le poste (ou le dossier `~/.gemini/config/`), `setup` et `update` installent aussi la sortie Antigravity ; `--target gemini` l’empêche, `--target both` la force avec Gemini, `--target agy` l’installe seule (les couches vont alors dans `~/.ai-toolkit/context/`).

## Ce qui est partagé sans rien faire

- **Les skills** : agy lit `~/.gemini/skills/`, donc les skills du kit, les playbooks métier et les skills de repo (`.agents/skills/`) sont visibles des deux côtés.
- **Le contexte du repo** : `AGENTS.md`, `GEMINI.md`, `GLOSSARY.md`, `REVIEW.md`, les `.agents/rules/`.
- **`30_USER.md`** et les couches du kit, via le plugin ci-dessous.

## Ce que le kit ajoute pour agy

Un plugin `~/.gemini/config/plugins/ai-kit/`, validé par `agy plugin validate` dans `doctor` :

| Fichier | Rôle |
| --- | --- |
| `plugin.json` | nom, description, version du kit |
| `rules/AGENTS.md` | règles toujours actives qui incluent les quatre couches par chemin (`@[00_kit](~/.gemini/00_KIT.md)`, …, `@[30_user](~/.gemini/30_USER.md)`, ou `~/.ai-toolkit/context/` sans Gemini) : une seule source, aucune copie |
| `agents/ai-kit-*.md` | les mêmes agents que Gemini (vérificateur, revue adverse, revue SQL, dbt, code) ; visibles dans agy |
| `hooks.json` | les deux garde-fous, `enabled` suivant `overrides.json`, charge utile agy (`toolCall.args.CommandLine`) comprise par les scripts |
| `mcp_config.json` | les MCP activés dans `overrides.json`, quand il y en a |

Et des **skills de commande** dans `~/.gemini/skills/` : agy n’a pas de fichiers de commande, mais tout skill est une commande `/<nom>`. Pour chaque commande du profil sans skill homonyme (`intent`, `spec`, `build`, `test`, `review`, `ship`, `diagnose`, `design`, `map`, `learn`, `explain`, `ask`, `audit`), le kit génère un skill du même nom dont le corps est le prompt de la commande. `/guide`, `/retro`, `/triage`, `/research`, `/handoff`, `/wizard` existent déjà comme skills. Dans Gemini, ces skills de commande sont aussi visibles : leur description précise de ne s’activer que sur la commande ou une demande explicite.

Après l’installation, redémarrer agy : un nouveau plugin n’est découvert qu’au démarrage.

## Vérifié le 25 octobre 2026 sur agy 1.4.7

- `agy plugin validate` passe ; `agy plugin list` montre `ai-kit` avec les agents du profil (6 pour un développeur, 4 pour un analyste), 1 règle, 2 hooks.
- En mode print, agy cite mot pour mot la section « Priorité entre les couches » de `00_KIT.md` : les inclusions par chemin fonctionnent.
- Les agents `ai-kit-*` du profil sont listés par agy.
- `/guide` et `/intent` fonctionnent par les skills de commande ; `/guide` route vers `/diagnose` pour un modèle dbt qui double des lignes.

## Limites connues

- **Mode print et permissions** : agy abandonne toute la réponse dès qu’un outil demande une permission qu’il ne peut pas poser. Les commandes qui lisent le repo (`/intent`, `/explain`, `/test`) échouent donc en `agy -p` tant que la personne n’a pas validé de règles de lecture dans ses propres réglages agy. En interactif, agy demande la permission et tout fonctionne. Le runner d’évaluations classe ce cas en erreur d’infrastructure, pas en échec de comportement.
- **Outil d’écriture** : le garde-fou `protected-paths` reconnaît les outils dont le nom contient `write`, `replace` ou `edit` et cherche le chemin dans `TargetFile`, `AbsolutePath`, `file_path` ou `path`. À confirmer sur un vrai appel d’écriture agy.
- **Champ `tools` des agents** : accepté par le validateur ; son effet exact dans agy n’est pas documenté.
- **Journaux** : `usage` lit `~/.gemini/antigravity-cli/history.jsonl` (prompts et commandes tapées) ; les activations de skills ne sont pas visibles dans ce fichier.

## Authentification : compte ou projet Google Cloud

Par défaut agy signe avec le compte Google de la personne et consomme son quota individuel ; quand il est épuisé, agy répond « Individual quota reached » (HTTP 429) jusqu’à la réinitialisation. Une organisation peut à la place faire signer agy avec les identifiants applicatifs Google Cloud et facturer un projet : variable d’environnement `AGY_ADC_AUTH=1` dans le shell, identifiants posés par `gcloud auth application-default login`, et projet de quota de ces identifiants (`gcloud auth application-default set-quota-project <projet>`) avec l’API Agent Platform (`aiplatform.googleapis.com`) activée. C’est le projet de quota des identifiants qui compte, pas `GOOGLE_CLOUD_PROJECT`. Exemple, sur un poste qui a déjà fait `gcloud auth application-default login` :

```sh
gcloud auth application-default set-quota-project mon-projet-gcp
export AGY_ADC_AUTH=1   # dans le profil du shell pour que ce soit permanent
agy
```

Un 403 « Agent Platform API has not been used in project … » dit que l’API n’est pas activée sur ce projet de quota : `gcloud services enable aiplatform.googleapis.com --project mon-projet-gcp`. Les modèles proposés par `/model` dépendent alors de ce que le projet peut utiliser. Le kit ne règle pas cette variable : elle relève du poste et de l’organisation, comme pour Vertex côté Gemini CLI (`vertex` dans `overrides.json`).

## Permissions : à chaque personne, jamais au kit

agy demande l’accord avant une commande shell ou une écriture, et propose de retenir la réponse. Ces règles (`permissions.allow` dans `~/.gemini/antigravity-cli/settings.json`) sont celles du poste et de la personne : elles reflètent ce qu’elle accepte que l’agent fasse chez elle. Le kit ne les écrit pas, ne les lit pas pour les modifier et ne touche jamais à ce fichier ; `update` le laisse intact (vérifié par un test). Une organisation qui veut un socle de règles le fait par sa propre distribution de settings, hors du kit, pour que les choix de chacun ne soient pas écrasés.

## Dépannage

`doctor` valide le plugin et signale les skills du kit masqués par des copies dans `~/.agents/skills`. Les skills de commande peuvent entrer en collision avec d’anciens skills personnels du même nom (`review`, `diagnose`, `test`…) : les déplacer ou les renommer, `update` refuse d’écraser ce qu’il ne gère pas.
