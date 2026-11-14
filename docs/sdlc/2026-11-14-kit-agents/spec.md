# Spec: verifier prouve que le test échoue sans le code — version A, 4.12.0 (from intent.md 2026-11-14)

Status: accepted (2026-11-14) · Reviewed by: Hachem LATRACH · Date: 2026-11-14 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full (hérité de intent.md) : un script du kit remplace temporairement des fichiers dans le working tree de la personne ; une perte de modifications est le risque principal.

## Objective
Qu'un test d'acceptation approuvé dans `/build` prouve réellement quelque chose : verifier montre qu'il échoue quand le code du changement est retiré, sépare les échecs apportés par le changement de ceux déjà présents sur la base, et signale toute modification d'un test existant.

## Scope and non-goals
- In (version A, 4.12.0) :
  - nouveau script `runtime/prove_test.py`, installé dans `~/.ai-kit/bin/` comme `weakened_tests.py` ;
  - agent `verifier` : preuve, nouveaux échecs, tests existants modifiés ;
  - `/build` : preuve systématique du test d'acceptation aux niveaux standard et full, arrêt si le test passe sans le code ;
  - `/ship` et skill `mr` : le résultat de la preuve dans la section Evidence ;
  - tests de warehouse (dbt) sur la cible dev, avec accord ;
  - doc, CHANGELOG, versions, snapshot, tests.
- Out :
  - nouveaux agents et branchements de playbooks (version B, spec à part, 4.13.0) ; deuxième lot (version C, 4.15.0) ;
  - comparaison test par test des sorties d'outils (décidé : par commande) ;
  - toute eval lancée (cas écrits, non lancés) ;
  - tout outil à installer.

## Requirements
Each requirement has a verifiable acceptance criterion.

**R1 — Le script, ses modes.** `prove_test.py` (bibliothèque standard seulement, aucune connexion, aucun modèle) :
- `prove --test <chemin> [--test …] [--keep <chemin> …] [--base REF] [--timeout S] -- <commande>` : remplace chaque **fichier de code** du changement par sa version de base (fichier modifié : contenu de base ; fichier ajouté : retiré ; fichier supprimé : remis), garde les tests à leur nouvelle version, lance la commande, restaure, rend le verdict ;
- `base-run [--base REF] -- <commande>` : remet **tous** les fichiers du changement (tests compris) à la base, lance la commande, restaure (pour R6) ;
- `recover` : restaure une sauvegarde restée après une interruption ;
- `modified-tests [--base REF]` : liste les fichiers de test qui existaient sur la base et que le changement modifie ou supprime.
Portée : celle de la relecture (commits depuis la merge-base, indexé, non indexé, nouveaux fichiers non ignorés). Sortie JSON sur stdout ; code 0 quand la sortie est valide, 2 quand le repo ne peut être lu ou qu'un refus de sécurité s'applique.
— Acceptance : tests unitaires sur un repo git construit dans un dossier temporaire, un par mode.

**R2 — Qu'est-ce qu'un fichier de test.** Est un test : un chemin passé en `--test` ; un fichier sous un dossier `test`, `tests`, `__tests__`, `spec` (règle de `weakened_tests.py`) ; un nom `test_*.py`, `*_test.py`, `*_test.go`, `*.test.{js,ts,jsx,tsx}`, `*.spec.{js,ts,jsx,tsx}`, `*Test.java`, `*Tests.java`, `*Spec.scala`, `*Test.php`. Tout le reste du changement est du code, sauf `--keep`. Un `--test` qui n'est pas dans le changement est refusé.
— Acceptance : test unitaire sur un changement mêlant ces formes.

