# Spec: Repérer les tests affaiblis dans /review avec un script déterministe (from intent.md 2026-11-13)

Status: accepted (2026-11-13) · Reviewed by: Hachem LATRACH · Date: 2026-11-13 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full, hérité de intent.md (contrat partagé : `/review` ; un script installé sur chaque poste).

## Objective
Quand on lance `/review`, un script du kit lit le diff et liste, sans jugement, les tests supprimés, désactivés ou relâchés ; l'agent de revue classe chaque cas (voulu, non demandé, ambigu) et signale en **Important** ceux que personne n'a demandés.

## Scope and non-goals
- In :
  - Un script `runtime/weakened_tests.py` (Python, bibliothèque standard), installé dans `~/.ai-kit/bin/` par `init` et `sync`, à côté de `friction.py`.
  - Niveau 1, tous langages : fichier de test supprimé, renommé ou déplacé.
  - Niveau 2, par famille : dbt, Java (Spring inclus), Python, JavaScript (React, Vue, React Native inclus), PHP, Go, Rust, Scala.
  - Une étape dans la skill `code-review` qui lance le script, lit son JSON et classe chaque fait ; une ligne dans `commands/review.md`.
  - L'ajout du script à la liste des outils du kit autorisés par `protected-paths`.
  - Tests hors ligne par famille, un cas d'eval, l'ADR 0027, les docs, le CHANGELOG.
- Out :
  - `/build` et `/test` (le script n'y tourne pas).
  - Bloquer quoi que ce soit : ni hook, ni code de sortie qui arrête la revue.
  - Analyse syntaxique complète (AST) : le script lit le diff ligne à ligne et les deux versions d'un fichier de test.
  - Juger si un changement est voulu : c'est l'agent de revue, puis l'humain.
  - La CI des dépôts : le script peut y être réutilisé plus tard, mais ce n'est pas livré ici.
  - Un playbook pour PHP, Go, Rust ou Scala.

## Requirements
Chaque exigence a un critère d'acceptation vérifiable ; les critères 1 à 9 sont prouvés par les tests hors ligne (`scripts/offline_tests.py`), sans modèle.

1. **Périmètre identique à `/review`.** Le script compare la base (argument `--base`, sinon `origin/HEAD`, sinon `main` puis `master`) via `git merge-base`, et inclut les changements indexés, non indexés et les nouveaux fichiers non suivis. — Acceptation : sur un dépôt d'essai avec un commit, une modification indexée, une non indexée et un fichier non suivi, chaque cas apparaît dans la sortie.
2. **Niveau 1 : fichier de test supprimé.** Un fichier reconnu comme test (table « Familles » ci-dessous, ou dossier `test/`, `tests/`, `__tests__/`, `spec/`) supprimé dans le diff donne un fait `test_file_deleted`. — Acceptation : la suppression de `tests/test_export.py` donne ce fait ; celle de `src/export.py` n'en donne aucun.
3. **Test déplacé, pas supprimé.** Un fichier renommé (détection de renommage de git) ou un test retiré d'un fichier puis ajouté sous le même nom dans un autre fichier du diff donne `test_moved`, jamais `test_removed` ni `test_file_deleted`. — Acceptation : déplacer `test_export_archived` de `tests/a.py` vers `tests/b.py` ne donne que `test_moved`.
4. **Test retiré.** Un test (déclaration de la famille) présent à la base et absent après, sans réapparition ailleurs, donne `test_removed` avec son nom. — Acceptation : un cas par famille.
5. **Test désactivé.** Une marque de désactivation ajoutée (colonne « Désactivé » des familles) donne `test_disabled`. — Acceptation : un cas par famille ; une marque déjà présente à la base n'en donne pas.
6. **Test focalisé.** En JavaScript, `.only` ajouté (`it.only`, `test.only`, `describe.only`, `fit`, `fdescribe`) donne `test_focused` : il fait taire les autres tests du fichier. — Acceptation : `it.only` ajouté est signalé.
7. **Assertion retirée.** Dans un fichier de test, une ligne d'assertion (colonne « Assertion ») retirée sans ligne d'assertion ajoutée dans le même test donne `assertion_removed`. — Acceptation : retirer `assert total == 3` est signalé ; remplacer `assertEquals(3, total)` par `assertEquals(4, total)` ne l'est pas (changement de valeur attendue, laissé à l'agent avec le fait `assertion_changed`).
8. **dbt : seuils et sévérité.** `severity: error` → `warn`, `error_if` ou `warn_if` relâché, `enabled: false` ajouté sur un test, un test retiré d'un `.yml`, un fichier supprimé sous `tests/` donnent respectivement `severity_lowered`, `threshold_relaxed`, `test_disabled`, `test_removed`, `test_file_deleted`. — Acceptation : un cas par fait ; `error_if: ">100"` → `">0"` (resserré) ne donne rien.
9. **Sortie stable.** Le script écrit sur la sortie standard un JSON conforme au contrat ci-dessous, trié par fichier puis ligne, et sort avec le code 0 même sans fait ; il sort avec le code 2 et un JSON `error` s'il ne peut pas lire le dépôt. — Acceptation : deux exécutions sur le même dépôt donnent la même sortie ; hors d'un dépôt git, code 2 et `error` renseigné.
10. **Lecture seule.** Le script n'écrit aucun fichier, n'ouvre aucune connexion réseau, n'appelle aucun modèle ; il ne lance que `git` en lecture (`diff`, `merge-base`, `show`, `ls-files`, `rev-parse`), avec la configuration du dépôt neutralisée comme ailleurs dans le kit (`core.fsmonitor=false`, `core.hooksPath` vide). — Acceptation : un test vérifie la liste des sous-commandes git appelées et l'absence d'écriture dans le dossier d'essai.
11. **La revue le lance.** La skill `code-review` lance le script avant les passes (`python3 ~/.ai-kit/bin/weakened_tests.py --base <base>`, `py -3 …` sous Windows), passe son JSON aux agents de revue délégués, et ajoute une passe **Tests** :
    - fait couvert par un contrat nommé (demande de la personne dans la session, `spec.md`, `intent.md` ou `plan.md` qui nomme ce test ou ce comportement) → pas de finding, mentionné dans le rapport comme « changement de test voulu » ;
    - fait sans contrat nommé → finding **Important**, pass Tests, avec le fichier, la ligne et le fait ;
    - contrat nommé mais vague → une question à la personne, pas un finding ;
    - le message de commit ne compte jamais comme contrat ;
    - `test_moved` et `assertion_changed` sont lus par l'agent, finding seulement s'il voit un affaiblissement.
    — Acceptation : le cas d'eval (exigence 13) ; le test de contenu vérifie que la skill cite le script, la passe Tests et la règle du commit.
