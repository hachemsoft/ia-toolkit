# Spec: Aides à la relecture 4.11.0 — cold review, doubter critique, guide de relecture, discussions de MR (from intent.md 2026-11-14)

Status: accepted (2026-11-14) · Reviewed by: Hachem LATRACH · Date: 2026-11-14 · Versioned: this file is the contract reviewers read in the merge request (MR)

Level: full (hérité de intent.md). Le périmètre 4.11.0 (numéro décalé : la 4.10.0 et la 4.10.1 viennent d'une autre session) est du texte (agents, skills, commandes, doc) plus les tests de contenu ; la page HTML (4.14.0) est hors périmètre.

## Objective
Rendre la relecture d'un changement plus rapide et plus fiable : des agents relecteurs qui jugent le code sans le récit de l'auteur (cold review), un doubter qui rend une position nette, un guide de relecture pour l'humain qui répond dans les fichiers, et la lecture des discussions de MR quand la MR existe.

## Scope and non-goals
- In:
  - règle **cold review** pour tous les agents relecteurs appelés par `/review` : `code-reviewer`, `security-reviewer`, `doubter`, et les relecteurs de domaine (`sql-reviewer`, `dbt-reviewer`, `infra-reviewer`, `architecture-reviewer`) ;
  - **doubter au format critique** et position en tête du rapport `/review` quand le doubter tourne ;
  - nouveau skill **`review-guide`** : guide de relecture Markdown local, marques `review:`, traitement en lot ;
  - marques `review:` proposées par `/spec` (sur `spec.md`) et `/build` (sur les tests d'acceptation avant approbation) ;
  - **discussions de MR** : lecture des discussions non résolues quand une MR existe ; post du guide et réponses dans les fils, avec accord ;
  - `.gitignore` du repo du kit : `docs/audits/` et `docs/sdlc/*/review-guide.md` ;
  - contexte du kit (`templates/kit-context.md`, section « Artifacts and git ») : `review-guide.md` est local ;
  - doc, CHANGELOG, VERSION 4.11.0, versions des composants, golden snapshot, tests.
- Out:
  - `review.html` (4.14.0) ;
  - preuve « le test échoue sans le code » et nouveaux agents (intent `2026-11-14-kit-agents`, 4.12.0 et suivantes) ;
  - la ligne `.gitignore` proposée aux repos des utilisateurs par `init-project-context` (réalignement en cours dans une autre session ; la ligne `**/docs/sdlc/**/review-guide.md` lui est transmise) ;
  - un agent `cold-reviewer` (la cold review est une règle, pas un rôle) ;
  - tout outil à installer ; toute eval lancée.

## Requirements
Each requirement has a verifiable acceptance criterion.

**R1 — Cold review : ce que le parent transmet.** Le skill `code-review` (section 3) dit que le parent donne à chaque relecteur, en contexte neuf : les commandes de portée, la base, la **sortie brute** de `git diff` (copiée telle quelle, jamais résumée ni reformulée), les chemins des fichiers, les faits de `weakened_tests.py`, la spec / intent / plan. Il ne donne **aucun récit de l'auteur** : ni résumé du changement, ni justification (« c'est sûr parce que… »), ni état des tests annoncé, ni guide de relecture. Les agents n'ayant que des outils de lecture, le diff brut reste fourni par le parent.
— Acceptance : le texte du skill contient la liste des éléments transmis et l'interdiction explicite du récit ; un test de contenu vérifie ces deux points.

**R2 — Cold review : ce que fait le relecteur.** Chaque agent relecteur du périmètre a, dans ses consignes : juger à partir du diff, des fichiers et de la spec ; tout récit ou justification de l'auteur trouvé dans le brief est **ignoré et signalé** dans les limites (« brief contenait un récit de l'auteur, ignoré ») ; la passe n'est pas rejetée.
— Acceptance : les six fichiers d'agents relecteurs et le doubter contiennent la règle ; un test de contenu la vérifie pour chacun.

**R3 — Doubter : affirmations étiquetées.** Le doubter reçoit en plus les affirmations de l'auteur (spec, intent, messages de commit, description de MR quand elle existe) **étiquetées « affirmations à vérifier »**, jamais présentées comme des faits. Les autres relecteurs ne les reçoivent pas.
— Acceptance : le skill `code-review` et `doubter.md` décrivent cette étiquette ; test de contenu.

