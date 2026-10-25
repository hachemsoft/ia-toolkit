# Référence des skills

Liste complète du catalogue (`skills/catalog.json`). Les utilisateurs n’ont pas à connaître ces noms : ils passent par les commandes. Cette page sert à qui veut voir ce qu’il y a dessous ou étendre le kit.

Catégories : `workflow` (une étape du SDLC), `tool` (utilitaire hors flux), `domain` (playbook Data), `reference` (vocabulaire consulté par les autres skills), `setup` (mise en place d’un repo). Tiers : `core` installé dans tous les profils (vérifié par un test), `profile` selon le profil, `optional` via `extra_skills` ou `extra_commands`.

| Skill | Catégorie | Tier | Commandes | Description |
| --- | --- | --- | --- | --- |
| `grilling` | workflow | core | — | Challenger un plan, une décision ou une idée par rounds de questions avant de la mettre en œuvre. |
| `codebase-design` | reference | optional | `/design` | Vocabulaire des modules profonds : interface, couture, profondeur ; conception d’interface en plusieurs variantes. |
| `prototype` | workflow | optional | `/design` | Prototype jetable pour trancher une question de conception, logique ou interface. |
| `domain-modeling` | reference | core | `/spec` | Glossaire du projet (GLOSSARY.md) et décisions d’architecture (ADR). |
| `tdd` | workflow | core | `/test` | Développement test-first : rouge, vert, refactor ; tests d’intégration privilégiés. |
| `diagnosing-bugs` | workflow | core | `/diagnose` | Boucle de diagnostic pour bugs difficiles et régressions de performance : reproduire, réduire, hypothèse, instrumenter, corriger. |
| `writing-for-agents` | reference | core | — | Rédiger des documents destinés aux agents : skills, AGENTS.md, docs de repo. |
| `research` | tool | optional | `/research` | Recherche sur sources primaires, consignée dans un fichier Markdown du repo, déléguée à un agent en arrière-plan. |
| `mr` | workflow | core | `/ship` | Rédiger la description d’une merge request : résumé visuel, preuves, risque de fusion. |
| `guide` | tool | core | `/guide` | Quelle commande, quel outil et quel niveau de cérémonie pour la situation : routeur du kit. |
| `grill-me` | workflow | optional | — | Entretien serré pour affûter un plan, sans dépôt ni trace écrite. |
| `grill-with-docs` | workflow | core | `/intent` | Entretien serré qui alimente GLOSSARY.md et les ADR au fil des réponses ; point d’entrée du flux principal. |
| `to-questionnaire` | tool | optional | `/ask` | Transformer une décision qu’on ne peut pas trancher seul en questionnaire pour quelqu’un d’autre. |
| `to-spec` | workflow | profile | `/spec` | Transformer la conversation en spécification publiée sur le gestionnaire de tickets. |
| `to-tickets` | workflow | profile | — | Découper un plan ou une spec en tickets traçantes avec leurs dépendances bloquantes. |
| `wayfinder` | workflow | optional | `/map` | Cartographier un chantier trop grand pour une session en tickets de décision, résolus un par un. |
| `implement` | workflow | core | `/build` | Implémenter un ticket ou une spec, en TDD, puis revue. |
| `implement-spec` | workflow | optional | — | Implémenter toute une spec : tickets lus comme graphe, sous-agents en parallèle, branche d’intégration. |
| `code-review` | workflow | core | `/review` | Revue d’un diff depuis un point fixe sur deux axes : standards du repo et conformité à la spec. |
| `triage` | workflow | optional | `/triage` | Faire avancer les tickets entrants dans une machine à états de triage jusqu’à être prêts pour un agent. |
| `retro` | tool | profile | `/retro` | Rétrospective d’une session de travail : améliorer l’environnement de l’agent, pas le code. |
| `handoff` | tool | optional | `/handoff` | Compacter la conversation en document de passation pour un autre agent ou une autre session. |
| `wait-what` | tool | profile | `/explain` | Reformuler le dernier message qui n’a pas été compris, avec le vocabulaire du glossaire. |
| `zoom-out` | tool | profile | `/explain` | Prendre de la hauteur : contexte élargi et vue d’ensemble. |
| `teach` | tool | core | `/learn` | Apprendre un périmètre ou un concept sur plusieurs sessions : leçons, quiz et fiches ; matériel partagé dans `docs/learn/<sujet>/` du repo, progression personnelle dans `~/.ai-toolkit/learning/`. |
| `improve-codebase-architecture` | tool | optional | `/audit` | Repérer les modules à approfondir, rapport HTML, puis entretien sur ceux retenus. |
| `wizard` | tool | optional | `/wizard` | Générer un assistant bash interactif pour les étapes que seul un humain peut faire. |
| `write-a-skill` | tool | optional | — | Créer un skill : structure, divulgation progressive, ressources. |
| `writing-great-skills` | reference | optional | — | Référence pour écrire et relire des skills prévisibles. |
| `setup-workflow` | setup | core | — | Configurer un repo pour le flux : gestionnaire de tickets (GitHub, GitLab, local), labels de triage, emplacement du glossaire et des ADR. À lancer une fois par repo. |
| `workflow-guide` | tool | optional | — | Quel skill ou quel flux pour la situation présente : routeur sur l’ensemble des skills. |
| `init-project-context` | setup | core | — | Poser le contexte agent d’un repo, avec confirmation à chaque fichier : AGENTS.md court, GLOSSARY.md pré-rempli, REVIEW.md, règle git des artefacts ; ne copie pas les gabarits, ne crée pas d’ADR vide. |
| `python-js-change` | domain | profile | — | Développer ou revoir une fonctionnalité Python ou JavaScript dans un repo existant. |
| `java-change` | domain | profile | — | Développer ou revoir une fonctionnalité Java dans un repo existant (Maven ou Gradle, Spring ou autre). |
| `infra-change` | domain | profile | — | Préparer ou revoir un changement d’infrastructure ou de livraison : Terraform, Kubernetes, Helm, pipeline CI/CD, Dockerfile, configuration cloud. |
| `architecture-decision` | domain | profile | — | Instruire et documenter une décision d’architecture (ADR) : options, critères, conséquences, réversibilité. |
| `sql-review` | domain | profile | — | Revoir du SQL BigQuery ou dbt et investiguer des agrégations, doublons ou résultats métier suspects. |
| `dbt-model-change` | domain | profile | — | Créer, modifier, tester ou documenter un modèle dbt sur BigQuery. |
| `bigquery-query-review` | domain | profile | — | Optimiser une requête BigQuery lente ou coûteuse et vérifier scans, partitions, jointures et plan. |
| `kpi-definition` | domain | profile | — | Définir ou redéfinir un KPI avant de le calculer : grain, population, période, exclusions, source de vérité, propriétaire. |
| `incremental-replay` | domain | profile | — | Rejouer ou corriger un modèle incrémental : clé unique, données tardives, fenêtre de retraitement, idempotence. |
| `bigquery-cost-review` | domain | profile | — | Mesurer et réduire le coût d’une requête ou d’un modèle BigQuery : octets, slots, fréquence, budget avant exécution. |
| `perimeter-brief` | domain | profile | — | Fiche HTML d’un périmètre Data, quiz et termes candidats au glossaire, première leçon de `/learn`. |
| `clarify-request` | remplacé | | | → `grilling` |
| `debug-systematically` | remplacé | | | → `diagnosing-bugs` |
| `verify-change` | remplacé | | | → `tdd`, `mr` |

## Origine

Les skills `origin: upstream` sont repris tels quels d’un dépôt amont sous licence MIT (`skills/LICENSE-UPSTREAM-MIT`), en anglais ; trois adaptations : `pr` devient `mr`, et les deux skills amont dont le nom portait celui de leur auteur deviennent `setup-workflow` et `workflow-guide`. Les skills `origin: contrib` (sous `skills/contrib/`) sont proposés par des personnes de l’organisation qui en restent propriétaires, toujours optionnels. Les skills `origin: internal` sont écrits pour le kit, en français. Voir [workflow](workflow.md) et [outils](tools.md) pour l’usage.
