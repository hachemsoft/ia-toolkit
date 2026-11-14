# Spec: protected-paths ne refuse plus des commandes qui ne font que lire (from intent.md 2026-11-14)

Status: accepted (2026-11-14: delivered in two changes, R1-R3 then R4; symlink in Limits; /review full; one test moved) · Reviewed by: the maintainer · Date: 2026-11-14 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full, hérité de l'intent : changement du contrat documenté d'un garde-fou.

## Objective
Le garde-fou `protected-paths` laisse passer trois formes de commandes shell qui ne modifient aucun fichier protégé (un `cd` dans un dossier de configuration suivi de lectures, le message d'un `git commit`, `sed` sans écriture ni exécution), sans qu'aucune écriture refusée aujourd'hui ne passe.

## Scope and non-goals
- In : `shell_config_write` et ses fonctions (`touches_config_folder`, `only_reads`, la recherche de noms) dans `runtime/hooks/protected-paths.py` ; les formes Bash, PowerShell (`Set-Location`, `Push-Location`, `sl`) et cmd (`chdir`) du `cd` ; `docs/hooks.md` ; amendement de l'ADR 0006 ; tests ; CHANGELOG.
- Out : exécuter un hook installé à la main (`python3 ~/.ai-kit/hooks/…`) ; `awk` ; `sed -f <script>` ; les règles des chemins protégés d'un repo (`repo_shell_reason`), qui acceptent déjà `sed` en lecture et le message de commit ; le suivi d'un `cd` par les autres garde-fous (`shell-guard.py`, limite documentée).

## Requirements
Toutes les commandes ci-dessous sont envoyées au hook comme outil shell (Bash et, pour R1, PowerShell), avec `HOME` isolé.

1. **`cd` dans un sous-dossier ordinaire d'un dossier de config.** Un dossier est ordinaire quand ce n'est pas la racine d'un dossier de config (`~/.ai-kit`, `~/.gemini`, `~/.codex`, `~/.claude`) et qu'aucun nom protégé (`CONFIG_PATHS`, `REPO_CONFIG`, fichiers installés de `state.json`) ne se trouve dessous. Le `cd` y est traité comme un `cd` hors config : la suite de la commande est jugée par les règles habituelles. Exception : un mot de la suite qui contient un segment `..` rend la commande « lecteurs seulement » (R2), pour qu'un chemin relatif ne remonte pas vers un fichier protégé.
   — Acceptation : `cd ~/.claude/projects/p/memory && cat a.md`, `cd ~/.claude/projects/p/memory && echo x >> MEMORY.md` et `cd ~/.claude/projects/p/memory && ls ..` passent ; `cd ~/.claude/projects/p && echo x > ../../settings.json` est refusé.
2. **`cd` dans la racine d'un dossier de config ou dans un dossier qui contient un nom protégé**, puis seulement des lectures. Autorisé quand chaque programme de chaque segment qui suit le `cd`, dans toute la commande, est un lecteur au sens de `only_reads`, en considérant que chaque mot peut être un nom protégé (un `cp` est donc refusé). La suite ne doit contenir aucune redirection (`>`, `>>`, `>|`, `&>` ; `tee` n'est pas un lecteur). Un joker n'est pas refusé en soi : avec des lecteurs seulement, il ne peut rien écrire (corrigé au /build : le joker entre guillemets de `find . -name '*.md'` contredisait le critère d'acceptation). Un `cd` seul passe.
   — Acceptation : `cd ~/.claude`, `cd ~/.claude && ls`, `cd ~/.claude && find . -name '*.md'`, `Set-Location $HOME\.claude; Get-ChildItem` passent ; `cd ~/.claude && rm settings.json`, `cd ~/.claude && sed -i s/a/b/ settings.json`, `cd ~/.ai-kit && echo x > aikit.toml`, `cd ~/.claude && cp x settings.json`, `cd ~/.claude && rm *.json`, `cd ~/.claude || rm -rf x` et `Set-Location $HOME\.claude; Remove-Item settings.json` sont refusés.
