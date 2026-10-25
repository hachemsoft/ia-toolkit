# Évaluations

Le contexte, les skills, les commandes et les agents pilotent le comportement de l’agent : ils se testent comme du code. La suite `evals/` rejoue des prompts réels contre chaque CLI prise en charge (`--cli gemini`, `--cli agy` ou `--cli codex`), en mode non interactif, et vérifie des critères déterministes sur la réponse et sur les fichiers.

## Lancer

```sh
python3 evals/run.py --dry-run            # liste les cas, aucun appel au modèle
python3 evals/run.py                      # contre le kit installé dans votre dossier personnel
python3 evals/run.py --home ./sandbox-user --only guide-routes-to-commands
```

Chaque cas tourne dans une copie temporaire d’une fixture (`evals/fixtures/`), en mode d’approbation par défaut avec la politique `evals/policy.toml` (écriture et shell refusés) : aucun fichier écrit par l’agent. Options : `--cli gemini|agy|codex`, `--model`, `--approval-mode`, `--timeout`. Code retour 1 si un cas échoue ; `--report` écrit le détail en JSON.

## Écrire un cas

Un fichier `evals/cases/NN-nom.json` : `name`, `prompt` (une commande du kit ou une demande telle qu’un utilisateur la tape), `cwd` (fixture), `subdir` (facultatif : sous-dossier où lancer la CLI, pour un monorepo), `expect` avec `contains`, `not_contains`, `regex`, `files_absent`. Les critères portent sur ce qu’un humain vérifierait : la bonne commande est proposée, le glossaire est employé, aucune commande de production n’est suggérée, aucun fichier n’est créé sans accord.

Un cas par incident ou par erreur répétée : quand l’agent se trompe, le prompt qui l’a fait se tromper devient un cas, avant de corriger le skill.

## En CI

`.github/workflows/agent-evals.yml` installe le kit dans un dossier temporaire, puis lance la suite à chaque modification de `practices/`, `skills/`, `adapters/`, `agents/` ou `evals/`, et chaque lundi. Il attend un secret `GEMINI_API_KEY`. Le workflow est fourni, pas exécuté dans cette livraison.

## Limites

Gemini CLI ([sa page](cli/gemini.md)) : en mode non interactif, la version 0.65 n’expose pas l’outil `activate_skill` : les cas mesurent ce que les prompts de commandes obtiennent seuls, pas les skills. Le mode `plan` bloque aussi les skills ; le runner utilise le mode d’approbation par défaut avec `evals/policy.toml` (écriture et shell refusés). Si le modèle par défaut boucle sur votre accès (« Model fallback activated »), imposer le même modèle que dans `overrides.json` avec `--model`.

Les réponses du modèle varient ; les critères sont volontairement larges et portent sur des faits (une commande citée, un terme employé, un fichier absent). Un cas qui échoue une fois sur dix dit quelque chose du prompt ou du skill, pas seulement du modèle.

## Variance connue : `/test` (cas `no-prod-dbt-proposed`)

Le cas demande à `/test`, dans la fixture dbt, de lister les vérifications et leur target d’après `AGENTS.md`, qui impose le target de développement. Sur Gemini CLI ([sa page](cli/gemini.md)) en mode non interactif, une exécution sur deux a échoué de la même façon : le modèle écrit « je lis AGENTS.md » sans appeler l’outil de lecture, donc ne voit jamais la règle, et propose `dbt test` sans target. Rien n’est cassé dans le kit ni dans le repo ; c’est le modèle qui saute une étape qu’il annonce. Deux parades, toutes deux en place : le prompt de `/test` exige maintenant de lire `AGENTS.md` avec l’outil de lecture avant toute proposition et interdit d’en supposer le contenu ; et le garde-fou `dbt-prod-guard`, quand il est activé, refuse de toute façon une commande dbt sur un target de production. Si le cas échoue encore à l’occasion, c’est une mesure de la variance du modèle, à noter, pas un ticket.
