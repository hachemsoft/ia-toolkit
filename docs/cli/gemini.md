# Gemini CLI

Ce que le kit fait pour Gemini CLI, et ce qui est propre à cette CLI. Comportement vérifié sur Gemini CLI 0.65. Les notions communes sont dans la [matrice](matrice.md).

## Ce que le kit installe

- **Contexte** : `00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` et `30_USER.md` dans `~/.gemini/`, déclarés dans `context.fileName` de `~/.gemini/settings.json`, suivis de `GEMINI.md` et `AGENTS.md` pour les repos. Les noms personnels déjà présents dans `context.fileName` sont conservés.
- **Skills** dans `~/.gemini/skills/`, **commandes** dans `~/.gemini/commands/*.toml`, **agents** dans `~/.gemini/agents/ai-kit-*.md`.
- **Garde-fous** activés : scripts dans `~/.ai-kit/hooks/` (partagés par toutes les CLI), déclarés sous `hooks.BeforeTool` dans des groupes nommés `ai-kit-<nom>`. Vos propres hooks sont conservés.
- **MCP** activés dans `overrides.json` : entrées `ai-kit-<nom>` sous `mcpServers`.
- **Réglage par défaut** : `skills.enabled`, seulement s'il manque.

## Authentification et modèle

Le kit n'y touche que sur déclaration dans `overrides.json` ; détail dans [personnalisation](../customization.md#authentification-et-modèle).

| Déclaration | Effet dans Gemini |
| --- | --- |
| `vertex` | `security.auth.selectedType` sur `vertex-ai` ; `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` dans `~/.gemini/.env` |
| `code_assist` | `selectedType` sur `oauth-personal` ; `GOOGLE_CLOUD_PROJECT` dans `~/.gemini/.env` |
| `model` | `model.name` dans `settings.json` |

Les lignes du kit dans `.env` portent le commentaire `# ai-kit :` et disparaissent quand la clé est retirée.

## Vérifier dans Gemini

`/memory show` (les quatre couches avant le contexte du repo), `/commands list`, `/skills list`, `/agents list` (après `/agents reload`), `/mcp`.

## Particularités

- **Alias `~/.agents/skills`** : Gemini le lit aussi, et il l'emporte sur `~/.gemini/skills` à nom égal (« Skill conflict detected » au démarrage). `doctor` liste les skills du kit ainsi masqués.
- **Contexte des sous-dossiers** : lancé à la racine d'un repo, Gemini lit aussi les `AGENTS.md` et `GEMINI.md` des sous-dossiers ; un `.geminiignore` limite ce qu'il parcourt.
- **Mode non interactif (`gemini -p`)** : l'outil d'activation de skill n'est pas exposé ; les commandes du kit disent quoi faire sans lui. Le mode `plan` bloque aussi les skills.
- **Sous-agents** : activés par défaut depuis 0.65 ; un `experimental.enableAgents` à `false` les désactive, le kit le respecte et `doctor` le signale. L'en-tête `model:` d'un agent est lu (profils de capacité, voir [agents](../agents.md)).
- **Identité** : le compte Google actif est lu dans `~/.gemini/google_accounts.json` (champ `active`), jamais les jetons.

## Dépannage propre à Gemini

- **Gemini absent** : le kit prépare les fichiers mais n'installe pas Gemini ; utiliser la procédure IT, puis se connecter.
- **Contexte non chargé** : `/memory show` dans un repo ; si les couches manquent, vérifier `context.fileName` et une éventuelle politique administrée.
- **Variables Vertex ignorées** : `selectedType` vaut encore `gemini-api-key` ; déclarer `vertex` dans `overrides.json` puis `update`, ou `/auth`.
- **Bloc hérité dans `GEMINI.md`** (installations 0.0.x) : copier vos ajouts dans `~/.gemini/30_USER.md`, retirer le bloc entre les marqueurs `ai-kit` de `~/.gemini/GEMINI.md`, puis `update`.
- **Skill installé hors du kit** (par exemple `gemini skills install`) : le retirer, ou l'ajouter à `disabled_skills`.

Passer à agy : [ce qui change, ce qui ne change pas](gemini-vers-agy.md).