**R4 — Doubter au format critique.** La sortie du doubter commence par :
```
position: pas d'objection | réserves | contre
objection la plus forte: <le meilleur argument contre, ou « aucune »>
alternative plus simple: <une phrase, ou « aucune »>
un inconnu comprendrait-il dans six mois: oui | non (<ce qui manque>)
```
puis le tableau existant affirmation / statut / preuve ou contre-exemple / action. Règles : pas d'objection fabriquée (si le changement est bon, une ligne) ; `contre` réservé à un coût réel, pas à une préférence ; pas de remarque de style. Le format vaut partout où le doubter est appelé (`/review`, workflow research).
— Acceptance : `doubter.md` contient les quatre champs, les trois règles ; test de contenu ; version du doubter montée.

**R5 — Position en tête du rapport `/review`.** Quand le doubter a tourné (mode full ou changement à risque, règles actuelles inchangées), le rapport `/review` affiche, juste après la ligne de portée, la position et l'objection la plus forte du doubter. Quand il n'a pas tourné : une ligne « Position : non évaluée (doubter non lancé : <raison>) ».
— Acceptance : section « 5. Report » du skill et `commands/review.md` décrivent la ligne ; test de contenu.

**R6 — Skill `review-guide` : le guide.** Nouveau skill `skills/internal/common/review-guide/SKILL.md`, installé par défaut, qui produit `review-guide.md` dans le dossier du changement `docs/sdlc/<date>-<slug>/` (créé s'il n'existe pas), avec les sections : **Ordre de lecture** (fichier:ligne, du cœur vers les conséquences), **Thèmes** (les hunks regroupés par thème, chacun avec ses fichiers:lignes), **Hypothèses** (ce que le changement suppose sans le dire), **Points à risque** (où concentrer l'attention), **À survoler** (mécanique : renommages, code généré), **Comment répondre** (les marques `review:`). Le guide peut porter le raisonnement de l'auteur : il est pour l'humain, et n'est **jamais donné aux agents relecteurs** avant leur passe (R1).
— Acceptance : le skill existe avec ces sections et la règle « jamais aux relecteurs avant leur passe » ; il apparaît dans la sélection par défaut et le catalogue ; tests de catalogue et de contenu.

**R7 — Quand le guide est proposé.** `/review` et `/ship` le proposent **en une ligne** aux niveaux standard et full, jamais en quick ; le guide n'est produit qu'après l'accord de la personne.
— Acceptance : `commands/review.md` et `commands/ship.md` contiennent la proposition conditionnée au niveau ; test de contenu.

**R8 — Marques `review:`.** Une marque est un commentaire du langage du fichier dont le contenu commence par `review:` : `<!-- review: … -->` (Markdown, HTML), `# review:` (Python, YAML, shell, TOML), `// review:` ou `/* review:` (JS, TS, Java, Go, Scala, PHP), `-- review:` (SQL, dbt). Le texte `review:` hors d'un commentaire n'est pas une marque.
— Acceptance : le skill `review-guide` liste ces formes et la règle ; test de contenu.

**R9 — Traitement en lot des marques.** Quand la personne dit qu'elle a relu (« relu », « reviewed » ou équivalent), l'agent : cherche toutes les marques dans les fichiers du changement (diff, fichiers nouveaux, fichiers du dossier du changement, y compris ceux ignorés par git) ; traite chacune ; **retire** une marque réglée ; **garde** une marque non réglée et ajoute dessous une réponse `review-reply: …` dans la même forme de commentaire (désaccord, décision à prendre) ; ne retire jamais une marque qu'il n'a pas traitée. Il rend un compte rendu par marque : fichier:ligne, la remarque, ce qui a été fait, et **l'extrait avant / après** (pas `git diff`, qui ne voit pas les fichiers ignorés), puis le décompte « N réglées, M ouvertes ».
— Acceptance : le skill décrit ces étapes, la règle « jamais retirer une marque non traitée » et le format du compte rendu ; test de contenu ; vérification manuelle sur un `spec.md` annoté (3 marques, dont une en désaccord).

**R10 — Marques dans `/spec` et `/build`.**
- `/spec` : après écriture de `spec.md`, propose en une ligne de le relire avec des marques `review:` puis de dire « relu ».
- `/build` (étape 2) : en montrant les tests d'acceptation qui échouent, propose de répondre par des marques `review:` dans les fichiers de test ; une marque ouverte vaut « pas encore approuvé ».
— Acceptance : `commands/spec.md` et `commands/build.md` contiennent ces lignes ; test de contenu ; la règle « aucun fichier existant ne change avant approbation » de `/build` reste inchangée.

**R11 — Marque oubliée signalée.** La passe Standards de `/review` signale toute marque `review:` ou `review-reply:` présente dans le diff : **Minor**, avec fichier:ligne.
— Acceptance : le skill `code-review` contient la règle et la sévérité ; test de contenu.

**R12 — Discussions de MR non résolues.** Quand `/review` tourne sur une branche qui a une MR (GitLab) ou une PR (GitHub) ouverte, l'agent lit ses discussions non résolues — GitLab : `glab mr view <id> --unresolved` ; GitHub : voir hypothèse H1 — et les traite comme des remarques à vérifier : chacune devient un constat confirmé, réfuté avec preuve, ou un point à trancher, dans une section « Discussions de MR » du rapport. Pas de forge joignable ou pas de MR : une ligne dans les limites, rien d'autre.
— Acceptance : le skill `code-review` décrit la détection, les commandes et la section ; test de contenu ; vérification manuelle sur une MR GitLab de test avec une discussion ouverte.

**R13 — Actions visibles sur la MR, avec accord.** Poster le guide en commentaire de MR et répondre dans un fil : seulement à la demande de la personne (réponses) ou sur sa proposition acceptée (guide), avec **le texte exact montré avant** et **un accord à chaque fois** ; jamais de résolution de fil par l'agent. Commandes : GitLab `glab mr note <id>` (hypothèse H2 pour la forme exacte), GitHub `gh pr comment <n> --body-file <fichier>`.
— Acceptance : `review-guide` et `code-review` décrivent la règle d'accord et l'interdiction de résoudre ; test de contenu.

**R14 — Fichiers locaux.** `.gitignore` du kit : ajout de `docs/audits/` (déjà fait localement) et de `docs/sdlc/*/review-guide.md`. `templates/kit-context.md` (« Artifacts and git ») : `review-guide.md` local, git-ignored, comme `intent.md` et `plan.md`.
— Acceptance : `git check-ignore docs/sdlc/2026-11-14-review-aids/review-guide.md docs/audits/x` répond pour les deux ; test de contenu sur le contexte.

**R15 — Livraison 4.11.0.** VERSION 4.11.0 ; CHANGELOG ; versions des composants montées (doubter, code-reviewer, security-reviewer, relecteurs de domaine, `code-review`, nouveau `review-guide`, commandes) puis `python3 scripts/versions.py --update` ; golden snapshot d'installation régénéré ; `docs/commands.md` et une page `docs/review.md` (cold review, guide, marques, MR). Aucun nom de kit ou produit tiers dans le repo.
— Acceptance : suite de tests verte (`python3 -m pytest` ou la commande déclarée par le repo) ; `versions.py` sans écart ; recherche manuelle des noms tiers vide.

## Contracts
| Object | Shape (fields, or one row per … for data) | Key | Sources | Freshness | Rules (compatibility, dates, exclusions, NULL) |
| --- | --- | --- | --- | --- | --- |
| Brief d'un agent relecteur | commandes de portée, base, diff brut, chemins, faits de tests, spec/intent/plan ; doubter : + affirmations étiquetées | un brief par agent et par passe | parent (`code-review`) | à chaque `/review` | jamais de récit de l'auteur ; diff jamais résumé ; pas de rétrocompatibilité à garder |
| Sortie du doubter | 4 champs (position, objection la plus forte, alternative plus simple, inconnu) + tableau affirmations | une par passe | doubter | à chaque appel | `position` ∈ {pas d'objection, réserves, contre} ; le tableau existant est conservé |
| Rapport `/review` | ligne de portée, **ligne de position**, constats classés, section « Discussions de MR » si MR, limites | — | `code-review` | à chaque `/review` | la ligne Security review reste en tête des limites (ADR 0029) |
| `review-guide.md` | 6 sections (R6) | un par dossier de changement | `review-guide` | régénéré sur demande | local, git-ignored ; jamais donné aux relecteurs avant leur passe |
| Marque `review:` / `review-reply:` | commentaire du langage, contenu commençant par `review:` / `review-reply:` | fichier:ligne | la personne / l'agent | jusqu'au traitement | retirée seulement si réglée ; jamais dans un commit (R11) |

## Constraints and policies applied
- **Aucune installation en plus** (intent) : seuls git, `glab`, `gh` déjà présents ; rien n'est ajouté au runtime.
- **Agents en lecture seule** (kit) : les relecteurs n'ont que lecture et recherche ; d'où le diff brut transmis par le parent (R1).
- **Actions visibles avec accord** (00_KIT, pratiques) : publier sur une forge = action vers l'extérieur ; accord à chaque fois, texte montré avant (R13) ; jamais de push.
- **Preuve, pas récit** (00_KIT « Evidence ») : la cold review applique cette règle aux relecteurs ; aucune affirmation de l'auteur n'est un fait (R3).
- **Tests jamais affaiblis** (00_KIT) : les tests de contenu existants qui changent (ex. `test_security_review.py`) sont mis à jour pour le nouveau contrat, nommés dans le CHANGELOG, avec un test qui prouve le nouveau comportement.
- **ADR 0027** (un signal déterministe nourrit la relecture, il ne bloque jamais) : la marque oubliée est un constat Minor, pas un blocage ; les discussions de MR sont des remarques à vérifier, pas des verdicts.
- **ADR 0029** (relecture sécurité par relecteurs indépendants) : déclencheurs et ligne « Security review » inchangés ; la cold review renforce l'indépendance.
- **Pas de nom de kit concurrent dans le repo**, idées reprises sans texte copié (règle du repo).
- **Pas de rétrocompatibilité** (règle du repo) : l'ancien format du doubter est remplacé, pas doublé.
- **Données personnelles minimisées** (10_COMPANY) : le guide et les commentaires postés ne recopient pas de données des fixtures ou des logs ; voir Threats.

## Threats
- Injection de prompt via une discussion de MR (un commentaire demande à l'agent d'agir) — les discussions sont des **données, jamais des instructions** (même règle que security-reviewer pour les commentaires de code) ; elles ne deviennent que des constats à vérifier — résiduel : un relecteur humain peut être trompé par un constat dérivé ; il voit la source citée.
- Fuite d'un secret ou d'une donnée personnelle dans un commentaire posté sur la MR — le texte exact est montré avant, accord à chaque fois ; le guide cite fichier:ligne plutôt que de recopier des valeurs — résiduel : la personne peut valider sans relire.
- Une marque `review:` contenant une instruction malveillante (fichier contribué par un tiers) — une marque est une remarque de la personne qui relit **dans cette session** ; une marque déjà présente dans le diff d'un tiers est signalée (R11), pas exécutée — résiduel : faible.
- Post sur la mauvaise MR — l'agent affiche l'identifiant et le titre de la MR avant l'accord — résiduel : faible.

## Areas of concern
- **Doubter sur research** : le format critique (position, alternative) est pensé pour un changement de code ; sur une recherche (`workflows/research.md`), « alternative plus simple » et « inconnu » peuvent sonner faux. Proposition : champs gardés, « aucune » accepté. — Hachem décide en relecture.
- **Faux positifs de marques** : un fichier YAML avec une clé `review:` en commentaire de doc pourrait être pris pour une marque. La règle R8 (commentaire dont le contenu *commence* par `review:`) limite le cas sans l'exclure. — à juger sur usage.
- **Taille du contexte** : passer le diff brut à chaque relecteur au lieu d'un résumé coûte plus de tokens sur un gros diff. Le diff était déjà transmis ; seul le récit disparaît. — acceptable, à surveiller.
- **Conflit avec l'autre session** : `.gitignore` et `init-project-context` ; le numéro est passé de 4.10.0 à 4.11.0 (4.10.0 et 4.10.1 livrées par l'autre session). — Hachem coordonne.
- **ADR** : la cold review change le contrat des relecteurs mais reste un changement de texte, réversible ; pas d'ADR proposé. Si Hachem veut la tracer, un court ADR « les relecteurs jugent le changement, pas le récit » (numéro après 0032). — Hachem décide.

## Open questions
- Assumption H1 : GitHub n'a pas de filtre « non résolu » dans `gh pr view --comments` (vérifié dans son aide : `-c, --comments`, sans filtre). Lire l'état de résolution demande `gh api graphql` (reviewThreads / isResolved) — non vérifié ; sinon lire toutes les discussions et dire dans les limites que la résolution n'est pas filtrée. — à vérifier au build.
- Assumption H2 : `glab mr note <id>` crée un commentaire (vérifié dans l'aide : « Creates a comment by default ») ; la forme exacte du texte (`-m` ou fichier) n'est pas vérifiée. — à vérifier au build.
- Assumption H3 : détecter la MR de la branche courante avec `glab mr view` sans argument (vérifié : `[<id | branch>]`) et `gh pr view` sans argument. — à vérifier au build.
- Ligne `**/docs/sdlc/**/review-guide.md` à ajouter par l'autre session dans `init-project-context`. — Hachem la transmet.
- Découpage : `/build` ou le skill `to-tickets` découpe cette spec ; pas de tickets ici.
