# Workflow : six étapes, une commande par étape

Le kit suit le cycle du [« AI-native SDLC playbook »](https://claude.com/fr/resources/articles/the-ai-native-sdlc-playbook) d’Anthropic : chaque étape se termine par un artefact versionné que l’étape suivante lit. Les commandes sont des verbes anglais, tapés dans la CLI ; les skills qui les réalisent restent sous le capot. `/guide` explique par quoi commencer.

## La cérémonie suit les enjeux

| Enjeu | Quoi faire | Commandes |
| --- | --- | --- |
| Retouche (libellé, filtre, couleur) | faire, vérifier soi-même | aucune ; `/test` si le repo a des tests |
| Visuel ou exploratoire | itérer avec l’agent, regarder, recommencer | `/design` pour un prototype jetable |
| Petite fonctionnalité | court cadrage, puis test-first | `/intent` court, `/build`, `/test`, `/ship` |
| Grande ou floue | spec, plan par phases, vérification entre chaque | `/intent`, `/spec`, `/build` par ticket, `/review`, `/ship` |
| Production, irréversible, données sensibles | tout ce qui précède, revue complète | `/review full`, garde-fous actifs |

Chaque commande annonce en une ligne le niveau qu’elle a retenu. `/review` accepte `quick` ou `full` en argument.

## Les étapes

Les commandes installées dépendent du profil : voir la [table des profils](getting-started.md#3-travailler--une-commande-par-étape). Une commande absente s’ajoute d’une ligne, `extra_commands` dans `~/.ai-toolkit/overrides.json`, puis `update`.

| Étape | Commande | Artefact | Ce que fait la commande |
| --- | --- | --- | --- |
| Plan | `/intent <idée, ticket, incident>` | `intent.md` | entretien par rounds jusqu’à une compréhension partagée ; problème, résultat attendu, utilisateurs et systèmes touchés, contraintes, questions ouvertes ; glossaire et ADR mis à jour |
| Plan | `/map <chantier>` (développeurs) | tickets de décision | cartographier un chantier trop grand pour une session, décisions d’abord, puis `/spec` |
| Design | `/spec` | `spec.md` | à partir de l’intent accepté, sans nouvel entretien : objectif, périmètre, exigences avec critères d’acceptation, contrats de données (grain, clés, sources, fraîcheur), règles appliquées pendant la rédaction, points de vigilance ; un fichier, jamais un ticket (le découpage en tickets est `to-tickets`, sur demande) |
| Build | `/design <question>` (développeurs) | esquisse d’interface ou prototype | plusieurs formes d’un module comparées, ou prototype jetable pour trancher |
| Build | `/build <ticket ou spec>` | `plan.md`, puis diff et tests | plan en mode plan (fichiers, ordre, risques, preuves), accepté avant tout code ; implémentation une tranche à la fois, test rouge d’abord ; vérification finale par l’agent vérificateur quand il est installé |
| Test | `/test [périmètre]` | sortie réelle des vérifications | teste ce qui a changé et ce qui en dépend, quelle que soit l’équipe : fichiers modifiés par rapport à la branche de base, commande « Changed » de chaque pile dans le bloc « Verifying your work » d’`AGENTS.md`, suite complète si un fichier partagé a changé ; même règle avec les outils du repo si le bloc manque, trouvés d’abord dans la CI ; si aucune commande ne se déduit, il le dit, demande les commandes et propose de les écrire dans `AGENTS.md` ; colle la sortie ; corrige le code, jamais le test |
| Deploy | `/review [base] [quick\|full]` | constats classés | passes bugs, sécurité, données, conformité à `spec.md` (et `plan.md` quand il est présent localement), selon `REVIEW.md` du repo ou le gabarit du kit ; les axes du skill amont sont remplacés par ces passes ; en mode `full`, passe de doute sur chaque affirmation |
| Deploy | `/ship` | description de MR | résumé visuel, preuves avant/après, porte à sens unique ou double ; ne pousse rien |
| Maintain | `/diagnose <symptôme>` | cause prouvée, test de non-régression | signal rouge/vert avant toute correction ; pour la donnée, une requête d’assertion ou un test dbt ; le constat peut redevenir un `intent.md` |
| Maintain | `/triage` (développeurs) | tickets prêts pour un agent | machine à états de triage sur les tickets entrants |

Les gabarits d’`intent.md`, `spec.md`, `plan.md`, `REVIEW.md` et `AGENTS.md` sont installés avec le skill `init-project-context`. Convention d’emplacement : un dossier par changement, `docs/sdlc/<AAAA-MM-JJ>-<slug>/`, qui regroupe les trois artefacts. `REVIEW.md` reste à la racine. Un repo peut documenter une autre convention dans `AGENTS.md`.

**Ce qui est versionné.** `spec.md` et `REVIEW.md` sont commités : la spec est le contrat que le relecteur lit dans la MR, `REVIEW.md` ses axes. `intent.md` et `plan.md` sont des notes de travail locales, ignorées par git (`init-project-context` propose les lignes de `.gitignore`) : on n’a pas envie de relire dans l’historique un entretien ou un plan de travail, et ils changent à chaque itération. Une équipe qui préfère tout versionner le dit dans `AGENTS.md`, et `/review` compare alors aussi au `plan.md`. Dans tous les cas, l’agent ne commite jamais sans accord.

**Langue.** Les titres de sections des artefacts restent en anglais, comme dans les gabarits : ils sont stables et cherchables. Le contenu est dans la langue de l’équipe ; les réponses de l’agent sont dans la langue de la personne. Les descriptions de commandes affichées par `/help` sont en anglais.

## Playbooks métier

Skills métier en français, activés par le modèle quand la tâche s’y prête et enchaînés par les commandes :

| Playbook | Enchaîné par | Rôle |
| --- | --- | --- |
| `kpi-definition` | `/intent` | grain, population, période, exclusions, source de vérité, propriétaire, avant toute requête |
| `sql-review` | `/diagnose` | grain, cardinalités des jointures, NULL, dates, résultats suspects |
| `dbt-model-change` | `/build` | test-first avec `dbt test` sur le target de développement |
| `incremental-replay` | `/build`, `/diagnose` | clé unique, données tardives, fenêtre de retraitement, idempotence du rejeu |
| `bigquery-query-review` | `/build`, `/diagnose` | sémantique conservée, partitions, plan d’exécution |
| `bigquery-cost-review` | `/build`, `/diagnose` | octets, slots, fréquence, coût mensuel, budget avant exécution |
| `perimeter-brief` | `/learn` | fiche HTML d’un périmètre, quiz, termes candidats au glossaire |
| `python-js-change` | `/build` (Développeur Data) | conventions du repo, TDD, interface avant implémentation |
| `java-change` | `/build` (Développeur Java) | conventions du repo et du build Maven ou Gradle, JUnit, contrats publics |
| `infra-change` | `/build`, `/diagnose` (DevOps) | rayon d’impact, preuve en lecture seule (plan, diff), jamais d’apply ni de déploiement, retour arrière |
| `architecture-decision` | `/spec` (Architecte) | options comparées, critères, conséquences, réversibilité, ADR |

Les playbooks Data sont dans les deux profils Data ; `python-js-change`, `java-change`, `infra-change` et `architecture-decision` sont chacun dans le profil indiqué. Un playbook d’un autre profil s’ajoute par `extra_skills` dans `overrides.json`. Les tables d’excuses, les déclencheurs des descriptions et les sections « Interdits » sont ce qui fait qu’un playbook s’active au bon moment.

Chaque playbook se termine par une table « Excuses entendues et réponses » : les raisons qu’un agent invoque pour sauter une étape, et ce qu’on lui répond. Quand l’agent trouve une nouvelle excuse, elle entre dans la table.

## Revue adverse

`/review full` ajoute une passe de doute : l’agent `ai-kit-doubter`, dans un contexte frais et en lecture seule, extrait les affirmations dont le changement dépend, cherche pour chacune une preuve ou un contre-exemple, et classe prouvée, réfutée, non prouvée. Une affirmation sans preuve lisible est rapportée comme Important.

## Mise en place d’un repo

1. « Initialise le contexte du projet » : `AGENTS.md` d’une page (Commands, Verifying your work, Conventions, Architecture, Things the agent gets wrong), `GLOSSARY.md` pré-rempli avec le vocabulaire du repo, `REVIEW.md`, et les lignes de `.gitignore` pour les notes locales. Pas d’ADR vide, pas de copie des gabarits.
2. Plus tard, seulement si l’équipe veut que l’agent lise et crée des tickets (`/map`, `/triage`, `to-tickets`) : `setup-workflow`, qui demande `glab` (GitLab) ou `gh` (GitHub) installé et connecté, ou choisit le mode markdown local. Il écrit `docs/agents/issue-tracker.md` et un bloc dans `AGENTS.md`.

Un repo peut surcharger une commande, sous la forme que lit la CLI ([matrice](cli/matrice.md)).

## Sous le capot

Les commandes sont écrites une fois dans `commands/<nom>.md` ([format pivot](format.md)) ; chaque adaptateur en dérive la forme de sa CLI ([matrice](cli/matrice.md)). Leur prompt active un ou plusieurs skills. Leur comportement se vérifie avec la suite d’[évaluations](evals.md). La liste des skills, leur catégorie et leur origine sont dans [skills-reference.md](skills-reference.md) ; les outils hors flux dans [tools.md](tools.md).
