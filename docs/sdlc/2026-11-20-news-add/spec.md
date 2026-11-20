# Spec: ajouter une annonce — `ai-kit news --add` et `/news` (4.19.0)

Status: accepted (2026-11-20) · Reviewed by: Hachem LATRACH · Date: 2026-11-20 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full : une commande de plus dans la surface CLI bornée par l'ADR 0025 (amendement), et ce qu'elle écrit atterrit dans le contexte de tous les agents une fois tagué.

## Risks first
| Risque | Comment il se voit | Mitigation / retour arrière |
|---|---|---|
| Une entrée mal formée passe : `whats-new` l'ignore en silence, l'annonce n'arrive jamais | rien au démarrage de session | `news --add` écrit puis relance `check_news.problems()` ; un problème remet le fichier tel qu'il était (exit 1) ; la CI garde son étape |
| Le texte injecté dans tous les agents contient une consigne (prompt injection) ou un secret | dans le contexte de chaque session après le tag | inchangé : relecture en MR avant le tag ; la commande n'écrit que le fichier local, ne commite ni ne tague rien |
| L'agent écrit dans le mauvais dépôt (le cache du kit, `~/.ai-kit`) | `NEWS.md` modifié hors d'un Core | `--path` doit contenir `NEWS.md` **et** `aikit.toml` (un dépôt Core) ; refus sous `~/.ai-kit` |
| Le shell développe le texte (`$(...)`, backticks) quand l'agent appelle la commande | texte altéré | `/news` passe le texte sur l'entrée standard, jamais en argument, comme `/friction` |
| Une annonce trop longue mange le budget du démarrage (`CONTEXT_LIMIT` = 8000, partagé avec le CHANGELOG) | annonce tronquée | refus au-delà de 1500 caractères de texte (décision du 2026-11-20) |

Retour arrière global : revert du commit ; aucune donnée ni configuration de poste n'est touchée.

## Objective
Écrire une entrée de `NEWS.md` d'un Core sans connaître le format à la main, et sans jamais produire une entrée que le hook ignorerait.

## Scope and non-goals
- In :
  - `ai-kit news --add [--path DIR] [--id ID] [--title T] [--teams a,b] [--until YYYY-MM-DD]`, texte sur l'entrée standard ou demandé ; questions en terminal pour ce qui manque, refus (exit 2) sans terminal ;
  - `/news`, commande du kit **optionnelle** (`default: false`, `extra_commands`) : pose les questions dans la session, puis appelle `ai-kit news --add` avec le texte sur l'entrée standard ;
  - ADR 0025 amendé (treize commandes ; l'agent peut lancer `news --add`) ; `docs/hooks.md#whats-new`, `docs/extending.md`, `docs/roadmap.md` (item 7 fait).
- Out :
  - commit, MR, tag ou release du Core : la commande affiche les étapes suivantes, la personne les fait ;
  - modifier ou supprimer une entrée existante ;
  - vérifier que les noms de `teams:` existent (le hook compare au nom de la Team active ; une liste des Teams n'est pas connue du Core).

## Requirements
**R1 — Écriture.** L'entrée `## <aujourd'hui> <id> : <titre>`, puis `teams:` / `until:` si donnés, une ligne vide, le texte, est insérée avant la première entrée existante (après l'en-tête du fichier), le reste du fichier intact octet pour octet.
— Acceptance : test — sur une copie de `NEWS.md`, le diff est exactement l'entrée ajoutée ; `parse_news` la relit avec les mêmes champs.

**R2 — Id.** Par défaut, dérivé du titre (minuscules, `a-z0-9-`, 3 à 32 caractères) ; `--id` le remplace. Un id déjà présent est refusé (exit 1), avec le conseil d'en choisir un autre.
— Acceptance : test — titre « Gemini CLI sur Windows corrigé ! » → `gemini-cli-sur-windows-corrige` ; un id en double refusé, fichier inchangé.

**R3 — Contrôle.** Après écriture, `check_news.problems()` sur le fichier ; un problème le remet à l'identique et sort en 1 avec la liste. Dates invalides et `until` passé refusés avant écriture.
— Acceptance : test — `--until 2026-02-30` refusé, `--until` antérieur à aujourd'hui refusé, fichier inchangé.

**R4 — Dépôt visé.** `--path` (défaut : dossier courant) doit contenir `NEWS.md` et `aikit.toml` ; refus sinon, et refus sous `~/.ai-kit`.
— Acceptance : test — un dossier sans `aikit.toml` refusé ; `~/.ai-kit/...` refusé.

**R5 — Taille.** Texte vide refusé ; texte au-delà de 1500 caractères refusé.
— Acceptance : test aux deux bornes.

**R6 — Sans terminal.** Titre ou texte manquant sans terminal → exit 2, rien d'écrit ; avec tout en options et le texte sur l'entrée standard → aucune question.
— Acceptance : test en sous-processus sans TTY.

**R7 — `/news`.** Commande `default: false` ; son prompt passe le texte sur l'entrée standard (macOS/Linux et PowerShell), ne commite rien, et répète la sortie de la commande ; tient dans le budget des commandes (< 4000 caractères).
— Acceptance : tests existants de cohérence et de budget des commandes, plus un test qui vérifie `default: false` et l'absence du texte en argument.

**R8 — Suite.** La sortie rappelle : relire, MR, tag `vX.Y.Z` du Core, puis `ai-kit sync` sur les postes.
— Acceptance : test sur la sortie.

## Decisions (2026-11-20)
1. Limite de taille du texte : 1500 caractères.
2. Défaut de `--path` : dossier courant.
