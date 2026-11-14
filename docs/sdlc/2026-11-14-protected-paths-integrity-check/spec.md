# Spec: protéger la configuration du kit en vérifiant le résultat, pas les commandes (from intent.md 2026-11-14)

Status: accepted (2026-11-14) · Reviewed by: the maintainer · Date: 2026-11-14 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full, hérité de l'intent : remplace le contrat d'un garde-fou actif par défaut, ajoute un événement de hook sur chaque CLI.

## Objective
Quand l'agent change, par une commande ou un outil, un fichier que le kit a installé, la personne et l'agent le savent à l'action suivante, de la même façon sur Mac, Windows et Linux ; seules les écritures dont le chemin est exact (outils d'écriture) et les commandes du kit qui changent l'installation sont encore refusées avant.

## Scope and non-goals
- In : `runtime/hooks/protected-paths.py` (partie shell retirée, sauf le refus des commandes du kit) ; un contrôle d'intégrité (nouveau script `runtime/hooks/integrity.py`, appelé après chaque outil et au démarrage) ; `state.json` (empreintes du `.git/config` et des `.git/hooks` du clone du kit) ; les adaptateurs (`installer/adapters/claude.py`, `codex.py`, `gemini.py`, `agy.py`) et `runtime/hooks/hooks.json` ; `ai-kit doctor` ; docs (`hooks.md`, `cli/matrice.md`, pages CLI, README, `sdlc-workflow.md`) ; ADR 0030 (remplace 0006) ; note de recherche Laya ; tests ; CHANGELOG 4.8.0.
- Out : toute analyse de commande shell autre que le refus des commandes du kit ; restaurer un fichier automatiquement ; écrire les permissions des CLI ; vérifier les fichiers que la personne gère elle-même (le reste des settings des CLI, `~/.gitconfig`, `USER.md`).
- Livré en deux changements (au plus trois tests d'acceptation chacun) : **A'** = R1 à R3 et R6 (le garde-fou réduit) ; **B'** = R4 et R5 (le contrôle d'intégrité). A' ne sort pas sans B'.

## Requirements
1. **Outils d'écriture : refus exact, inchangé.** Une écriture (write, edit, patch) dont le fichier est la configuration du kit ou d'une CLI (`CONFIG_PATHS`, fichiers installés de `state.json`), le `.git/config` ou les `.git/hooks` du clone du kit, ou les settings de CLI d'un repo, est refusée ; un `.env` qui fixe `AI_KIT_*` ou `DBT_TARGET` aussi. Un lien vers un dossier protégé est ce dossier.
   — Acceptation : les tests existants des outils d'écriture passent sans modification de leurs cas de configuration.
2. **Shell : plus d'analyse, sauf les commandes du kit.** Une commande shell n'est plus refusée par `protected-paths`, quoi qu'elle nomme, sauf une commande du kit qui change l'installation ou facture un appel (`ai-kit init`, `sync`, `rollback`, `uninstall`, `team use`, `doctor --live`, `friction --publish`, `python -m ai_kit …`, un lanceur du kit), refusée comme en 4.7.1. Les règles shell du clone du kit, de `~/.gitconfig` et du `.env` disparaissent (le kit lance git sans configuration globale, `docs/repositories.md` ; `dbt-prod-guard` ignore déjà un `.env`).
   — Acceptation : `echo x > ~/.claude/settings.json`, `rm ~/.ai-kit/hooks/protected-paths.py`, `cd ~/.claude && sed -i s/a/b/ settings.json`, `git config --file <clone>/.git/config remote.origin.url x` passent le garde-fou ; `ai-kit sync`, `python3 -m ai_kit uninstall --yes`, `sh <clone>/scripts/bootstrap.sh` sont refusés.
3. **Motifs propres à un repo retirés.** `<repo>/.ai-kit/protected-paths` n'est plus lu ; ce fichier n'est plus protégé.
   — Acceptation : dans un repo qui déclare `*.lock`, une écriture de `poetry.lock` (outil et shell) passe ; une écriture de `.claude/settings.local.json` par un outil d'écriture reste refusée.