3. **Message de `git commit`.** La valeur de `-m`/`--message` (formes `-m "…"`, `-m '…'`, `-m…` collé, `--message=…`, plusieurs `-m`) n'est plus cherchée comme nom protégé, et `git commit` dont seul le message cite un nom protégé passe. Le masquage a lieu avant le découpage en segments, pour qu'un `;` ou `&&` dans le message ne coupe pas la commande. Une valeur qui contient `$(` ou un backtick reste lue telle quelle (une substitution s'exécute dans des guillemets doubles). `-F`/`--file` n'est pas concerné.
   — Acceptation : `git commit -m "docs: explain .ai-kit/protected-paths"`, `git commit -m "a; b ~/.claude/settings.json"` et `git commit -m 'x' -m 'cite .claude/settings.json'` passent ; `git commit -m "$(rm ~/.claude/settings.json)"`, `` git commit -m "`rm ~/.claude/settings.json`" `` et `git commit -m x && rm ~/.claude/settings.json` sont refusés.
4. **Abandonné (2026-11-14), `sed` reste refusé.** La revue adversariale, confirmée par des sondes, a montré que lire le script avec `shlex` ne revient pas à le lire comme le shell : une variable non quotée devenue `-i` (`X=-i; sed -e p $X <fichier protégé>`) et un `#` au milieu d'un mot, que `shlex` prend pour un commentaire, laissaient passer des écritures que le code actuel refuse. Chaque correction en appelait une autre, sans preuve possible, pour une seule friction (`grep … | sed`). Texte d'origine, gardé pour mémoire : **`sed` lecteur.** `sed` (et `gsed`) devient un lecteur quand aucun mot n'est `-i…`, `--in-place…`, `-f…`, `--file…` ou `-s` combiné avec `-i`, et que chaque script (valeurs de `-e`/`--expression`, sinon le premier argument positionnel) n'est fait que de commandes d'une liste fermée : adresses (nombres, `$`, `/regex/`, plages `a,b`, `!`), `p`, `d`, `q`, `Q`, `=`, `n`, `N`, `y/…/…/`, `s/…/…/` avec des drapeaux parmi `g`, `p`, `i`, `I`, `m`, `M` et des chiffres, groupes `{…}`, séparés par `;` ou des retours à la ligne. Tout le reste (`w`, `W`, `r`, `R`, `e`, drapeaux `w` ou `e` de `s`, un délimiteur ou un script non analysable) laisse `sed` hors des lecteurs.
   — Acceptation : `grep x ~/.claude/settings.json | sed 's/a/b/'`, `sed -n '1,5p' ~/.gemini/settings.json` et `sed -E 's#a#b#g' ~/.ai-kit/aikit.toml` passent ; `sed -i 's/a/b/' ~/.ai-kit/aikit.toml`, `sed -n 'w ~/.ai-kit/aikit.toml' /etc/hosts`, `sed 's/a/b/w ~/.ai-kit/aikit.toml' /etc/hosts`, `echo ~/.claude/settings.json | sed 's/^/rm /e'`, `sed -f s.sed ~/.claude/settings.json` et `awk '{print}' ~/.ai-kit/aikit.toml` sont refusés.
5. **Aucune régression des refus.** Chaque commande de `BLOCKED` dans `tests/test_guardrail_bypasses.py` et des listes de refus de `tests/test_hooks.py` et `tests/test_repo_paths_shell.py` reste refusée, sauf `sed -n '1,5p' ~/.gemini/settings.json`, qui passe dans `ALLOWED` (changement de contrat voulu, R4).
   — Acceptation : `python3 scripts/offline_tests.py discover -s tests` vert, avec ce seul test déplacé, dit dans le CHANGELOG.

## Contracts
| Object | Shape | Key | Sources | Freshness | Rules |
| --- | --- | --- | --- | --- | --- |
| Réponse du hook `protected-paths` à un appel shell | JSON `{}` (ou `{"decision": "allow"}` pour agy) qui laisse passer, ou `{"decision": "deny", "reason": "Blocked by the kit: …"}` | une réponse par appel d'outil | `runtime/hooks/protected-paths.py`, installé sous `~/.ai-kit/hooks/` | à chaque appel | forme inchangée ; seul l'ensemble des commandes acceptées s'élargit, selon R1 à R4 |
| Règles documentées | texte de `docs/hooks.md` (`protected-paths`, Limits) et ADR 0006 | — | repo | à la release | la phrase « a `cd` into a configuration folder … is refused » et « sed and awk are never readers » sont réécrites ; l'ADR reçoit un « Amended: 4.6.2 » |

## Constraints and policies applied
- **Le garde-fou n'est pas une barrière de sécurité** (ADR 0006, `docs/hooks.md` Limits) : on vise les erreurs honnêtes, mais on ne rouvre aucun contournement déjà fermé (R5).
- **Liste fermée de ce qui est permis** (`docs/hooks.md`) : `sed` entre par une grammaire fermée, pas par une liste de ce qui écrit.
- **Tests jamais affaiblis** (kit, 00_KIT) : un seul test change, parce que le contrat change exprès ; il est dit et un test prouve le nouveau comportement (R4).
- **Bibliothèque standard seulement, pas de réseau, rapide** : l'analyse de `sed` et du message de commit est faite sur le texte ; on ne lit `state.json` qu'une fois par appel, comme aujourd'hui.
- **Repo générique et public** (ADR 0009) : exemples sans nom interne ; docs en anglais.

## Areas of concern
- **Chemins relatifs après un `cd` dans un dossier ordinaire** : ils sont le seul nouveau moyen d'atteindre un fichier protégé. R1 les couvre avec la règle du `..`, mais un lien symbolique placé dans ce dossier vers un fichier protégé n'est pas vu (comme un script qui écrit, limite déjà documentée). À ajouter aux Limits de `docs/hooks.md`. Décide : le mainteneur.
- **Grammaire de `sed`** : c'est la partie la plus fragile. Un drapeau GNU oublié dans la liste fermée donne un faux refus (sans danger), une erreur dans l'analyse du délimiteur peut laisser passer `w` ou `e`. Les cas de refus de R4 sont les garde-fous ; un relecteur doit relire l'analyseur ligne à ligne. Décide : la revue `/review full`.
- **Masquage du message de commit avant le découpage** : il touche le texte vu par toutes les règles qui suivent (`kit_shell_reason`, `kit_command_reason`, la règle `.env`). Le masquage ne doit s'appliquer qu'aux valeurs de `-m`/`--message` d'un `git … commit` et garder tout ce qui contient `$(` ou un backtick.
- **Deux règles qui divergeaient** : les chemins protégés d'un repo acceptent déjà `sed` en lecture et le message de commit, la configuration du kit non. Le spec les aligne dans le sens le plus permissif des deux, borné par R5 ; c'est un choix, pas une conséquence.

## Open questions
- Version : 4.6.2 (correctif de garde-fou) proposée ; décidée à `/ship`.
- Assumption: aucune autre règle (`kit_shell_reason`, le garde-fou du dossier du kit) ne refuse indépendamment ces mêmes commandes ; vérifié au moment des tests d'acceptation de `/build`, qui passent par le hook entier.
- Assumption: PowerShell n'a pas d'équivalent de `sed` à traiter ; `Set-Location` et `Push-Location` suivent R1 et R2 comme `cd`.

Le découpage en tranches se fait dans `/build` (ou to-tickets sur demande).
