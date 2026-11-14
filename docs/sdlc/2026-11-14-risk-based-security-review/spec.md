# Spec: Revue de sécurité selon le risque, relecteurs indépendants en parallèle (from intent.md 2026-11-14)

Status: accepted (2026-11-14) · Reviewed by: Hachem LATRACH · Date: 2026-11-14 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full, hérité de intent.md (contrats partagés : `/review`, `/spec`, la sélection d'agents par défaut).

## Objective
Quand un changement présente un risque de sécurité, `/review` le fait relire par des relecteurs indépendants (code, sécurité, doute), chacun dans un contexte neuf, en même temps quand le CLI le permet, puis rend une seule liste fusionnée et classée ; `/spec` écrit les menaces de ces changements, et le scanner que le dépôt déclare est lancé.

## Scope and non-goals
- In :
  - Les déclencheurs de la revue de sécurité dédiée, reconnus par l'agent, et dits dans le rapport.
  - La revue par relecteurs indépendants (`ai-kit-code-reviewer`, `ai-kit-security-reviewer`, `ai-kit-doubter`) et la synthèse.
  - `security-reviewer` dans la sélection par défaut.
  - Une section « Threats » dans le modèle `spec.md` et dans `/spec`, pour les mêmes déclencheurs.
  - Une ligne optionnelle « Security scan » dans le modèle `AGENTS.md`, lancée par `/review` quand elle est remplie.
  - Docs, ADR 0029, CHANGELOG, tests de contenu, un cas d'eval.
- Out :
  - Imposer ou installer un outil de sécurité ; appel réseau ; dépendance.
  - Bloquer un merge : les relecteurs signalent, l'humain décide.
  - `/build` : il ne lance pas de relecteur de sécurité (son étape de revue reste celle de 4.6.1).
  - Un audit ou un test d'intrusion : hors de portée d'une revue par IA, et dit dans les docs.
  - Les playbooks de domaine : leur passe Domain et leurs relecteurs restent tels quels.

## Requirements
1. **Déclencheurs.** La revue de sécurité dédiée se lance quand au moins un est vrai : le niveau du changement est full ; le changement touche des données personnelles, des secrets ou des jetons, l'authentification ou les droits, une entrée venant de l'extérieur (requête, fichier, webhook), ou un appel à un service externe ; `spec.md` du changement a une section Threats ; la personne la demande. La liste est un guide, pas une liste fermée de mots. — Acceptation : la skill `code-review` porte ces déclencheurs (test de contenu) ; le rapport de `/review` dit en une ligne « Security review: dedicated (<déclencheur>) » ou « Security review: in the main pass (no trigger) ».
2. **Relecteurs indépendants.** Quand la revue dédiée se déclenche, l'agent principal donne à chaque relecteur installé (code-reviewer, security-reviewer, doubter) les commandes du périmètre, le diff, les fichiers et les faits du contrôle des tests (ADR 0027), et le spec, intent ou plan quand il existe ; chacun travaille dans un contexte neuf ; ils sont lancés en même temps quand le CLI sait lancer des sous-agents en parallèle, l'un après l'autre sinon, indépendamment du réglage `[agents] parallel` (ils ne font que lire). Un relecteur non installé : sa passe est faite par l'agent principal, et c'est dit dans les limites. — Acceptation : test de contenu sur la skill ; le cas d'eval (exigence 8).
3. **`security-reviewer` par défaut.** `aikit-default: "true"` ; il est installé avec les autres agents par défaut sur les 4 CLI. — Acceptation : tableau de sélection (`scripts/selection_table.py`) et snapshot d'installation montrent 5 agents par défaut ; test d'installation.
4. **Synthèse.** L'agent principal rend une seule liste : les doublons fusionnés (le même fichier, la même ligne ou le même défaut), classée sur l'échelle existante (Important, Minor, Nit, cinq nits au plus) ; chaque finding porte sa passe, sa gravité, le fichier et la ligne, et le ou les relecteurs qui l'ont trouvé ; un désaccord entre relecteurs est dit comme un point à trancher, pas tranché en silence ; les limites disent quels relecteurs ont tourné, et s'ils ont tourné en même temps ou l'un après l'autre. — Acceptation : test de contenu ; le cas d'eval.
5. **Threats en conception.** Quand un déclencheur de l'exigence 1 s'applique au changement décrit, `/spec` ajoute à `spec.md` une section « Threats » : pour chaque menace, la parade et le risque restant ; le modèle `templates/spec.md` contient la section, à supprimer quand aucun déclencheur ne s'applique. La passe Compliance de `/review` vérifie chaque parade. — Acceptation : test de contenu sur `/spec`, le modèle et la skill.
6. **Scanner déclaré.** Le modèle `templates/AGENTS.md` gagne, dans « Verifying your work », une ligne optionnelle « Security scan » (commande du dépôt, à supprimer sans outil). Quand l'`AGENTS.md` du dépôt en a une, `/review` la lance sur le périmètre et donne sa sortie au security-reviewer ; sans ligne, rien n'est lancé et rien n'est inventé. — Acceptation : test de contenu.
7. **Budgets.** `commands/review.md` et `commands/spec.md` restent sous 4 000 caractères ; le contexte du kit n'est pas modifié. Le détail vit dans la skill `code-review`, l'agent `security-reviewer` et les modèles. — Acceptation : `tests/test_commands.py`, `tests/test_context_layers.py`.
8. **Mesure.** Un cas d'eval `review-finds-logged-personal-data` : un diff où un numéro de téléphone est écrit dans un log au milieu de changements légitimes, sans demande ; critère jugé sur le fond (le log du numéro est nommé et présenté comme un problème à corriger). Campagne : Codex, 3 runs par configuration (sans kit, 4.6.1, nouvelle version), soit 9 appels, lancée seulement avec l'accord de la personne. — Acceptation : le cas existe avec des exemples de réponses (pass et fail) vérifiés hors ligne.

## Contracts

| Object | Shape | Rules |
| --- | --- | --- |
| Ligne de rapport de `/review` | `Security review: dedicated (<trigger>)` ou `Security review: in the main pass (no trigger)` | toujours présente ; en tête des limites |
| Finding de la synthèse | `- **<Severity> · <Pass>** — <file>:<line> — <defect> (<reviewer>[, <reviewer>])` | échelle Important, Minor, Nit inchangée ; un finding de sécurité sans scénario d'exploitation est au plus Minor (règle de l'agent) |
| Section `## Threats` de `spec.md` | une ligne par menace : menace — parade — risque restant | présente seulement quand un déclencheur s'applique ; titre en anglais, contenu dans la langue de l'équipe |
| Ligne `Security scan` de `AGENTS.md` | `| Security scan | <commande> | <commande complète> |` dans la table « Verifying your work » | optionnelle ; jamais inventée par l'agent |
| `security-reviewer.md` | `aikit-default: "true"`, `aikit-version: "1.1.0"` | ses consignes gagnent : lire les Threats de la spec et la sortie du scanner quand elles sont fournies |

