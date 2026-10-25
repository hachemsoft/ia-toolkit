# Format pivot des commandes

Une commande du kit est écrite une fois, dans `commands/<nom>.md`, et chaque adaptateur en dérive la forme de sa CLI (tableau ci-dessous et [matrice](cli/matrice.md)). Une CLI de plus est un adaptateur de plus ([ajouter une CLI](cli/matrice.md#ajouter-une-cli)) ; les fichiers sources ne changent pas. Les skills (`SKILL.md`) et les agents (`agents/internal/*.json`) suivent déjà ce principe.

## Le fichier

```markdown
---
name: intent
description: "Plan: capture an idea, ticket or incident as intent.md"
category: workflow
stage: Plan
skills: [grill-with-docs]
artifact: intent.md
order: 10
---

Activate the grill-with-docs skill ...

Input: {{args}}
...
```

| Champ | Obligatoire | Sens |
| --- | --- | --- |
| `name` | oui | identique au nom du fichier ; devient `/<name>` (Gemini, agy) ou `$<name>` (Codex) |
| `description` | oui | une ligne en anglais, affichée par `/help` ; pour une étape, commencer par son nom (`Plan:`, `Build:`) |
| `category` | oui | `workflow` (une étape du cycle, listée sous « Étapes » dans `00_KIT.md`) ou `tool` (listée sous « Outils ») |
| `stage` | pour `workflow` | Plan, Design, Build, Test, Deploy ou Maintain |
| `skills` | oui, liste | les skills que le prompt active ; la commande n’est installée que si tous le sont ; `[]` pour une commande autonome |
| `artifact` | non | ce que la commande produit, pour la documentation |
| `order` | non | position dans les listes (`00_KIT.md`, `/guide`) ; 1000 par défaut |

Le corps est le prompt. `{{args}}` reçoit ce que la personne tape après la commande. Pas de triple guillemet dans le corps. Les règles qui valent pour tous les prompts du kit : nommer le skill activé et dire quoi faire si l’outil d’activation est absent ; annoncer en une ligne le niveau de cérémonie ; répondre dans la langue de la personne ; ne citer un playbook métier que « si installé ».

## Ce que chaque adaptateur en fait

| Cible | Sortie | Détail |
| --- | --- | --- |
| Gemini CLI | `~/.gemini/commands/<name>.toml` | `description` et `prompt`, `{{args}}` conservé |
| Antigravity CLI | `~/.gemini/skills/<name>/SKILL.md` quand aucun skill ne porte déjà ce nom | description préfixée « Kit command /<name> », `{{args}}` remplacé par une phrase, activation réservée à la commande |
| Codex CLI | `~/.codex/skills/<name>/SKILL.md` et `agents/openai.yaml` quand aucun skill ne porte déjà ce nom | même texte que pour agy ; `openai.yaml` réserve l’activation à `$<name>` |

L’en-tête est lu sans dépendance : une clé par ligne, une valeur simple, une chaîne entre guillemets JSON ou une liste `[a, b]`. `python3 -m unittest tests.test_commands tests.test_consistency` vérifie chaque fichier : nom, description, catégorie, skills existants, `{{args}}` présent, TOML généré valide.

## Surcharger dans un repo

Sous la forme que lit la CLI, dans le repo ([matrice](cli/matrice.md)). Le repo l’emporte sur le kit. Voir [ajouter ou remplacer un skill](extending.md).