12. **La revue survit au script.** Si le script manque, échoue ou rend `error`, la revue fait ses autres passes et écrit dans ses limites « vérification des tests non faite : <raison> ». — Acceptation : le texte de la skill le dit (test de contenu) ; le cas d'eval en mode sans script passe toujours les autres critères.
13. **Mesure.** Un nouveau cas d'eval `22-review-flags-weakened-test` : un diff qui mêle un changement légitime, un test supprimé et un `error_if` dbt relâché, sans demande de la personne ; critère : la réponse signale les deux, en Important, et ne signale pas le changement légitime. Le cas `07-contract-change-updates-its-test` sert de témoin : il doit continuer de passer (pas de finding sur un changement demandé). — Acceptation : le cas existe et passe les tests du runner sans modèle (`--stand-in`) ; la campagne facturée (environ 18 appels) n'est lancée qu'avec l'accord de la personne.
14. **Le garde-fou laisse passer le script.** `protected-paths` autorise `~/.ai-kit/bin/weakened_tests.py` comme il autorise `friction.py` (`KIT_TOOLS`), aux mêmes conditions (aucun autre mot de la commande ne vise un chemin protégé). — Acceptation : un test de hook ; la commande avec une redirection vers un chemin protégé reste bloquée.

### Familles
Reconnaissance par chemin, puis marques lues dans le diff. « Assertion » ne vaut que dans un fichier de test.

