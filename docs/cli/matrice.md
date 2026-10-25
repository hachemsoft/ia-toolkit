# Matrice des CLI

Le contenu du kit (pratiques, skills, commandes, agents, garde-fous) est écrit une fois, sans rien de propre à une CLI. Chaque CLI le reçoit par son adaptateur, à l'endroit et dans la forme qu'elle lit. Cette page dit où, CLI par CLI. Pour en brancher une nouvelle, on remplit sa colonne : c'est le cahier des charges de son adaptateur.

## Où en est chaque CLI

| CLI | Adaptateur | Vérifiée sur | Page |
| --- | --- | --- | --- |
| Gemini CLI | ✅ intégrée | 0.65 | [Gemini CLI](gemini.md) |
| Antigravity CLI (agy) | ✅ intégrée | 1.4.7 | [Antigravity CLI](agy.md) |
| Codex CLI | ✅ intégrée | 0.160 | [Codex CLI](codex.md) |
| Claude Code | ❌ pas d'adaptateur | — | — |
| GitHub Copilot CLI | ❌ pas d'adaptateur | — | — |

Une CLI sans adaptateur peut déjà lire les fichiers de repo du kit (`AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`) si elle lit `AGENTS.md`, mais elle n'a ni les couches globales, ni les commandes, ni les skills, ni les garde-fous du kit.

## Notion par notion

| Notion du kit | Gemini CLI | Antigravity CLI (agy) | Codex CLI |
| --- | --- | --- | --- |
| Dossier de la CLI | `~/.gemini/` | `~/.gemini/` (lu aussi par agy) et `~/.gemini/config/plugins/ai-kit/` | `~/.codex/` |
| Couches de contexte (`00_KIT`, `10_COMPANY`, `20_TEAM`) | fichiers dans `~/.gemini/`, déclarés dans `context.fileName` de `settings.json` | incluses par chemin depuis `rules/AGENTS.md` du plugin | bloc géré en tête de `~/.codex/AGENTS.md` |
| Contexte personnel `30_USER.md` | `~/.gemini/30_USER.md`, déclaré dans `context.fileName` | inclus par chemin depuis le plugin | copié dans ce bloc à chaque `update` |
| Contexte du repo | `AGENTS.md` ou `GEMINI.md`, à la racine et dans les dossiers traversés | `AGENTS.md`, `GEMINI.md`, `.agents/rules/` | `AGENTS.md` (et `AGENTS.override.md`), à la racine et dans les dossiers |
| Skills du kit | `~/.gemini/skills/<nom>/SKILL.md` | les mêmes (`~/.gemini/skills/`) | `~/.codex/skills/<nom>/SKILL.md`, « sur commande seulement » respecté (`agents/openai.yaml`) |
| Skills d'un repo | `<repo>/.agents/skills/` ou `<repo>/.gemini/skills/` | `<repo>/.agents/skills/` | `<repo>/.agents/skills/` |
| Commandes (`commands/<nom>.md`) | `~/.gemini/commands/<nom>.toml` | un skill de commande `~/.gemini/skills/<nom>/` (dans agy, tout skill est une commande) | un skill de commande, appelé par `$<nom>` |
| Surcharger une commande dans un repo | `<repo>/.gemini/commands/<nom>.toml` | `<repo>/.agents/skills/<nom>/SKILL.md` | `<repo>/.agents/skills/<nom>/SKILL.md` |
| Agents | `~/.gemini/agents/ai-kit-<nom>.md` | `agents/` du plugin | `[agents.ai-kit-<nom>]` dans le bloc géré de `config.toml` |
| Garde-fous | groupes `ai-kit-*` sous `hooks.BeforeTool` de `settings.json` | `hooks.json` du plugin (`PreToolUse`) | `[[hooks.PreToolUse]]` dans ce bloc, à approuver dans Codex (« Trust ») |
| Chemins protégés d'un repo | `<repo>/.ai-kit/protected-paths`, lu par le script du kit | le même fichier, lu par le même script | le même fichier, lu par le même script |
| MCP | `mcpServers` de `settings.json` | `mcp_config.json` du plugin | `[mcp_servers.ai-kit-<nom>]` dans ce bloc |
| Permissions | mode d'approbation de Gemini | règles de chaque personne dans `~/.gemini/antigravity-cli/settings.json`, jamais écrites par le kit | bac à sable et approbations de Codex, jamais réglés par le kit |
| Journaux lus par `usage` | `~/.gemini/tmp/*/chats/*.json` | `~/.gemini/antigravity-cli/history.jsonl` | `~/.codex/history.jsonl` |
| Appel réel de `doctor --live` | `gemini -p` | non (agy est vérifié par `agy plugin validate`) | non (`codex doctor` vérifie sa configuration) |
| Évaluations | `evals/run.py --cli gemini` | `evals/run.py --cli agy` | `evals/run.py --cli codex` |
| Authentification réglée par le kit | sur déclaration : `vertex`, `code_assist`, `model` dans `overrides.json` | jamais ; voir [la page agy](agy.md#authentification--compte-ou-projet-google-cloud) | jamais (`codex login`) |
| Page détaillée | [Gemini CLI](gemini.md) | [Antigravity CLI](agy.md) | [Codex CLI](codex.md) |

**Où vivent les couches et `30_USER.md`.** Gemini n'importe que des fichiers situés dans `~/.gemini` (vérifié sur la 0.65). Quand Gemini est installé, les couches et `30_USER.md` sont donc dans `~/.gemini/`, et agy et Codex les lisent depuis là. Sans Gemini (`--target codex`, `--target agy`, ou un poste où seule une autre CLI est détectée), ils sont dans `~/.ai-kit/context/`, et aucun dossier `~/.gemini` n'est créé pour Codex. Si l'emplacement change, `30_USER.md` est recopié au nouvel endroit s'il y manque ; l'ancien n'est jamais supprimé. `doctor` indique le fichier en vigueur.

## Ajouter une CLI

Une nouvelle CLI, c'est un module dans `installer/adapters/`, ajouté à la liste `ADAPTERS`, qui respecte le contrat `Adapter` de `installer/interface.py`, sa colonne dans le tableau ci-dessus et ses scénarios dans `tests/snapshot.py`. Ce que cet adaptateur doit savoir faire : où écrire chaque ligne ci-dessus, comment la CLI charge un contexte global sans copier `30_USER.md`, sous quelle forme elle reçoit une commande, et comment elle passe un appel d'outil à un script de garde-fou (le JSON qu'elle envoie et la réponse qu'elle attend).
