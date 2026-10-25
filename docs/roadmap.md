# Feuille de route

Le kit vise deux CLI, Gemini CLI et Antigravity CLI (agy), avec une seule source, pour une équipe (profils analyste Data, développeur Data, général), avec le moins de support possible. Les étapes 1 et 2 sont livrées ; les étapes 3 et 4 sont des procédures fournies, que chaque organisation déroule avec ses propres personnes et son propre calendrier.

## 1. Zéro support à l’installation — 0.9.0 — *livrée*

1. `doctor --live` : un appel réel au modèle, et pour chaque échec connu le diagnostic en une phrase et la commande qui le règle : clé AI Studio épuisée, type d’authentification qui ignore les variables Vertex, API Vertex non activée sur le projet, compte Code Assist sans projet, modèle par défaut indisponible qui boucle, droits IAM, quota.
2. `setup` et `update` ne disent « installation terminée » qu’après un `doctor --live` vert, ou expliquent pourquoi il ne l’est pas.
3. Noyau analyste réduit à sept commandes : `/guide`, `/intent`, `/build`, `/test`, `/ship`, `/diagnose`, `/learn`. `/spec`, `/review`, `/explain`, `/retro`, `/ask` passent en option activable d’une ligne pour les analystes ; le profil développeur garde tout.
4. Page `docs/ca-coince.md` : un symptôme, une cause, une commande. Alimentée uniquement par de vrais tickets.
5. Règle d’équipe écrite dans `docs/contributing.md` : tout ticket de support devient un contrôle `doctor`, une ligne de « Ça coince ? » ou un cas d’évaluation. Jamais une explication orale répétée.

## 2. Adaptateur agy — 0.10.0 — *livrée, voir docs/agy.md*

1. Skills de commande générés depuis le manifeste, installés dans les deux CLI.
2. Plugin agy sous `~/.gemini/config/plugins/ai-kit/` : `plugin.json`, `skills/`, `rules/AGENTS.md` avec les quatre couches, `hooks.json`, `mcp_config.json`. Fichiers gérés par empreinte, `agy plugin validate` dans `doctor`.
3. Scripts de garde-fous bilingues (`tool_input` Gemini, `toolCall.args` agy).
4. `--target gemini|agy|both`, `doctor` et `usage` étendus aux journaux agy, évaluations exécutables avec `agy -p`.

## 3. Authentification générique — 0.11.0 — *livrée*

1. Le kit ne suppose aucun mode d’authentification ni aucun modèle. Trois modes documentés dans `docs/customization.md` : connexion Google (Gemini Code Assist, avec `code_assist.project` pour les licences Standard et Enterprise), Vertex AI (`vertex`), clé API (rien à configurer dans le kit). Modèle imposé seulement si `overrides.json` déclare `model`.
2. Les permissions agy restent à chaque personne : agy les demande, la personne décide, le kit n’y touche jamais.
3. La procédure d’élagage devient la revue d’usage, documentée dans `docs/usage-review.md` : pourquoi, ce qu’elle mesure, ce qu’elle ne fait jamais.

## 4. Pilote — *procédure fournie : docs/pilote.md*

Un petit groupe, les deux CLI installées, des repos réels, une à deux semaines. Retours uniquement par `doctor`, `usage` et les tickets ; les quatre cas d’évaluation rejoués sur chaque CLI ; première revue d’usage si le seuil de données est atteint. Qui participe et quand est un choix de l’organisation.

## 5. Passage à agy — 1.0.0 — *parties code et doc livrées*

1. `--target auto` détecte les CLI présentes au `setup` ; `--target both` force les deux.
2. Guide d’une page `docs/guide-bascule.md` : ce qui ne change pas, ce qui change, la commande à taper quand ça coince.
3. Distribution : dépôt git (`git clone`, puis `git pull` et `update`), version par tag, ZIP du dépôt pour qui n’a pas git, les deux adaptateurs maintenus tant que Gemini CLI est utilisé.
4. Reste : les retours du pilote (playbooks complétés sur de vrais tickets, `perimeter-brief` éprouvé sur un vrai périmètre) et le passage lui-même.

## En continu

- Revue d’usage avec `python3 -m installer usage` quand l’équipe le décide ; procédure dans `docs/usage-review.md`.
- Quand l’agent se trompe deux fois : une ligne d’`AGENTS.md`, un cas d’évaluation ou une ligne de table d’excuses, pas un prompt de plus.
- Mise à jour des skills amont par recopie, renommages rejoués, tests et évaluations relancés.

## Choix propres à chaque organisation

Le kit ne les tranche pas et fonctionne sans eux ; ils se déclarent dans `~/.ai-toolkit/overrides.json` ou se décident en équipe.

- Mode d’authentification Gemini et, si besoin, projet Google Cloud (`code_assist` ou `vertex`).
- Modèle à imposer (`model`) seulement si le modèle par défaut boucle sur votre accès ; `doctor --live` le dit.
- Règles de permissions agy : par personne, validées quand agy les demande.
- Gestionnaire de tickets, déclaré par repo avec `setup-workflow`.
- Participants et durée du pilote ; cadence des revues d’usage.