## Constraints and policies applied
- Rien ne bloque ; l'humain décide (règle de gravité de `code-review`, ADR 0027 pour les signaux déterministes).
- Les relecteurs ne font que lire (Read, Grep) ; sur Codex, la lecture seule tient par leur instruction (`AGENT_TOOLS = 'instruction'`), pas par l'outil : déjà le cas des relecteurs actuels.
- Budgets de taille (docs/extending.md#size-budgets) : le détail va dans la skill et les modèles.
- Toute skill ou tout agent modifié change de version (`scripts/versions.py`) ; le snapshot change exprès (un agent par défaut de plus), dit dans le CHANGELOG.
- Dépôt public et générique : aucun nom d'outil de sécurité commercial ni de projet, d'entreprise ou de personne dans les textes, les modèles ou les cas d'eval ; la ligne « Security scan » donne un exemple neutre ou aucun.
- Evals facturées : un cas, 9 appels, avec accord.
- Décision consignée dans l'ADR 0029.

## Areas of concern
1. **Reconnaître les déclencheurs sans liste fermée.** L'agent juge à partir du niveau, du diff, des chemins et de la spec ; il peut en rater un (faux négatif) ou en voir un partout (coût). Atténuation : la ligne « Security review: … » rend le choix visible à chaque revue, et le cas d'eval mesure un faux négatif typique. — Décide : la personne, à l'usage (frictions).
2. **Coût en tokens.** Trois relecteurs au lieu d'un sur les changements à risque. Le déclenchement limite ; la ligne de rapport rend le coût visible. — Décide : la personne ; resserrer les déclencheurs est le retour arrière.
3. **Doubter en dehors de `full`.** Aujourd'hui il ne tourne qu'en `/review full` ; avec cette spec il tourne aussi sur un changement standard qui touche un déclencheur. C'est voulu (le doute sur « aucune donnée ne fuit » est utile), mais c'est un relecteur de plus. — Décide : la personne.
4. **Codex et la lecture seule par instruction.** Un relecteur Codex pourrait écrire malgré son instruction ; risque déjà présent pour les relecteurs actuels, inchangé. — Signalé, pas traité ici.
5. **Faux sentiment de sécurité.** La doc dit qu'une revue par IA ne remplace ni un audit ni un test d'intrusion, et que le scanner déclaré complète sans remplacer.

## Decisions after the review of the change (2026-11-14)
La revue dédiée, appliquée à ce changement, a trouvé un défaut que la passe unique avait manqué. Décisions de la personne :
- **Exigence 6 retirée de cette version** : lancer le scan qu'un dépôt déclare dans son `AGENTS.md` ferait exécuter à `/review` une commande lue dans la copie revue, donc celle du changement relu (noms de fichiers injectables, secrets recopiés dans le contexte). Elle demande sa propre conception (commande lue dans la base, refusée quand le changement la touche).
- **Exigence 5** : la section Threats suit les déclencheurs de contenu (données personnelles, secrets, authentification, entrée externe, service externe), pas le niveau full ni la demande ; l'ADR le dit.
- **Le risque l'emporte sur le mode** : la revue dédiée tourne aussi en `/review quick`. `/build` et `implement` ne la lancent pas (hors périmètre, comme l'écrit Scope).
- Exigence 4 précisée : la forme du finding est dans la skill ; un relecteur qui ne revient pas est dit dans les limites ; en full, un seul passage du doubter porte aussi la question du retour arrière.

## Open questions
- Le découpage en tranches (déclencheurs, relecteurs, défaut et synthèse ; puis Threats ; puis scanner) est fait par `/build` ; `to-tickets` peut en faire des tickets sur demande.
- Assumption : les 4 CLI lancent un agent en lecture dans un contexte neuf ; vérifié par `docs/parallel-agents.md` (une exécution réelle par CLI, 2026-11-13) pour les sous-agents en lecture.
- Assumption : la nouvelle passe ne dépasse pas le budget de `/review` en ne mettant dans la commande que la ligne des déclencheurs et le renvoi à la skill ; à vérifier en `/build`.
