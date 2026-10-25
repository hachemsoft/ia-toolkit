---
name: guide
description: "Routeur du kit : quelle commande, quel outil et quel niveau de cérémonie pour la situation décrite. Déclencheurs : quel skill pour, par quoi je commence, comment on fait ici, guide, aide sur le workflow."
---

# guide

Répondre dans la langue de la personne, en quelques lignes : le niveau de cérémonie, la commande ou l’outil, l’artefact produit, un exemple de prompt. Ne citer les noms de skills que si on le demande.

Ne proposer que les commandes listées sous « Commandes » dans le contexte du kit (00_KIT.md) : ce sont celles installées pour ce profil. Les tableaux ci-dessous donnent la carte complète ; quand la commande qui conviendrait n’est pas installée (par exemple `/spec`, `/review`, `/explain` pour un analyste), le dire en une ligne avec la façon de l’activer : `extra_commands` dans `~/.ai-toolkit/overrides.json`, puis `update`.

## Niveau de cérémonie d’abord
| Enjeu | Quoi faire | Commandes |
| --- | --- | --- |
| Retouche (libellé, filtre, couleur) | faire, vérifier soi-même | aucune ; `/test` si le repo a des tests |
| Visuel ou exploratoire | itérer avec l’agent, regarder, recommencer | `/design` pour un prototype jetable |
| Petite fonctionnalité | court cadrage, puis test-first | `/intent` court, `/build`, `/test`, `/ship` |
| Grande ou floue | spec, plan par phases, vérification entre chaque | `/intent`, `/spec`, `/build` par ticket, `/review`, `/ship` |
| Production, irréversible, données sensibles | tout ce qui précède, revue complète | `/review full`, hooks actifs |

## Les étapes et leurs artefacts
- `/intent <idée>` → `intent.md` (Plan). `/map` quand le chantier dépasse une session.
- `/spec` → `spec.md` (Design). `/design` pour la forme d’un module ou un prototype.
- `/build <ticket>` → `plan.md`, puis code et tests, une tranche à la fois (Build).
- `/test` → sortie réelle des vérifications (Test).
- `/review [base] [quick|full]` → constats classés (Deploy). `/ship` → description de MR.
- `/diagnose <symptôme>` → cause prouvée et test de non-régression (Maintain). `/triage` pour les tickets entrants.

## Les outils, à tout moment
`/learn` apprendre un périmètre ou un concept · `/explain` carte d’une zone ou reformulation · `/ask` questionnaire pour un propriétaire métier · `/retro` améliorer l’environnement de l’agent · `/handoff` passation · `/research` sources primaires · `/wizard` étapes humaines · `/audit` santé du code.

## Mise en place d’un repo
Première fois : « Initialise le contexte du projet » (AGENTS.md, GLOSSARY.md, REVIEW.md, règle git des artefacts). Plus tard, quand l’équipe veut que l’agent lise et crée des tickets (`/map`, `/triage`, to-tickets) : `setup-workflow`, qui demande `glab` ou `gh` installé.

## Hors des commandes
Les skills métier Data (SQL, dbt, BigQuery, Python/JS) s’activent seuls quand la tâche s’y prête ; `/build` et `/diagnose` les enchaînent. Pour la carte complète du flux amont, le skill `workflow-guide` est disponible en option.