| Famille | Fichier de test | Déclaration d'un test | Désactivé | Assertion |
| --- | --- | --- | --- | --- |
| dbt | `tests/**/*.sql` ; `tests:` / `data_tests:` dans `models/**/*.yml` | entrée sous `tests:` / `data_tests:`, fichier sous `tests/` | `enabled: false` | `severity`, `error_if`, `warn_if` (exigence 8) |
| Java (Spring) | `*Test.java`, `*Tests.java`, `*IT.java`, `src/test/**` | `@Test`, `@ParameterizedTest` | `@Disabled`, `@Ignore` | `assert*(`, `assertThat(`, `verify(` |
| Python | `test_*.py`, `*_test.py`, `tests/**/*.py` | `def test_`, `class Test` | `@pytest.mark.skip`, `skipif`, `xfail`, `@unittest.skip`, `pytest.skip(` | `assert `, `self.assert`, `pytest.raises(` |
| JavaScript (React, Vue, React Native) | `*.test.*`, `*.spec.*` (`js`, `jsx`, `ts`, `tsx`, `mjs`, `cjs`, `vue`), `__tests__/**` | `it(`, `test(` | `it.skip`, `test.skip`, `describe.skip`, `xit`, `xdescribe`, `test.todo` | `expect(`, `assert` |
| PHP | `*Test.php`, `tests/**/*.php` | `function test`, `#[Test]`, `@test`, `it(` / `test(` (Pest) | `markTestSkipped(`, `markTestIncomplete(`, `->skip(` | `$this->assert`, `self::assert`, `expect(` |
| Go | `*_test.go` | `func Test` | `t.Skip(`, `t.SkipNow(` | `t.Error`, `t.Fatal`, `assert.`, `require.` |
| Rust | `tests/**/*.rs` ; fichiers avec `#[cfg(test)]` | `#[test]` | `#[ignore]` | `assert!`, `assert_eq!`, `assert_ne!` |
| Scala | `*Spec.scala`, `*Test.scala`, `*Suite.scala`, `src/test/**` | `test(`, `it(`, `should`, `in {` | `ignore(`, `pending`, `.ignore` | `assert(`, `shouldBe`, `should be`, `assertEquals(` |

## Contracts

| Object | Shape (fields) | Key | Sources | Freshness | Rules |
| --- | --- | --- | --- | --- | --- |
| Sortie de `weakened_tests.py` (JSON, stdout) | `{"schema": 1, "base": str, "merge_base": str, "error": str\|null, "facts": [Fact], "families_seen": [str], "files_unrecognized": int}` | — | le dépôt git courant | calculée à chaque appel | `schema` monte à toute rupture ; champs ajoutés sans rupture |
| `Fact` | `{"kind": str, "family": str\|null, "path": str, "line": int\|null, "test": str\|null, "before": str\|null, "after": str\|null, "moved_to": str\|null}` | (`path`, `line`, `kind`) | diff et versions du fichier | idem | `kind` ∈ `test_file_deleted`, `test_moved`, `test_removed`, `test_disabled`, `test_focused`, `assertion_removed`, `assertion_changed`, `severity_lowered`, `threshold_relaxed` ; `family` null au niveau 1 ; `before`/`after` = la ligne citée, tronquée à 200 caractères |
| Ligne de commande | `weakened_tests.py [--base REF] [--repo PATH]` | — | — | — | codes de sortie : 0 (sortie valide, avec ou sans faits), 2 (dépôt illisible : `error` renseigné) ; jamais d'autre effet |
| `KIT_TOOLS` de `protected-paths` | ajoute `/.ai-kit/bin/weakened_tests.py` | — | `runtime/hooks/protected-paths.py:232` | — | mêmes conditions que `friction.py` |
| Passe **Tests** de `code-review` | findings tagués `Tests`, sévérité Important ; ligne de limites si le script échoue | — | `skills/internal/common/code-review/SKILL.md` | — | `aikit-version` de la skill 1.0.1 → 1.1.0, enregistrée dans `versions.lock.json` |

