---
name: init-project-context
description: "Poser le contexte agent d’un repo : AGENTS.md court, GLOSSARY.md pré-rempli avec le vocabulaire Data, dossier docs/ prêt pour les ADR. Déclencheurs : initialise le contexte du projet, crée le AGENTS.md, pose le glossaire, prépare le repo pour l’agent."
---

# init-project-context

Le kit n’écrit jamais dans un repo. Ce skill le fait, à la demande, avec confirmation avant chaque fichier.

## Avant d’écrire
1. Lire le repo : README, `dbt_project.yml`, `pyproject.toml` ou `package.json`, commandes de test, CI, dossiers principaux. Noter les commandes réelles, pas des commandes supposées.
2. Vérifier ce qui existe déjà : `AGENTS.md`, `GEMINI.md`, `GLOSSARY.md`, `GLOSSARY-MAP.md`, `docs/adr/`. Ne jamais remplacer un fichier existant : proposer un complément.
3. Lire le skill `writing-for-agents` pour la forme d’`AGENTS.md`, et `domain-modeling` avec `GLOSSARY-FORMAT.md` pour le glossaire.

## Fichiers proposés
- Bloc « Verifying your work » : générique, le même pour un repo Data et un repo d’application, déduit automatiquement. Repérer les piles utilisées en lisant, dans cet ordre, la CI d’abord (`.gitlab-ci.yml`, `.github/workflows/`, `Jenkinsfile`), qui lance déjà les vraies commandes ; puis les fichiers de pile (`dbt_project.yml`, `pyproject.toml`, `setup.cfg`, `pytest.ini`, `package.json` et ses scripts, `go.mod`, `pom.xml`, `build.gradle`, `Cargo.toml`) ; puis `Makefile`, `justfile` ou `Taskfile` et le README. Pour chaque pile trouvée, remplir pour chacune la commande sur le périmètre modifié et la commande complète, la branche de base, les fichiers partagés qui imposent la suite complète, le target de développement ; supprimer les lignes des piles absentes. Proposer de lancer chaque commande une fois, avec accord, et n’écrire que celles qui passent ; signaler celles qui échouent. Si aucune pile ni commande de test ne se déduit du repo, ne rien inventer : laisser le bloc avec ses `<…>`, le dire clairement, et demander à la personne d’y écrire elle-même les commandes de test du repo (ou de les donner, pour que l’agent les écrive).
- `AGENTS.md` à partir de `templates/AGENTS.md` : une page, structurée comme le fichier de contexte du playbook SDLC : Commands, Verifying your work, Conventions, Architecture, Things the agent gets wrong, Where the rest lives. Remplacer chaque `<…>` par les faits lus dans le repo ; supprimer les lignes sans fait. Si le repo utilise déjà `GEMINI.md`, le conserver et y ajouter `@AGENTS.md` plutôt que dupliquer.
- `GLOSSARY.md` à partir de `templates/GLOSSARY.md` : termes Data génériques déjà rédigés au format `domain-modeling`. Retirer ceux qui ne s’appliquent pas, ajouter les termes métier rencontrés dans les modèles et la doc, chacun avec ses synonymes à éviter.
- `REVIEW.md` à partir de `templates/REVIEW.md` : les passes de revue que `/review` suit (bugs, sécurité, données, conformité), ce que veut dire Important, le plafond de nits. Adapter la passe Data au périmètre.
- Règle git des artefacts, avec confirmation : ajouter à `.gitignore` les lignes `docs/sdlc/**/intent.md`, `docs/sdlc/**/plan.md` et `docs/sdlc/handoff-*.md` (notes de travail locales) ; `spec.md` et `REVIEW.md` restent versionnés. Si l’équipe préfère tout versionner, l’écrire dans `AGENTS.md` et ne pas toucher `.gitignore`.
- Gabarits d’artefacts `templates/intent.md`, `templates/spec.md`, `templates/plan.md` : ne pas les copier dans le repo ; `/intent`, `/spec` et `/build` les lisent depuis ce skill et écrivent l’artefact rempli au moment voulu. Convention : un dossier par changement, `docs/sdlc/<AAAA-MM-JJ>-<slug>/` contenant `intent.md`, `spec.md`, `plan.md` ; l’historique git du dossier est la piste d’audit. L’écrire dans `AGENTS.md`.
- `docs/adr/` : ne pas créer de fichier vide. Si une décision structurante est déjà visible dans le repo (matérialisation incrémentale, convention de couches, outil imposé), proposer un premier ADR selon `ADR-FORMAT.md` ; sinon dire que le dossier sera créé avec la première décision.

## Déroulé
1. Présenter le plan : fichiers à créer, résumé de chacun.
2. Pour chaque fichier, montrer le contenu complet et attendre la confirmation.
3. Proposer ensuite `setup-workflow` pour déclarer le gestionnaire de tickets (GitLab via `glab`, GitHub ou markdown local) et les labels de triage que `to-spec`, `to-tickets` et `code-review` attendent.
4. Après écriture, tester : demander à l’agent d’accomplir une tâche courante du repo en ne lisant que ces fichiers. Ajouter ce qui a manqué, retirer ce qui n’a pas servi.

## Interdits
Pas d’écriture sans confirmation. Pas de fichier qui répète la structure du code. Pas de terme inventé : chaque entrée du glossaire vient du repo ou de la personne.
