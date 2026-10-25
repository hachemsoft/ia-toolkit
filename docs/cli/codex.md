# Codex CLI

Ce que le kit fait pour Codex CLI, et ce qui est propre à cette CLI. Vérifié sur Codex CLI 0.160. Les notions communes sont dans la [matrice](matrice.md).

## Installer pour Codex

`setup` et `update` installent pour Codex quand la commande `codex` est présente ou que `~/.codex` existe (`--target auto`) ; `--target all` le force avec les autres CLI, `--target codex` l’installe seul, `--target gemini` ou `both` l’exclut. Codex se connecte avec son propre compte (`codex login`, compte ChatGPT ou clé OpenAI) : le kit n’y touche pas.

## Ce que le kit installe

- **Contexte** : un bloc géré en tête de `~/.codex/AGENTS.md`, entre deux marqueurs `ai-kit`, avec les couches du kit et une copie de `30_USER.md` (dans `~/.gemini/` si Gemini est installé, sinon dans `~/.ai-toolkit/context/`). Le reste du fichier vous appartient et n’est jamais modifié. Codex n’incluant pas d’autres fichiers par chemin, la copie de `30_USER.md` est rafraîchie à chaque `update` : après l’avoir modifié, relancer `update` (`doctor` le signale).
- **Skills** dans `~/.codex/skills/`. Les skills marqués « sur commande seulement » reçoivent un `agents/openai.yaml` avec `allow_implicit_invocation: false` : Codex respecte cette marque nativement, il ne les active que si on les appelle.
- **Commandes** : un skill par commande, lui aussi sur commande seulement. Dans Codex, on les appelle par **`$intent`**, `$build`, `$test`… ; `/skills` les liste.
- **Agents** : un rôle `ai-kit-<nom>` par agent, déclaré sous `[agents.ai-kit-<nom>]` dans le bloc géré de `~/.codex/config.toml`, ses instructions dans `~/.codex/ai-kit/agents/`.
- **Garde-fous** activés : déclarés sous `[[hooks.PreToolUse]]` dans le même bloc ; les scripts comprennent le format d’appel de Codex, y compris les chemins d’un `apply_patch`.
- **MCP** activés : `[mcp_servers.ai-kit-<nom>]` dans le même bloc.

Le bloc de `config.toml` est ajouté à la fin du fichier, vérifié avant écriture (le fichier doit rester du TOML valide) ; vos propres réglages ne bougent pas. Les deux fichiers sont sauvegardés à chaque modification.

## Approuver les garde-fous

Codex n’exécute un hook qu’après l’avoir approuvé : au premier lancement qui suit leur installation, il affiche « Hooks need review ». Répondre « Trust all and continue » ; « Continue without trusting » les laisse inactifs. Le kit n’écrit jamais cette approbation à votre place. En mode non interactif (`codex exec`), un hook non approuvé ne s’exécute pas.

## Vérifier dans Codex

`codex doctor` (configuration chargée, `config.toml parse ok`), `/skills` dans Codex, puis `$guide je dois …` dans un repo.

## Particularités

- **`~/.codex/AGENTS.override.md`** : s’il existe, Codex le lit à la place d’`AGENTS.md`, et le contexte du kit est ignoré ; `doctor` le signale.
- **Contexte du repo** : Codex lit nativement l’`AGENTS.md` du repo et de ses dossiers, comme le kit l’organise.
- **Journaux lus par `usage`** : `~/.codex/history.jsonl` (prompts tapés, commandes `$intent` ou `/intent`).
- **Évaluations** : `python3 evals/run.py --cli codex` lance `codex exec` en bac à sable lecture seule ; `/intent` dans un cas devient `$intent`.
- **Profils de capacité** : la clé `models` d’`overrides.json` porte des noms de modèles Gemini et n’est pas appliquée aux agents Codex, qui gardent le modèle de la session.

## Dépannage propre à Codex

- **« Bloc du kit modifié à la main »** : une ligne a été changée entre les marqueurs `ai-kit` ; reporter le changement hors du bloc (ou dans `30_USER.md` ou `overrides.json`), retirer le bloc, puis `update`.
- **« hooks.PreToolUse déjà défini sous une autre forme »** : votre `config.toml` déclare ses hooks autrement que par `[[hooks.PreToolUse]]` ; le kit ne réécrit pas vos réglages, il refuse.
- **Les garde-fous ne bloquent rien** : ils n’ont pas été approuvés ; relancer Codex en interactif et répondre « Trust ».