**R3 — Verdict.** `prove` rend `proven` si la commande sort avec un code non nul sans le code (la sortie littérale, tronquée, est jointe pour que la personne voie si c'est une assertion ou une erreur d'import), `not_proven` si elle sort avec 0, `not_possible` avec la raison (un `--test` hors du changement, aucun fichier de code dans le changement, commande introuvable, un lien symbolique ou un sous-module dans le changement, une commande d'entrepôt sans `--target`), `timeout`.
— Acceptance : tests unitaires des quatre verdicts.

**R4 — Sécurité du working tree.** Avant tout remplacement : copie octet pour octet de chaque fichier touché dans `<repo>/.ai-kit-proof/` (dossier qui s'ignore lui-même par un `.gitignore` contenant `*`), avec un manifeste (chemin, empreinte SHA-256, existait ou non). La restauration a lieu dans tous les cas : fin normale, erreur, `KeyboardInterrupt`, `SIGTERM` (et `CTRL_BREAK` sous Windows quand disponible) ; après restauration, chaque empreinte est revérifiée, puis le dossier est supprimé. Une sauvegarde trouvée au lancement (interruption brutale) : le script refuse tout autre mode et indique `recover`. Jamais d'écriture dans `.git`, l'index ou un fichier hors du changement ; jamais de `git stash`, `checkout` ou `reset` ; la commande est lancée sans shell (liste d'arguments).
— Acceptance : tests unitaires — restauration après une commande qui échoue, qui lève une erreur, qui est interrompue ; empreintes identiques avant/après ; sauvegarde restée → refus puis `recover` ; `git status --porcelain` identique avant et après ; aucun fichier sous `.git` modifié.

**R5 — verifier.** `verifier.md` :
- dans `/build` aux niveaux standard et full, lance `prove` sur les tests d'acceptation approuvés avec la commande ciblée du repo (« Verifying your work ») ; sur demande ailleurs ;
- rapporte le verdict, la commande, la sortie littérale ;
- seule exception à « ne rien modifier » : le remplacement temporaire fait par `prove_test.py`, restauré ; ne jamais remplacer de fichiers à la main ;
- une sauvegarde restée : lancer `recover` et le dire avant toute autre chose.
— Acceptance : test de contenu sur `verifier.md` ; contrôle manuel sur un changement réel (une fonction et son test).

**R6 — Nouveaux échecs.** Une commande de vérification rouge est relancée en `base-run` : rouge aussi → « déjà présent sur la base », verte → « apporté par le changement » ; les noms des tests en échec sont repris de la sortie quand ils sont lisibles.
— Acceptance : test de contenu sur `verifier.md` ; test unitaire de `base-run`.

**R7 — Tests existants modifiés.** verifier lance `modified-tests` et liste chaque test existant modifié ou supprimé comme « à approuver par la personne » (en complément des faits de `weakened_tests.py`, qu'il ne remplace pas).
— Acceptance : test unitaire de `modified-tests` ; test de contenu sur `verifier.md`.

**R8 — `/build` s'arrête si le test ne prouve rien.** Étape 3 : verdict `not_proven` → `/build` ne déclare pas fini ; la personne décide (renforcer le test ou accepter en le notant dans le rapport). `not_possible` ou `timeout` → dit dans le rapport, pas d'arrêt. Sans agent verifier, l'agent principal lance le script lui-même.
— Acceptance : test de contenu sur `commands/build.md`, sous le budget de 4 000 caractères.

**R9 — Warehouse (dbt) sur la cible dev.** Une commande qui lance une requête sur un entrepôt (dbt, ou déclarée comme telle dans AGENTS.md) n'est lancée par `prove` ou `base-run` que si une cible de développement est déclarée dans AGENTS.md ; verifier annonce la commande, la cible et le coût estimé (dry run quand l'outil le permet) **pour les deux lancements** (version de base, puis reconstruction avec le nouveau code après restauration) et attend un accord unique ; sans cible dev déclarée : `not_possible` (« test sur l'entrepôt sans cible dev »). Jamais la production.
— Acceptance : test de contenu sur `verifier.md` ; pas de test exécuté contre un entrepôt.

**R10 — Evidence dans la MR.** `/ship` (skill `mr`, section Evidence) cite le verdict de la preuve quand il existe : « échoue sans le code (preuve) » ou « non prouvé, accepté par <personne> ».
— Acceptance : test de contenu.

**R11 — Installation et livraison.** Script installé dans `~/.ai-kit/bin/` pour toutes les CLI (`py -3` sous Windows) ; doc (`docs/commands.md`, page `docs/review.md` ou une page dédiée) ; VERSION 4.12.0, CHANGELOG, versions, snapshot. Un cas d'eval écrit pour la preuve, non lancé.
— Acceptance : test d'installation (le script est présent) ; suite complète verte sur la CI Mac, Linux et Windows.

## Contracts
| Object | Shape (fields, or one row per … for data) | Key | Sources | Freshness | Rules (compatibility, dates, exclusions, NULL) |
| --- | --- | --- | --- | --- | --- |
| Sortie JSON de `prove_test.py` | `{"schema": 1, "mode", "base", "merge_base", "verdict", "exit_code", "command", "swapped": [chemins], "kept": [chemins], "tests", "output_tail", "reason", "error"}` ; `tests` : chemins dans `prove`, objets `{"path", "change": "modified"|"deleted"}` dans `modified-tests` | une par appel | git (lecture), le working tree, la commande | à chaque appel | `verdict` : `prove` ∈ {proven, not_proven, not_possible, timeout} ; `base-run` ∈ {fails_on_base, passes_on_base, not_possible, timeout} ; `recover` ∈ {recovered, nothing_to_recover} ; code de sortie 0, 2 (repo illisible, sauvegarde présente, restauration incomplète), 130 (interrompu, fichiers restaurés) ; pas de rétrocompatibilité à garder |
| Dossier `<repo>/.ai-kit-proof/` | `.gitignore` (`*`), `manifest.json`, copies des fichiers | un par repo | le script | pendant un lancement seulement | supprimé après restauration ; sa présence au lancement = interruption |

## Constraints and policies applied
- **Ne jamais perdre une modification** (pratiques, intent) : sauvegarde avant, restauration toujours, empreintes vérifiées, reprise après crash (R4).
- **Agents en lecture seule sauf verifier** (kit) ; l'exception « remplacement temporaire » est bornée au script (R5).
- **Codex refuse d'écrire dans `.git`** (étude du 2026-11-13) : pas de `git stash`, `worktree`, `checkout` ; la sauvegarde vit dans le working tree, dossier auto-ignoré (R4).
- **Jamais la production, coût mesuré, accord** (pratiques d'équipe, intent) : R9.
- **Tests jamais affaiblis** (00_KIT) : la preuve ne modifie aucun test ; `not_proven` arrête `/build`.
- **ADR 0027** (un signal déterministe nourrit la relecture, il ne bloque jamais) : la preuve est un signal pour verifier et la personne ; l'arrêt de `/build` sur `not_proven` est une décision demandée à la personne, pas un blocage automatique.
- **ADR 0028** (test d'abord là où une personne regarde le test) : la preuve s'ajoute après approbation, elle ne remplace pas l'approbation.
- **Pas d'installation, bibliothèque standard** (kit) ; Mac, Linux et Windows.

## Threats
- Perte de modifications de la personne (le script écrit dans son working tree) — sauvegarde octet pour octet, restauration dans tous les chemins de sortie, empreintes revérifiées, refus et `recover` si une sauvegarde reste — résiduel : coupure de courant pendant l'écriture d'un fichier ; la sauvegarde reste et `recover` la remet.
- Injection de commande via la commande de test — lancée sans shell, en liste d'arguments, telle que déclarée dans AGENTS.md — résiduel : la commande du repo elle-même est exécutée, comme aujourd'hui par verifier.
- Code propriétaire copié dans `.ai-kit-proof/` — dans le repo, ignoré par git, supprimé après — résiduel : un outil de synchronisation de dossiers (cloud) peut le copier pendant le lancement.
- Requête sur un entrepôt — cible dev déclarée obligatoire, coût annoncé, accord — résiduel : un coût imprévu si l'estimation n'est pas disponible.

## Areas of concern
- **Relecture à froid du build (2026-11-14)** : code-reviewer et security-reviewer ont trouvé des chemins de perte de données (bit exécutable, liens symboliques, fichier sauvegardé pendant la preuve, sous-dossier de monorepo, timeout sans les petits-enfants, manifeste piégé lu par `recover`, deux lancements simultanés) ; tous corrigés, un test de régression chacun. Ajouts au contrat : chemins relatifs à la racine et commande lancée dans le dossier courant ; la création de `.ai-kit-proof/` sert de verrou ; un fichier modifié pendant la preuve n'est jamais écrasé ; `recover` sur accord de la personne ; commande d'entrepôt avec `--target` explicite, accord demandé par l'agent principal ; timeout par défaut 420 s ; version de base passée par les filtres de checkout de la personne (fins de ligne).
- **Changement d'un invariant** : verifier « ne modifie rien » devient « ne modifie rien, sauf le remplacement temporaire du script ». Je propose un court ADR (numéro après 0032) « verifier may swap files temporarily to prove a test ». — Hachem décide.
- **Fausse preuve** : retirer un fichier de configuration modifié par le changement peut faire échouer le test pour une autre raison que le code. Atténuation : `--keep`, et la sortie littérale montrée. — à juger sur usage.
- **Outils qui surveillent les fichiers** (IDE, rechargement à chaud, `watch`) : ils voient le remplacement temporaire. — le rapport le signale ; pas de solution technique proposée.
- **Budget de `/build`** : 3 989 / 4 000 caractères ; R8 doit tenir en quelques mots, le détail va dans `verifier.md`. — à résoudre au build.
- **Interruption brutale** (kill -9, crash de la CLI) : la restauration n'a pas lieu ; elle dépend de `recover` au lancement suivant. — accepté, signalé dans la doc.
- **Intent** : la règle « refus sur working tree sale » de l'intent est remplacée par la sauvegarde (décision du 2026-11-14), puisque le travail n'est pas commité au moment de `/build`.

## Open questions
- Assumption: Codex (sandbox workspace-write) laisse écrire dans le working tree hors `.git` et lancer la commande de test ; Gemini et agy aussi. — à vérifier au build, sur Codex et Claude Code seulement (Gemini et agy coûtent).
- Assumption: l'arrêt propre sous Windows (CTRL_BREAK) suffit pour restaurer quand la CLI arrête verifier. — à vérifier sur la CI Windows.
- Assumption: le contrôle d'intégrité du kit (4.8) ne signale pas `.ai-kit-proof/` dans le repo de la personne (il surveille les fichiers installés par le kit). — à vérifier au build.
- Découpage en tâches : `/build` ou le skill `to-tickets`.
