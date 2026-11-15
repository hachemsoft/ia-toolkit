# Spec: deuxième lot d'agents optionnels — version C, 4.14.0 (from intent.md 2026-11-14)

Status: accepted (2026-11-15) · Reviewed by: Hachem LATRACH · Date: 2026-11-15 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full (hérité de intent.md). Ici, le risque est faible : quatre agents en lecture seule, optionnels, appelés seulement quand ils sont installés ; aucun script, aucune écriture. Numéro : 4.14.0 (la page `review.html` passe en 4.15.0, décision du 2026-11-15).

## Objective
Offrir quatre relecteurs ciblés à ceux qui les installent, chacun branché à son moment du cycle : les erreurs avalées dans `/review`, les exemples existants avant d'écrire du code, les règles métier avant d'en changer une, et la lecture d'un nouvel arrivant avant de livrer une spec ou une MR.

## Scope and non-goals
- In (4.14.0) :
  - quatre agents optionnels (`aikit-default: "false"`) : **silent-failure-hunter**, **pattern-scout**, **rule-miner**, **fresh-eyes** ;
  - leur appel **d'office aux niveaux standard et full quand ils sont installés**, jamais en quick ;
  - des **ensembles recommandés par rôle** dans la doc, activés par une Team (`[defaults]`) ou une personne (`extra_agents`) ;
  - doc, CHANGELOG, versions, snapshot, tests ; un cas d'eval par agent, écrit, non lancé.
- Out :
  - profils dans le kit (ADR 0018 : le kit n'a pas de presets ; une Team ou une personne choisit) ;
  - tout agent installé par défaut (passage par défaut selon la revue d'usage) ;
  - `/build` modifié directement (3 999 / 4 000 caractères) : l'appel passe par les skills et playbooks qu'il active ;
  - la page `review.html` (4.15.0).

## Requirements
Each requirement has a verifiable acceptance criterion.

**R1 — silent-failure-hunter.** Relecteur en lecture seule, cold review. Il cherche dans le diff les échecs silencieux : `catch`/`except` vides ou qui avalent l'erreur, journalisation sans propagation là où l'appelant attendait une erreur, valeur par défaut ou solution de repli qui masque une panne (retourner `[]`, `None`, `0`, `{}`), `except Exception: pass`, promesse sans gestion d'erreur, code de retour ignoré, `COALESCE`/`IFNULL` ou filtre SQL qui fait disparaître des lignes en erreur. Chaque constat : gravité (Important si une panne devient invisible pour l'utilisateur ou les données, sinon Minor), fichier:ligne, l'entrée qui déclenche l'échec silencieux, ce que l'appelant verra, la correction. Il ne commente pas le style.
— Acceptance : test de contenu.

**R2 — Son appel.** Skill `code-review` : quand `ai-kit-silent-failure-hunter` est installé et que la revue n'est pas en mode quick, il reçoit le même brief à froid que les autres relecteurs, en même temps quand la CLI le permet ; ses constats sont fusionnés dans la passe Bugs (avec son nom). Cela vaut pour `/review` et pour la relecture du changement entier que fait `/build`.
— Acceptance : test de contenu sur `code-review`.

**R3 — pattern-scout.** Agent en lecture seule. Avant qu'on écrive du code, à partir de ce qu'il faut faire (la tâche, les symboles ou fichiers visés), il trouve **deux ou trois endroits du repo qui font déjà la même chose** et rend, pour chacun : fichier:ligne, ce qu'il montre (nommage, structure, gestion d'erreur, tests associés, bibliothèque utilisée), puis la convention commune en trois lignes au plus, et ce qui diverge entre les exemples. Rien de comparable : il le dit, sans inventer de convention.
— Acceptance : test de contenu.

**R4 — Son appel.** Playbook `code-change`, section « In the kit commands », `/build` : aux niveaux standard et full, quand `ai-kit-pattern-scout` est installé, le lancer avant d'écrire les tests d'acceptation et le code, et suivre la convention qu'il rend sauf raison écrite.
— Acceptance : test de contenu ; version du playbook montée.

**R5 — rule-miner.** Agent en lecture seule. Avant de changer une logique métier ou un KPI, il extrait les règles **déjà en place** dans le code, le SQL ou les modèles dbt touchés, en **Given / When / Then**, chacune avec fichier:ligne, et marque celles qui se contredisent entre deux endroits ou qui ne sont écrites nulle part ailleurs que dans le code. Il n'invente aucune règle : ce qu'il ne trouve pas, il le dit.
— Acceptance : test de contenu.

**R6 — Son appel.** `/spec` (une phrase, sous 4 000 caractères) et playbook `kpi-definition` : quand la change touche une règle métier ou un KPI, aux niveaux standard et full, quand `ai-kit-rule-miner` est installé, le lancer avant d'écrire les exigences ; les règles qu'il rend vont dans la spec, et une règle existante que la change modifie y est nommée comme telle.
— Acceptance : tests de contenu sur `commands/spec.md` et `kpi-definition`.

