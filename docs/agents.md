# Agents

Un skill décrit une procédure. Un agent reçoit une mission délimitée dans un contexte séparé et renvoie ses constats au parent. Le kit utilise les sous-agents natifs de chaque CLI ; il n’impose pas un workflow de délégation ou d’agents parallèles.

| Agent | Profils par défaut | Mission |
| --- | --- | --- |
| `ai-kit-repo-investigator` | tous | Comprendre les flux et dépendances du repo |
| `ai-kit-verifier` | tous | Exécuter les vérifications déclarées par le repo et rapporter, sans corriger |
| `ai-kit-doubter` | tous sauf Data Analyst (avec `/review full`) | Revue adverse en lecture seule : douter de chaque affirmation du changement, chercher preuve ou contre-exemple |
| `ai-kit-code-reviewer` | Général, Développeur Java, Architecte, Développeur Data | Revue de code : contrats, exceptions, compatibilité et régressions |
| `ai-kit-security-reviewer` | Développeur Java, DevOps | Secrets, injections, contrôle d’accès, droits et exposition, dépendances |
| `ai-kit-infra-reviewer` | DevOps | Rayon d’impact d’un changement d’infrastructure ou de pipeline : destructions, droits, versions, retour arrière |
| `ai-kit-architecture-reviewer` | Architecte | Proposition d’architecture ou ADR : options, critères, conséquences, cohérence avec les décisions existantes |
| `ai-kit-sql-reviewer` | Data Analyst, Développeur Data | Grain, jointures, agrégations, dates et NULL |
| `ai-kit-dbt-reviewer` | Data Analyst, Développeur Data | Modèles, incrémental, tests et documentation dbt |

## Utilisation

Après setup ou update, redémarrer la CLI, puis lister les agents avec sa commande (voir sa page : [Gemini CLI](cli/gemini.md), [Antigravity CLI](cli/agy.md)).

Exemples :

```text
@ai-kit-repo-investigator Explique le parcours de cette donnée dans le repo.
@ai-kit-code-reviewer Revois cette modification ; voici le diff et les critères attendus : ...
@ai-kit-sql-reviewer Revois models/marts/ventes.sql et son grain.
@ai-kit-dbt-reviewer Examine les risques de rejeu de ce modèle incrémental.
```

L’agent peut aussi choisir une délégation d’après la description. Ces instructions guident le modèle ; elles ne garantissent pas une invocation. La disponibilité dépend de la version de la CLI et des politiques entreprise. Le kit ne force aucun paramètre d’activation des sous-agents ; `doctor` signale une désactivation.

## Profils de capacité

Un agent ne nomme jamais un modèle : il déclare, au plus, ce qu’il attend (`"capability": "fast"` pour le vérificateur, qui lance des tests et doit répondre vite ; `"deep"` pour l’agent de doute, qui doit raisonner). L’organisation donne la correspondance, si elle le souhaite, dans `~/.ai-toolkit/overrides.json` :

```json
{ "models": { "fast": "gemini-2.5-flash", "deep": "gemini-2.5-pro" } }
```

`update` écrit alors `model:` dans l’en-tête des agents concernés ; la prise en compte de ce champ dépend de la CLI (voir sa page). Sans cette clé, rien n’est écrit et chaque agent hérite du modèle du parent, comme avant. Un agent sans `capability` hérite toujours. Les noms de modèles ne sont jamais dans le kit : ils changent par organisation et par trimestre.

## Outils et limites

Les agents de revue disposent exclusivement de `read_file` et `grep_search`. `ai-kit-verifier` est l’exception : il a aussi `list_directory` et `run_shell_command`, parce que son rôle est de lancer les commandes de vérification déclarées dans `AGENTS.md` (build, tests, lint, `dbt test` sur le target de développement) et de rapporter leur sortie réelle à la fin d’un `/build`. Il ne corrige rien ; le garde-fou `dbt-prod-guard` s’applique aussi à lui. Ils ne peuvent pas modifier les fichiers, exécuter le shell, dbt ou BigQuery, ni appeler les MCP via leur propre liste d’outils. Ils proposent les validations à l’agent principal. Le parent doit fournir le diff ou les résultats pertinents quand ils ne sont pas accessibles.

Les pratiques entreprise et Data sont incluses dans leur prompt lors de l’installation : on ne suppose pas qu’un agent isolé reçoive le contexte complet du parent. Le contexte personnel (`30_USER.md`) n’y est pas copié : il règle la forme des réponses du parent, pas la mission déléguée. Les instructions de projet doivent être lues et les faits manquants signalés. Les skills ne sont pas supposés automatiquement disponibles dans les sous-agents. Quand un skill du socle parle de « sub-agent » ou de « background agent », `00_KIT.md` indique au modèle d’utiliser ces agents `ai-kit-*`, ou de faire le travail lui-même s’ils sont absents.

Le modèle est hérité du parent, sans nom de modèle figé. Chaque agent dispose d’une limite de 12 tours et 5 minutes, sauf le vérificateur (15 tours, 10 minutes) qui doit laisser le temps aux tests de tourner. Une délégation ajoute des appels modèle et peut augmenter latence et consommation : la réserver aux missions qui bénéficient de cette séparation.

L’accès ultérieur à un MCP devra utiliser des outils explicitement autorisés et être validé pour chaque agent. Ne pas élargir à `*` pour résoudre un problème de configuration.

## Organisation

- `agents/catalog.json` : catalogue partagé.
- `agents/internal/<catégorie>/<nom>.json` : rôle et instructions indépendants de toute CLI.
- `agents/defaults.json` : outils et paramètres par défaut, partagés par toutes les CLI.
- `profiles/*.json` : agents sélectionnés par rôle.
- Sortie : un fichier `ai-kit-<nom>.md` par agent, à l’endroit que lit chaque CLI ([matrice](cli/matrice.md)).

L’installateur génère les fichiers, les versionne dans son état, protège les modifications locales et retire les anciennes sorties intactes quand le profil change. La mise à jour depuis la V0.0.2 est prise en charge.

Personnalisation dans `~/.ai-toolkit/overrides.json` : ajouter `extra_agents` et `disabled_agents` comme listes de noms du catalogue (sans préfixe ai-kit). Conserver les autres clés du fichier.

Les agents propres à un repo restent dans ce repo (`.agents/`). Les mêmes agents sont installés dans le plugin Antigravity ; voir [agy](cli/agy.md).

Formats et vérifications propres à chaque CLI : voir sa page. L’invocation effective d’un agent dépend toujours du modèle.
