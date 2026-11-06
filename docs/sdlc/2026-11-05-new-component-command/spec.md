# Spec: créer un profil, un skill, un agent ou une commande du kit en une commande (from intent.md 2026-11-05)

Status: accepted · Reviewed by: Hachem LATRACH · Date: 2026-11-05 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full (hérité de l'intent : nouvelle sous-commande publique `ai-kit new`, qui écrit dans le repo du kit, commite, pousse et ouvre une merge request, avec accord explicite).

## Objective
Depuis son clone du kit, une personne crée un profil, un skill, un agent ou une commande en répondant à quelques questions, et obtient une merge request dont la CI passe sans retouche des catalogues, des versions, du snapshot ni du tableau des profils.

## Scope and non-goals
- In : la sous-commande `ai-kit new <profile|skill|agent|command>` (module `installer/new.py`, câblage dans `installer/cli.py`) ; les squelettes ; la mise à jour des catalogues, de `versions.lock.json`, du snapshot et du tableau des profils ; les vérifications ; branche, commit, push et merge request après confirmation ; la proposition de `write-a-skill` à la fin ; tests, docs, CHANGELOG.
- Out : la création dans `internal/` (promotion manuelle par les mainteneurs) ; un profil contribué (les profils vont dans `profiles/`) ; les skills personnels et de repo projet ; une commande agent `/new` ; l'écriture du contenu par un modèle ; la modification d'un composant existant ; une installation ZIP.

## Requirements
Each requirement has a verifiable acceptance criterion.

1. **Point d'entrée.** `ai-kit new <type> [--name N] [--owner O] [--description D] [--category C] [--skill S] [--label L] [--yes] [--no-mr]`, avec `<type>` parmi `profile`, `skill`, `agent`, `command`. Les valeurs manquantes sont demandées (Questionary quand il est là, sinon `input()` en mode texte). — Acceptance : `ai-kit new skill --name demo --owner team-x --yes --no-mr` crée le skill sans aucune question ; sans `--yes`, la catégorie, la description et une confirmation avant écriture sont demandées ; `ai-kit new` sans type liste les quatre types et sort en code 2.
2. **Seulement dans un clone du kit.** Le dossier du kit (`AI_KIT_SOURCE_DIR` du lanceur, sinon le dossier du code) doit être la racine d'un dépôt git et contenir `skills/catalog.json` et `profiles/`. Un fichier partagé déjà modifié (catalogue, verrou des versions, snapshot) arrête aussi la commande avant écriture, pour qu'il n'entre pas dans son commit. — Acceptance : depuis une installation ZIP ou un dossier sans `.git`, la commande s'arrête avec `ai-kit new needs a git clone of the kit` et n'écrit rien.
3. **Nom valide et libre.** Un nom suit `^[a-z0-9][a-z0-9-]*$`, n'existe ni dans `skills/catalog.json`, ni dans `agents/catalog.json`, ni dans `commands/`, ni dans `profiles/`, ni sur le disque. — Acceptance : un nom pris ou invalide est refusé avec la raison, rien n'est écrit.
4. **Skill.** Écrit `skills/contrib/<nom>/SKILL.md` (en-tête `name`, `description` ; corps avec les `<…>` à remplir) et l'entrée du catalogue : `path`, `origin: "contrib"`, `owner`, `description`, `category` (`tool`, `domain`, `reference` ou `workflow`, demandée), `tier: "optional"`, `version: "1.0.0"`. Un `domain` reçoit les sections `## Rationalizations and rebuttals` (trois lignes à remplir, le minimum que vérifient les tests) et `## In the kit commands`. Écrit aussi `evals/cases/NN-<nom>.json` (prochain numéro libre) avec `requires.skills` et un `_doc` marqué « to complete », et ajoute une section `### \`<nom>\`` à `docs/eval-cases.md`. — Acceptance : les tests existants du catalogue, de `contrib`, des dépendances et de la page des cas passent sur le skill créé.
5. **Agent.** Écrit `agents/contrib/<nom>.md` (en-tête `name`, `description`, `tools` lecture seule par défaut comme `agents/defaults.json`, `max_turns: 12`, `timeout_mins: 5` ; corps à remplir) et l'entrée de `agents/catalog.json` : `path`, `origin: "contrib"`, `owner`, `version: "1.0.0"`. — Acceptance : les tests de `agents/contrib` passent ; l'agent n'est dans aucun profil.
6. **Commande.** Écrit `commands/<nom>.md` au format pivot (`name`, `description` en anglais, `category: tool`, `skills: [<skill>]`, `order: 1000`) avec un prompt qui active le skill, gère l'absence de l'outil d'activation, contient `{{args}}` et demande la ligne de niveau. Le skill cité doit exister dans le catalogue. — Acceptance : `tests.test_commands` et `tests.test_consistency` passent ; un skill inconnu est refusé.
7. **Profil.** Écrit `profiles/<id>.toml` à partir de `general.toml` : `id`, `label`, `order` (prochain libre par dizaine), les playbooks choisis parmi les skills `domain` du catalogue, les agents choisis, `mcp = []`. Lance `scripts/profile_table.py --write`. — Acceptance : le profil apparaît dans le menu de `setup`, le tableau de `docs/getting-started.md` est à jour, la règle « aucun playbook dans `general` » tient.
8. **Vérifications.** Après écriture : `runtime/check_skills.py` sur le nouveau composant, `scripts/versions.py --update`, `tests/snapshot.py --update`, puis les tests ciblés (`test_skills_catalog`, `test_skill_dependencies`, `test_commands`, `test_consistency`, `test_evals_runner`, `test_profiles_general`, `test_versions`, `test_evals_and_playbooks`, `test_invariants`, `test_snapshot`). Un échec arrête avant le commit et affiche la sortie réelle. — Acceptance : un skill contenant `curl … | sh` est créé puis refusé par `check_skills`, sans commit.
9. **Branche, commit, merge request, avec accord.** La commande crée la branche `new-<type>-<nom>` depuis la branche courante, jamais sur `main` en place. Elle affiche les fichiers, le remote et la branche, puis demande une confirmation avant le commit, et une autre avant le push et la merge request. Ces deux confirmations sont toujours posées : `--yes` ne répond qu'aux questions de contenu (catégorie, playbooks, agents), jamais au commit ni au push. La merge request passe par `gh pr create` si le remote est GitHub, `glab mr create` sinon, quand l'outil est présent et connecté ; sinon la commande affiche l'URL de création. `--no-mr` s'arrête après les vérifications, sans commit. — Acceptance : sans accord, aucun commit ni push ; la branche courante reste inchangée ; un refus laisse les fichiers pour relecture.
10. **Fin.** La commande liste les `<…>` restant à remplir, propose le skill `write-a-skill` pour un skill ou un agent, et rappelle ce qu'elle ne fait pas : le tableau des profils du README pour un profil, l'entrée de `docs/tools.md` pour une commande. — Acceptance : la sortie nomme chaque fichier qui contient encore un `<…>`.

## Contracts
| Object | Shape | Key | Sources | Freshness | Rules |
| --- | --- | --- | --- | --- | --- |
| `ai-kit new` | sous-commande du lanceur, passée à `installer/cli.py` comme `friction` et `news` | `<type>` | arguments, questions | à chaque appel | codes de sortie : 0 fait, 1 vérification, commit ou push en échec, ou réponse « non », 2 usage invalide ou refus avant écriture (nom pris, pas un clone, pas de terminal, fichiers modifiés), 130 annulé |
| `skills/catalog.json`, `agents/catalog.json` | une entrée par composant, clés existantes inchangées | nom | la commande | à la création | ajout seulement, ordre et formatage existants gardés (indentation 2) |
| `profiles/<id>.toml` | mêmes clés que `general.toml` | `id` | la commande | à la création | aucune clé nouvelle |

## Constraints and policies applied
- Règle 4 du kit : commit et push seulement avec l'accord de la personne dans la session ; ici, deux confirmations toujours posées, à un terminal : `--yes` ne les donne pas, un pipe non plus.
- Pratique d'équipe : réutiliser l'existant ; les mises à jour passent par `scripts/versions.py`, `tests/snapshot.py`, `scripts/profile_table.py`, `runtime/check_skills.py`, sans réimplémenter.
- `docs/architecture.md` : aucun module d'`installer/` au-dessus de 800 lignes ; `cli.py` en compte 788, la logique va dans `installer/new.py`, `cli.py` ne reçoit que le câblage.
- ADR 0004 : pas d'appel au modèle ; le seul accès réseau est le push et la merge request acceptés.
- ADR 0009 et la règle des noms : les squelettes et la doc ne nomment ni personne, ni organisation, ni produit concurrent.
- Python 3.9, Mac, Windows, Linux ; fichiers ouverts avec `encoding='utf-8'`.

## Areas of concern
- **Accord sur les commits** : décidé, `--yes` ne couvre que les questions de contenu ; le commit et le push demandent toujours une confirmation, ce qui tient la règle 4 sans exception, même quand un agent lance la commande.
- **Snapshot** : `tests/snapshot.py --update` réécrit la référence de 16 scénarios ; un composant `contrib` n'est installé dans aucun profil, donc la référence ne devrait pas changer pour un skill ou un agent. Pour un profil, elle change ; la MR doit le montrer.
- **Cas d'éval squelette** : il passe `--dry-run` mais ne mesure rien tant que le prompt et les critères sont des `<…>` ; `test_evals_runner` doit l'accepter sans le prendre pour un vrai cas.
- **Merge request et outils** : `glab` ou `gh` absents ou non connectés ; la commande ne doit pas échouer pour autant (elle donne l'URL).
- **Recovery** : tout se passe sur une branche ; `git branch -D new-<type>-<nom>` et `git push origin --delete` annulent tout. Un échec de vérification laisse les fichiers non commités pour relecture.

## Decisions after review
Relecture indépendante et vérificateur, sur le premier jet ; constats reproduits, chacun avec son test dans `tests/test_new.py`.
- **Pas de terminal** : refus avant toute écriture, sauf avec `--no-mr --yes`. Un agent s'arrête donc à `--no-mr` ; le commit reste le sien, avec ton accord, ou le tien.
- **Modifications non commitées** : refus aussi pour ce que lisent le verrou des versions et le snapshot, pas seulement les fichiers réécrits. Sinon le commit enregistre une modification qu'il ne contient pas.
- **Windows** : le snapshot n'est pas réécrit, sa référence contient des chemins POSIX.
- **Commande** : elle rejoint les profils qui installent son skill et n'ont pas de liste `commands` ; le tableau et le snapshot changent, et sont commités. Refusée sur un playbook (`domain`), car les commandes restent neutres.
- **Version** : le squelette est enregistré en `1.0.0` ; son premier contenu passe en `1.0.1`. La commande le dit. La règle du verrou ne change pas.
- **Retour arrière** : chaque arrêt donne les commandes exactes, Ctrl+C compris, et un test exécute celles qu'il imprime ; un commit qui échoue revient à la branche de départ ; après un push, elles couvrent aussi la branche distante et la merge request, que la commande ne supprime pas elle-même.
- **Terminal réel** : ton premier essai a planté dans Questionary, sous la couche de couleur, chemin qu'aucun test ne couvrait (faux UI). Le test passe désormais par un pseudo-terminal, jusqu'à un vrai push vers un dépôt local. Il a aussi trouvé le texte de remplacement pré-rempli dans le champ, et un refus de repo posé après les questions.

## Open questions
- Assumption: les contributeurs ont un clone git du kit avec `glab` ou `gh` connecté ; à vérifier au pilote.