4. **Contrôle après chaque action (changement B').** Après chaque appel d'outil, sur Claude Code (`PostToolUse`), Codex (`PostToolUse`) et Gemini CLI (`AfterTool`), `integrity.py` compare chaque fichier de `state.json` (`files`, plus les empreintes du `.git/config` et des `.git/hooks` du clone) à son état enregistré : taille et date d'abord, empreinte sha256 seulement si elles diffèrent ; un fichier absent compte. Un écart produit, **une fois par ensemble d'écarts**, un message qui nomme les fichiers et la commande `ai-kit sync --offline`, dans `additionalContext` (avec la consigne de le dire à la personne en première ligne) et dans `systemMessage` (affiché à la personne). Jamais `decision: "block"` (il remplacerait le résultat de l'outil sur Gemini et Codex). Rien n'est écrit quand rien n'a changé.
   — Acceptation : un fichier installé modifié produit le message à l'appel suivant, au format de chaque CLI ; le même écart n'est pas répété ; un nouvel écart l'est ; après restauration plus rien ; le `.git/config` du clone modifié est signalé ; sans écart, le contrôle de 237 fichiers prend moins de 30 ms (mesuré).
5. **Contrôle au démarrage (changement B').** Au début de chaque session, sur les quatre CLI, le même contrôle s'exécute (avec le marqueur commun : un écart déjà annoncé après une action ne l'est pas de nouveau) ; sur agy, c'est le seul contrôle (le format d'une sortie après l'outil n'y est pas documenté ; décidé le 2026-11-14), au format déjà utilisé par `whats-new` ; `systemMessage` est ajouté là où la CLI le documente au démarrage (Claude Code, Gemini CLI, Codex).
   — Acceptation : un fichier modifié hors session est annoncé au démarrage suivant ; sur agy, le message passe par `injectSteps`.
6. **Contrat changé exprès, dit.** Les tests qui attendaient un refus shell (hors commandes du kit) passent en autorisés ou sont retirés, chacun listé dans le CHANGELOG 4.8.0 ; `tests/test_repo_paths_shell.py` et `tests/test_protected_paths_reads.py` sont retirés.
   — Acceptation : `python3 scripts/offline_tests.py discover -s tests` vert, la liste dans le CHANGELOG.

## Contracts
| Object | Shape | Key | Sources | Freshness | Rules |
| --- | --- | --- | --- | --- | --- |
| Réponse de `protected-paths` | inchangée : `{}` / `{"decision": "ask"}` (agy) ou refus `Blocked by the kit: …` | un appel d'outil | hook installé | à chaque appel | refuse seulement R1 et les commandes du kit (R2) |
| Sortie de `integrity.py` après l'outil | Claude Code : `{"systemMessage": …, "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": …}}` ; Gemini CLI : `{"systemMessage": …, "hookSpecificOutput": {"additionalContext": …}}` ; Codex : `{"systemMessage": …, "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": …}}` ; rien (`{}`) sans écart nouveau | un appel d'outil | `state.json` | à chaque appel | jamais `decision` ; formes exactes vérifiées contre la doc de chaque CLI au build |
| Sortie au démarrage | la forme actuelle de `whats-new` (`additionalContext`, `injectSteps` pour agy) plus `systemMessage` où documenté | une session | `state.json` | à chaque démarrage | le texte d'intégrité vient en premier |
| `state.json` | `files` inchangé ; nouveau `kit_git: {"<rel>": "<sha256>"}` pour le `.git/config` et les `.git/hooks/*` du clone | chemin relatif | `ai-kit sync`/`init` | à chaque sync | absent pour une installation par ZIP sans clone |
| Marqueur `~/.ai-kit/integrity.json` | `{"announced": "<sha256 de la liste triée des écarts>", "stamps": {"<rel>": [size, mtime]}}` | — | `integrity.py` | écrit seulement quand l'ensemble ou un stamp change | protégé pour les outils d'écriture (R1) ; illisible = absent |

## Constraints and policies applied
- Même comportement sur tous les OS : aucune logique propre à un shell dans le nouveau contrôle (intent).
- Anti-erreur, pas barrière (ADR 0006 → 0030) : une modification passe, elle est signalée et réparable.
- ADR 0012 et 0003 : lecture locale seulement, rien d'envoyé, aucun modèle.
- Permissions des CLI : jamais écrites par le kit.
- Tests jamais affaiblis pour cacher une régression : chaque test déplacé ou retiré l'est par contrat, listé (R6).
- Bibliothèque standard ; sur Windows, la commande du hook passe par la forme que chaque adaptateur utilise déjà (`commandWindows` pour Codex quand il en faut une).
- Repo générique et public (ADR 0009).

## Threats
- L'agent modifie un fichier du kit (hook, règle) par une commande — signalé à l'action suivante, réparable par `ai-kit sync --offline` — l'action suivante s'exécute déjà avec la configuration modifiée.
- L'agent retire le hook « après l'outil » des settings de sa CLI — les settings écrits par le kit sont dans `files`, donc l'écart est vu au prochain contrôle qui tourne (le démarrage suivant) — la fin de la session courante n'est plus contrôlée.
- L'agent fait taire le contrôle en modifiant le marqueur ou `state.json` — refusé aux outils d'écriture (R1) ; par une commande, `doctor` recalcule sans marqueur et `state.json` modifié change les fichiers attendus — une écriture shell coordonnée de `state.json` et du fichier cache l'écart jusqu'au prochain `sync`.
- Le `.git/config` du clone est redirigé vers une autre source — signalé à l'action suivante (empreinte `kit_git`) — un `ai-kit sync` lancé par la personne avant de lire le message irait chercher à la nouvelle source.
- L'agent ne relaie pas le message — `systemMessage` affiché à la personne sur trois CLI, `doctor` — sur agy, la personne dépend de l'agent au démarrage ou de `doctor`.

## Areas of concern
- **Prévention perdue pour le shell** : assumé par le mainteneur (2026-11-14), en échange d'un contrôle identique sur tous les OS.
- **Menace sur le clone et `sync`** (ci-dessus) : `ai-kit sync` pourrait vérifier `kit_git` avant de lancer git et refuser sur un écart ; à décider au build si le coût est faible. Décide : le mainteneur.
- **Fausse alerte du mainteneur** qui modifie le `.git/config` de son clone : prévenu une fois, il relance `sync`.
- **Coût par action** : le contrôle tourne après chaque appel d'outil ; objectif 30 ms, mesuré au build, sinon on réduit (par exemple, seulement les fichiers de hooks et de settings après l'outil, tous au démarrage).

## Open questions
- Assumption: les formes de sortie de R4 citées sont celles des pages lues le 2026-11-14 (Claude Code `code.claude.com/docs/en/hooks`, Gemini CLI `geminicli.com/docs/hooks/reference/`, Codex `learn.chatgpt.com/docs/hooks`) ; revérifiées au build contre la version installée de chaque CLI (`VERIFIED` des adaptateurs).
- Version : 4.8.0, confirmée à `/ship`.

Le découpage se fait dans `/build` (A' puis B'), ou to-tickets sur demande.