## Constraints and policies applied
- Aucun appel au modèle et aucun réseau dans le moteur et les tests (ADR 0004) ; le script n'utilise que `git` local.
- Le garde-fou protège la configuration du kit ; un outil du kit n'y entre que nommé dans `KIT_TOOLS` (ADR 0006, ADR 0019).
- Dépôt générique et public, en anglais (ADR 0009) : code, messages, cas d'eval et docs sans nom d'outil concurrent, d'entreprise ou de personne interne ; les noms de frameworks de test (pytest, JUnit, Jest…) sont des faits techniques, pas des produits concurrents du kit.
- Un seul script par usage, écrit une fois (même principe que ADR 0007 pour les frictions).
- Une commande lance seulement des skills invocables par le modèle (ADR 0020) : `code-review` l'est.
- Pages générales sans nom de CLI dans la prose (`tests/test_consistency.py`).
- Tests : jamais affaiblis pour masquer une régression ; la référence `tests/golden/install-snapshot.json` change exprès (nouveau fichier installé), mise à jour avec `tests/snapshot.py --update` et dite dans le CHANGELOG.
- Toute skill modifiée change de version (`scripts/versions.py`).
- Evals facturées : un cas ciblé, lancé seulement avec l'accord de la personne, pas sur Gemini ni agy.
- La décision est consignée dans l'ADR 0027, proposé avec cette spec.

## Areas of concern
1. **Faux positifs, surtout par famille.** Une assertion déplacée dans une fonction d'aide ressemble à une assertion retirée ; Scala et PHP ont plusieurs styles de déclaration. Atténuation : `assertion_changed` et `test_moved` laissent le jugement à l'agent ; cas négatifs obligatoires par famille. — Décide : la personne, au vu des tests hors ligne, famille par famille ; une famille trop bruyante peut sortir sans toucher aux autres.
2. **Sévérité Important vs changement voulu.** La règle du kit autorise un test changé exprès ; la passe Tests le signale en Important sauf contrat nommé. Un contrat donné oralement dans une autre session n'est pas visible. — Décide : la personne ; la règle retenue (contrat dans la session ou dans les fichiers du changement) est volontairement stricte.
3. **Agents délégués sans shell.** `ai-kit-code-reviewer` n'a que Read et Grep : l'agent principal doit lancer le script et transmettre le JSON. Sur une CLI sans agents, la skill fait la passe elle-même. — À vérifier dans `/build` sur les 4 CLI.
4. **Interpréteur.** Le script est lancé par `python3` (ou `py -3`), comme `friction.py`, pas par l'environnement privé du kit. Un poste sans `python3` sur le PATH tombe dans l'exigence 12.
5. **Taille du diff.** Sur un très gros diff, la sortie JSON peut être longue pour le contexte de l'agent. Proposition : au-delà de 200 faits, le script les compte par `kind` et ne détaille que les 200 premiers (`truncated: true`). — À trancher dans `/build` si un dépôt réel l'atteint.

## Open questions
- Le CLI de la campagne d'eval facturée : Claude Code ou Codex (non bloquant ; la personne choisit au moment de lancer).
- Le nom `weakened_tests.py` : proposé ; un nom qui commence par `test_` est écarté (il serait pris pour un test par les outils des dépôts qui forkent le kit).
- Assumption : les fichiers de test suivent les conventions de la table « Familles ». À vérifier sur des dépôts réels pendant `/build` ; un dépôt hors convention ne profite que du niveau 1 sur ce que les dossiers `test/`, `tests/`, `__tests__/`, `spec/` désignent.
- Assumption : la détection de renommage de git (seuil par défaut) suffit pour la plupart des déplacements de fichiers ; sinon le rapprochement par nom de test (exigence 3) prend le relais.
- Le découpage en tranches (socle et dbt, puis Java, Python, JavaScript, puis PHP, Go, Rust, Scala) est fait par `/build` ; `to-tickets` peut en faire des tickets sur demande.
- Décidé le 2026-11-13, pour la tranche 2 (après la revue de la tranche 1) :
  - Filtres git : vérifier d'abord si `git diff` contre l'arbre de travail lance les filtres `clean` du dépôt (git-lfs) ; si oui, les neutraliser pour tenir l'exigence 10 (lecture seule).
  - Dossiers génériques : dans une famille connue, un fichier sous `test/`, `tests/`, `__tests__/` ou `spec/` n'est un test que s'il suit les noms de la famille (table « Familles ») ; les données (`.json`, `.csv`, `.yml` hors dbt…) n'y sont plus des tests. La règle large du dossier reste pour les langages sans famille.