**R7 — fresh-eyes.** Agent en lecture seule, qui lit un document **comme un nouvel arrivant** : il ne reçoit que le document (spec, corps de MR, README) et le repo, jamais la conversation. Il rend la liste de ce qu'il ne comprend pas : terme non défini (ou absent de `GLOSSARY.md`), étape sautée, référence à un contexte qu'il n'a pas, phrase ambiguë, chacun avec la ligne citée et la question qu'il poserait. Il ne réécrit rien.
— Acceptance : test de contenu.

**R8 — Son appel.** `/spec` (après avoir écrit `spec.md`) et `/ship` (après avoir écrit le corps de MR) : aux niveaux standard et full, quand `ai-kit-fresh-eyes` est installé, lui donner le document ; montrer ses questions à la personne avec le document, sans corriger d'office.
— Acceptance : tests de contenu sur `commands/spec.md` et `commands/ship.md`.

**R9 — Format commun.** Les quatre : lecture seule (outils par défaut), cold review (règle commune), une ligne « Not for: … (agent) » dans la description, une section de limites. Leur absence n'empêche rien : la commande ou le playbook n'appelle que ce qui est installé et ne dit rien de plus.
— Acceptance : test de contenu sur les quatre.

**R10 — Ensembles recommandés.** `docs/commands.md` (table des agents) et une ligne dans `docs/repositories.md` (défauts d'une Team) : développement → silent-failure-hunter, pattern-scout ; data → rule-miner ; tous → fresh-eyes ; activés par `extra_agents` (personne) ou les défauts d'une Team.
— Acceptance : test de contenu sur la doc ; test d'installation : chacun s'installe avec `extra_agents` et n'est pas installé par défaut.

**R11 — Livraison.** VERSION 4.14.0, CHANGELOG, versions (agents 1.0.0, `code-review`, `code-change`, `kpi-definition` montés), snapshot, table de sélection ; quatre cas d'eval écrits, non lancés.
— Acceptance : suite complète verte, `ruff`, `versions.py`, `check_skills.py`.

## Contracts
| Object | Shape (fields, or one row per … for data) | Key | Sources | Freshness | Rules (compatibility, dates, exclusions, NULL) |
| --- | --- | --- | --- | --- | --- |
| Constat de silent-failure-hunter | gravité · fichier:ligne · entrée déclenchante · ce que voit l'appelant · correction | fichier:ligne | diff brut, fichiers | à chaque `/review` non quick | fusionné dans la passe Bugs |
| Sortie de pattern-scout | 2-3 exemples (fichier:ligne, ce qu'il montre) · convention (≤ 3 lignes) · divergences | — | repo | avant le code | rien de comparable : dit, pas inventé |
| Sortie de rule-miner | règles Given/When/Then · fichier:ligne · contradictions · règles écrites seulement dans le code | une règle | code, SQL, dbt | avant les exigences | aucune règle inventée |
| Sortie de fresh-eyes | ligne citée · ce qui manque · question | ligne | le document seul + le repo | après écriture | aucune réécriture |

## Constraints and policies applied
- **ADR 0018** (le kit n'a pas de presets) : disponibilité par `extra_agents` et défauts de Team, ensembles recommandés documentés seulement.
- **Agents en lecture seule, cold review, une responsabilité, aucun agent qui en appelle un autre** (intent, 4.11.0).
- **Budgets des commandes** : `/build` non touché (3 999) ; `/spec` et `/ship` restent sous 4 000.
- **Ne jamais inventer une règle métier** (pratiques) : rule-miner extrait, ne déduit pas ; fresh-eyes questionne, ne corrige pas.
- **Pas de nom de kit ou produit tiers dans le repo** ; idées reprises, pas de texte copié.
- **Evals écrites, non lancées** sans demande.

## Areas of concern
- **Coût** : avec les quatre installés, un `/review` non quick lance un relecteur de plus, et `/spec` jusqu'à deux (rule-miner, fresh-eyes). Accepté : optionnels, choisis par la personne ou la Team. — à mesurer à la revue d'usage.
- **Recouvrement** : silent-failure-hunter recouvre en partie la passe Bugs de code-reviewer. Il est fusionné dans la même passe, doublons fusionnés par la règle existante.
- **pattern-scout et les mauvais exemples** : il peut proposer comme convention un motif que l'équipe veut abandonner. La convention reste une proposition ; `AGENTS.md` gagne.
- **fresh-eyes et les langues** : un document en français relu par un agent qui répond en anglais ; il répond dans la langue du document.
- **Correction de la 4.13.0** : la spec B disait architecture-reviewer et infra-reviewer « liés aux profils Architect et DevOps » ; ce sont des presets de test, pas des profils du kit. La doc dit seulement « optional » : rien à corriger côté utilisateur.

## Open questions
- Assumption: `code-change` est le bon point d'appel de pattern-scout (seulement pour qui a installé ce playbook) ; un appel depuis `tdd` couvrirait tout le monde mais touche un skill amont. — à revoir après usage.
- Découpage en tâches : `/build` ou le skill `to-tickets`.
