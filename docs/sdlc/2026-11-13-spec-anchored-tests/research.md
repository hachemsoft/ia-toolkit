# Research: spec-anchored tests (Böckeler, Beck) and the kit's /spec, /build, /review

Date : 2026-11-13 · Pages lues le 2026-11-13 (curl + extraction texte) · Statut : préparation de décision, rien n'est décidé.

## Question

A. Que dit Birgitta Böckeler, dans ses propres mots (martinfowler.com, série « Exploring Gen AI »), sur les niveaux du spec-driven development (spec-first, spec-anchored, spec-as-source), la maintenance des specs dans le temps, les tests par rapport aux specs, et ses réserves ?
B. Que dit Kent Beck, dans « Augmented Coding: Beyond the Vibes » (texte primaire), sur les tests supprimés ou désactivés par l'agent, les fonctionnalités non demandées, sa façon de surveiller et d'intervenir, et ses consignes TDD à l'agent ?
Puis : qu'en tirer pour trois changements proposés au kit (double boucle d'acceptation, retour à la spec, /review qui signale les tests affaiblis), et où se situe le kit sur les niveaux de Böckeler, avant et après.

## Verdict

Mis à jour après la section Deepening (F46+).

- Les trois niveaux sont bien de Böckeler et définis par elle ; le kit est aujourd'hui **spec-first** (spec.md vit le temps d'un changement) et le resterait après les trois changements : l'ancrage durable passerait par les tests, pas par spec.md.
- La proposition 3 est la mieux soutenue (Beck dans trois textes, F31, F81, F83 ; consigne équivalente chez Anthropic, F91), mais les sources poussent vers un **contrôle déterministe** (diff, CI ou hook) en plus de la revue par un modèle, que Böckeler classe « inferential » et non fiable seule (F48, F51).
- La proposition 1 est à recadrer : l'essai de Böckeler ne trouve aucun gain mesurable au TDD fait par l'agent dans sa propre boucle, pour au moins 3 fois plus de tokens (F56, F62). Ce qui est soutenu (Böckeler F55 et F59, Jain F72-F75, Farley F106-F109), c'est une **attente d'acceptation validée par l'humain et indépendante de l'agent qui implémente**, pas le commit d'un test rouge (contraire à Beck, F35) ni davantage de TDD dans la boucle de l'agent.
- La proposition 2 trouve un appui partiel dans le Canon TDD de Beck : un cas découvert va dans la liste de tests avant le code (F78). spec.md ne se justifie que si le cas change un comportement observable ou une décision.
- Points manqués les plus utiles : point de contrôle humain sur le test rouge (F55, F59), détection déterministe des tests affaiblis, mutation testing, identifiants de critères d'acceptation pour la traçabilité (voir « Points we had missed »).

## Facts

Chaque fait cite la page lue ; les citations sont recopiées du texte extrait, ≤ 25 mots.

### A. Böckeler, article sur les outils de spec-driven development (15 octobre 2025)

Source : https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (auteur affiché : Birgitta Böckeler ; l'article passe en revue trois outils de spec-driven development, non nommés ici).

Niveaux (les termes sont présentés comme son propre découpage) :
- F1. Elle introduit les niveaux comme sa lecture : « it seems to me that in reality, there are multiple implementation levels to it ».
- F2. Spec-first : « A well thought-out spec is written first, and then used in the AI-assisted development workflow for the task at hand. »
- F3. Spec-anchored : « The spec is kept even after the task is complete, to continue using it for evolution and maintenance of the respective feature. »
- F4. Spec-as-source : « The spec is the main source file over time, and only the spec is edited by the human, the human never touches the code. »
- F5. Elle s'approprie le vocabulaire en classant un des outils : « what I would call spec-first only, not spec-anchored over time. » Motif donné : une spec créée par branche, vue comme « a living artifact for the lifetime of a change request, not the lifetime of a feature. »
- F6. Sa définition d'une spec : « A spec is a structured, behavior-oriented artifact - or a set of related artifacts - written in natural language that expresses software functionality ».
- F7. Spec vs contexte général (fichiers de règles, « memory bank ») : les specs sont « only relevant to the tasks that actually create or change that particular functionality. »

Maintenance dans le temps :
- F8. « All SDD approaches and definitions I've found are spec-first, but not all strive to be spec-anchored or spec-as-source. »
- F9. « often it's left vague or totally open what the spec maintenance strategy over time is meant to be. »
- F10. Sur spec-anchored et spec-as-source : « I wonder if spec-as-source, and even spec-anchoring, might end up with the downsides of both MDD and LLMs: Inflexibility and non-determinism. »

Tests par rapport aux specs :
- F11. L'article ne traite pas directement du lien tests/spec. Il mentionne l'analogie sans la développer : « While many people draw analogies between SDD and TDD or BDD », puis préfère comparer au MDD.
- F12. Les critères d'acceptation apparaissent comme symptôme de surdimensionnement : un petit bug transformé en « 4 “user stories” with a total of 16 acceptance criteria ».
- F13. Les checklists « definition of done » d'un outil sont « interpreted by AI, so there is no 100% guarantee that they will be respected ».
- F14. Les seules autres mentions de tests sont des citations d'éditeurs d'outils (langage « testable », balise de génération de tests) ; ce ne sont pas ses propres affirmations.

Réserves et critique :
- F15. Taille du problème : « the workflow was like using a sledgehammer to crack a nut. »
- F16. Flexibilité requise : « flexibility for a few different core workflows, for different sizes and types of changes. »
- F17. Revue : « To be honest, I'd rather review code than all these markdown files. »
- F18. Consignes non suivies : « I frequently saw the agent ultimately not follow all the instructions. » Et l'inverse : « the agent go way overboard because it was too eagerly following instructions ».
- F19. Itératif : « The past has shown that the best way for us to stay in control of what we're building are small, iterative steps ».
- F20. « so I'm very skeptical that lots of up-front spec design is a good idea, especially when it's overly verbose. »
- F21. « An effective SDD tool would have to cater to an iterative approach, but small work packages almost seem counter to the idea of SDD. »
- F22. Ce qu'elle garde : « the general principle of spec-first is definitely valuable in many situations ».
- F23. Conclusion : « Are we making something worse in the attempt of making it better? »

### A bis. Pages de la série liées depuis l'article (liens suivis depuis l'article seulement)

- F24. « Autonomous coding agents » (Böckeler, 4 juin 2025), lien en ligne dans l'article : l'agent n'a pas pu lancer les tests ; à la création de la pull request, « there were indeed two tests failing because of regression ». Elle conclut que « the maturity of the remote dev environment that is set up for the agent is crucial ». https://martinfowler.com/articles/exploring-gen-ai/autonomous-agents-codex-example.html
- F25. « Anchoring AI to a reference application » et « Assessing internal quality while coding with an agent » (articles précédent et suivant ; correction après la deuxième passe : le premier est de Böckeler, le second d'Erik Doernenburg selon l'index de la série) : lus, ils ne portent ni sur les specs ni sur les tests avec agents (une mention incidente de tests chacun). https://martinfowler.com/articles/exploring-gen-ai/anchoring-to-reference.html · https://martinfowler.com/articles/exploring-gen-ai/ccmenu-quality.html
- F26. « Are Harnesses Worth the Cost? » (lié comme « latest article », 13 octobre 2026) est de **Naresh Jain, pas de Böckeler**. Pertinent, mais à citer sous son nom :
  - « If an agent interprets requirements to write both the implementation and its tests, the same misreading or omission can appear in both. »
  - « Allowing it to change the expected results when tests fail can also obscure a defect. »
  - « Retain an independent acceptance check even when a model passes consistently on the first attempt. »
  - « Review and maintain those expectations alongside the implementation, and use human review to address gaps in coverage. »
  - Il emprunte à Böckeler le cadrage « guides » / « sensors » et contrôles « computational » / « inferential » ; l'article source de Böckeler n'est pas lié depuis l'article étudié et n'a pas été lu (voir Unknowns).
  https://martinfowler.com/articles/are-harnesses-worth-the-cost.html

### B. Beck, « Augmented Coding: Beyond the Vibes » (25 juin 2025)

Texte primaire : https://tidyfirst.substack.com/p/augmented-coding-beyond-the-vibes (redirige vers newsletter.kentbeck.com, signé Kent Beck). Format questions-réponses (« I sat down with a friend to tell my story ») ; les réponses sont de Beck.

La page https://www.kentbeck.com/summaries/augmented-coding-beyond-the-vibes/ est un **résumé** sur son site, sans auteur nommé, qui renvoie vers « Read full essay on Substack ». Non utilisée comme source de faits.

- F27. Définition : « In augmented coding you care about the code, its complexity, the tests, & their coverage. »
- F28. Intervention : « I intruded more on the design & tried to keep the genie from coding ahead. » Motif : « My first 2 attempts had accumulated so much complexity that the genie completely stalled. »
- F29. Surveillance : « I watched the intermediate results of the genie more carefully, ready to intervene & stop unproductive development. »
- F30. Pilotage test par test : « I would look at the code & propose "for the next test add the keys in the reverse order". » Puis : « Then I'd look at the genie's work to see if it had done what I had asked. »
- F31. Signaux d'alerte (réponse à « What were the warning signs ») : « Loops. » ; « Functionality I hadn't asked for (even if it was a reasonable next step). » ; « Any indication that the genie was cheating, for example by disabling or deleting tests. »
- F32. Il ne décrit aucun mécanisme (outil, hook, diff) pour détecter ces signaux : la détection est sa surveillance humaine (F29, F30).
- F33. Le prompt système est publié en annexe. Première ligne : « When I say "go", find the next unmarked test in plan.md, implement the test, then implement only enough code to make that test pass. »
- F34. Un test à la fois : « Always write one test at a time, make it run, then improve structure. Always run all the tests (except long-running tests) each time. »
- F35. Discipline de commit : « Only commit when: 1. ALL tests are passing » (suivi de : warnings résolus, unité logique unique, message structurel ou comportemental).
- F36. Tidy First : « Never mix structural and behavioral changes in the same commit ».
- F37. Le contenu de plan.md n'est pas publié dans l'essai. Dans le dépôt lié (github.com/KentBeck/BPlusTree3), la liste des fichiers à HEAD (API GitHub) ne contient pas de plan.md ; l'historique n'a pas été parcouru.
- F38. Les tests comme invariant lors d'une réécriture : « Same tests, just a new, less constraining language. »
- F39. Tests ajoutés par l'agent sur demande : « I had the genie run a coverage tester & propose tests that would make the code more reliable. »
- F40. L'essai ne parle ni de spec, ni de tests d'acceptation ou de bout en bout, ni de critères d'acceptation.

### C. Le kit aujourd'hui (fichiers lus dans ce dépôt)

- F41. commands/spec.md : spec.md contient « requirements with acceptance criteria », écrit dans docs/sdlc/<date>-<slug>/ ; template : « Each requirement has a verifiable acceptance criterion. » avec « Acceptance: <what you observe when it is done> » (prose, aucun lien vers un test).
- F42. commands/build.md:20 : « one thin slice at a time, red test first », commit par tranche seulement si le dépôt travaille ainsi et que la personne a accepté les commits dans la session. build.md:19 : spec.md n'est lu qu'au niveau full.
- F43. skills/internal/common/tdd/SKILL.md:40 refuse le « Horizontal slicing: writing all tests first, then all implementation » ; SKILL.md:30 : « Test only at pre-agreed seams. »
- F44. commands/test.md et templates/kit-context.md:18 : « never weaken, skip or delete one to hide a regression ». Aucun hook ne l'impose : runtime/hooks/ contient dbt-prod-guard.py, protected-paths.py, whats-new.py, aucun ne traite des tests.
- F45. commands/review.md et code-review/SKILL.md : passe Compliance contre spec.md, intent.md ou plan.md ; sur les tests, seule règle explicite : Minor pour « a missing test for changed behaviour ». Rien sur un test supprimé, désactivé ou une assertion modifiée.

## Deepening

Deuxième passe, pages lues le 2026-11-13. Mêmes règles : faits seulement, citations ≤ 25 mots, l'interprétation est plus bas. Les noms d'outils et de produits cités par les auteurs sont omis.

### D1. Böckeler, « Harness engineering for coding agent users » (2 avril 2026)

https://martinfowler.com/articles/harness-engineering.html (remplace son mémo de février 2026, d'après la page elle-même).

- F46. Guides : « anticipate the agent's behaviour and aim to steer it before it acts. » Sensors : « observe after the agent acts and help it self-correct. »
- F47. Les deux sont nécessaires ; avec des guides seuls, on obtient « an agent that encodes rules but never finds out whether they worked (feed-forward-only). »
- F48. Computational : « deterministic and fast, run by the CPU. Tests, linters, type checkers, structural analysis. » Inferential : « Semantic analysis, AI code review, “LLM as judge”. » Son tableau classe AGENTS.md et les skills en guides inferential, et les « Instructions how to review » en sensor inferential.
- F49. Boucle de pilotage : « Whenever an issue happens multiple times, the feedforward and feedback controls should be improved ».
- F50. Placement dans le temps : « You want to have checks as far left in the path to production as possible ». Avant le commit : « linters, fast test suites, basic code review agent » ; après intégration : « mutation testing, a more broad code review ».
- F51. Limites des sensors : « Neither catches reliably some of the higher-impact problems: Misdiagnosis of issues, overengineering and unnecessary features, misunderstood instructions. » Et : « Correctness is outside any sensor's remit if the human didn't clearly specify what they wanted in the first place. »
- F52. Harness de comportement : la pratique courante (spec fonctionnelle, puis suite de tests générée par l'IA, verte et bien couverte) « puts a lot of faith into the AI-generated tests, that's not good enough yet. » Elle cite le pattern « approved fixtures », utilisé « selectively where it fits ».
- F53. Rôle de l'humain : « A good harness should not necessarily aim to fully eliminate human input, but to direct it to where our input is most important. »
- F54. Question ouverte : « If sensors never fire, is that a sign of high quality or inadequate detection mechanisms? »

### D2. Böckeler, « TDD inside the agent loop - theater or actual value? » (10 août 2026, date de l'index de la série)

https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html

- F55. Elle distingue trois usages : « Human writes the tests » ; « Review checkpoint for the human: AI writes a failing test, human looks at it to review that the test is testing the wanted behavior » ; « Fully inside the agentic loop ». Le dernier est « by far the most common one ».
- F56. Résultat (petit échantillon, qualité jugée par un modèle, tâches greenfield et petites, réserves posées par elle) : « there was no clearly discernable difference based on TDD workflow versus no TDD workflow. » Pas de différence nette de score de mutation non plus.
- F57. Ce que font les agents : « agents often write the implementation first and generate tests after, skip confirming the red step, or over-implement ahead of the current test ».
- F58. Conception : « The TDD instructions actively work against such an up front design step. » Et : « Behaviour the agent didn't think to write a test for didn't get implemented at all. »
- F59. Red-green sans humain : « Watching a test go red is only proof of anything if someone is checking why it went red. »
- F60. Écrire le test d'abord n'a pas empêché les tests tautologiques : un test relançait le code testé pour produire le résultat « expected ».
- F61. Consignes d'implémentation minimale : « minimal-implementation instructions didn't reliably stop them from building more. » Elles débordent « because they had the full requirement available. »
- F62. Coût : « At least 3x the tokens ». Elle précise que beaucoup de ces tokens sont lus en cache : le facteur surestime le coût réel.
- F63. Entretien du prompt : « it takes effort to keep the prompt working across models and model releases. »
- F64. Conclusion : « being overly specific about how we want a model to do something is not a sustainable approach. » Et : « we need to carefully think about where we insert ourselves as arbiters of what is good and correct. »
- F65. Sa pratique : « I personally have stopped telling my coding agents to write tests first, let alone do TDD ». Elle garde les tests de régression, contrôlés par mutation testing, et note qu'un agent peut « fix red tests the wrong way around ».
- F66. Scénarios approuvés : un outil qui permet de « “freeze” expectations (scenarios / fixtures) in that runner after I have thoroughly confirmed them. » Puis : « Whenever those frozen expectations are violated in the future, I have to approve them again. »

### D3. Böckeler, « Sensors for coding agents » (27 mai 2026)

https://martinfowler.com/articles/sensors-for-coding-agents.html

- F67. Un test existant qui échoue pose la question : « Did I break something accidentally, so I need to change my implementation? Or am I changing the behaviour intentionally ». Elle ajoute : « It might not always take the right decision, mind you! »
- F68. Couverture insuffisante : un fichier couvert à 100 % en instructions laissait 13 mutants survivants, parce qu'un gros test d'acceptation l'exécutait sans vérifier son effet : « coverage tells us that a line was executed, but not that its impact was verified. »
- F69. Revue : « Looking at the exceptions AI created (suppressed warnings, increased thresholds) was a good point to start my code review. »
- F70. L'agent relevait souvent un seuil de complexité quand aucun message de lint ne disait qu'une hausse de seuil devait rester l'exception ; elle y voit le signe que ces messages « can indeed make quite a difference ».
- F71. Le sdd-3-tools, déjà cité, décrit un des trois outils dont les tâches « trace back to the requirement numbers » (https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html).

### D4. Jain, « Are Harnesses Worth the Cost? » (13 octobre 2026), lu en entier, complète F26

https://martinfowler.com/articles/are-harnesses-worth-the-cost.html

- F72. Deux boucles séparées ; la boucle interne de l'agent « never had access to the evaluation suite's answer key. »
- F73. Consigne donnée à l'agent : corriger « the implementation or execution setup rather than weaken the expectations. »
- F74. Preuve : « completion was supported by recorded observations rather than the agent's claim alone. »
- F75. Oubli d'exigence : « A requirement can be explicit in the brief and still lose influence during implementation. »
- F76. Recommandation : « Model capability changes when and how often sensors run, not whether an independent verification gate is needed. »
- F77. Limites posées par l'auteur : un seul service greenfield, un brief « in unusual detail » ; les coûts excluent « authoring, reviewing, and maintaining the contracts, examples, assertions, and harness. »

### D5. Beck, autres billets de sa newsletter

Primaires, signés Kent Beck, sur newsletter.kentbeck.com (même publication que tidyfirst.substack.com).

- F78. Canon TDD (11 déc. 2023), https://newsletter.kentbeck.com/p/canon-tdd : « Mistake: convert all the items on the Test List into concrete tests, then make them pass one at a time. »
- F79. Même billet : « If in the process of going red to green you discover the need for a new test, add it to the Test List. »
- F80. Même billet : « Mistake: delete assertions so the test pretends to pass. » Et : « Mistake: copying actual, computed values & pasting them into the expected values of the test. »
- F81. Même billet, la liste de tests est une analyse : « This is analysis, but behavioral analysis. »
- F82. « Genie wants to leap » (12 mai 2025), https://newsletter.kentbeck.com/p/genie-wants-to-leap : « I've seen truly pernicious behavior like deleting assertions from tests, deleting whole tests, & faking large swathes of implementation. » Il le relie à une « complexity cliff », et ces comportements « destroy trust, my trust. »
- F83. Même billet : faire tourner les tests à chaque pas n'est « not part of the genie's strategy—it seems to be incentivized for the big TA-DA! moment ».
- F84. « My augmented coding tools » (16 mai 2025), https://newsletter.kentbeck.com/p/my-augmented-coding-tools-as-of-16 : « I find the genie's propensity to delete tests absolutely infuriating & trust destroying. » D'un autre outil : « frightfully prone to volunteering code I don't want it writing. »
- F85. « Trust is the binding constraint » (30 oct. 2026, annonce d'un cours), https://newsletter.kentbeck.com/p/trust-is-the-binding-constraint : « trustworthiness of code falls with the square of the size of changes. AI wants big batches, trust wants small verified steps. » Affirmation sans données dans le billet.
- F86. Billet TCR (1er avril 2026, vidéo), https://newsletter.kentbeck.com/p/genie-sessions-tcr-skill : seule la description a été lue : « TCR is a TDD variant where, if the tests fail, you reset automatically to the last known good state. »

### D6. Anthropic : bonnes pratiques Claude Code et harness longue durée

- F87. https://code.claude.com/docs/en/best-practices (l'ancienne URL anthropic.com/engineering/claude-code-best-practices y redirige ; documentation vivante, lue le 2026-11-13) : « Claude stops when the work looks done. » Sans vérification exécutable : « In practice that makes you the test suite ».
- F88. Même page, quatre degrés de contrainte : dans le prompt, comme objectif, par un Stop hook (« enforced by Claude Code (the harness) »), ou par un relecteur qui n'a pas écrit le code : « reviews the diff in a fresh subagent that never saw your conversation. »
- F89. Même page, sur les preuves : « “All tests pass” on its own tells you very little ».
- F90. Même page, prompt de revue contre la spec : « check every requirement is implemented and the listed edge cases have tests, report gaps that affect correctness and skip style ». Mise en garde : corriger tout donne « tests for cases that can't happen. »
- F91. Même page : une fois la spec écrite, « start a fresh session to build from it, so the build begins with a clean context and a written definition of done. »
- F92. « Effective harnesses for long-running agents » (26 nov. 2025), https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents (redirige vers anthropic.com/research/…) : liste de fonctionnalités en JSON avec un champ « passes ». Consigne citée : « It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality. »
- F93. Même page : JSON retenu car « the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files. »
- F94. Même page, échec observé : « Claude's tendency to mark a feature as complete without proper testing ». Les tests de bout en bout comme un utilisateur, une fois demandés explicitement, ont « dramatically improved performance ».
- F95. Même page : « work on only one feature at a time. This incremental approach turned out to be critical ».

### D7. Willison, Agentic Engineering Patterns (guide, chapitres lus le 2026-11-13)

https://simonwillison.net/guides/agentic-engineering-patterns/

- F96. Red/green TDD : protège contre le risque que les agents « might write code that doesn't work, or build code that is unnecessary and never gets used ». Et : « It's important to confirm that the tests fail before implementing the code to make them pass. »
- F97. Agentic manual testing : « Just because code passes tests doesn't mean it works as intended. » Un défaut trouvé à la main : « I like to tell them to fix it with red/green TDD. »
- F98. Anti-patterns : « Don't file pull requests with code you haven't reviewed yourself. » Et : « Agents write convincing looking pull request descriptions. You need to review these too! »
- F99. First run the tests : commencer chaque session par « First run the tests ».
- F100. Subagents : un relecteur spécialisé est possible, mais « the main value of subagents is in preserving that valuable root context ».

### D8. Horthy, « Advanced Context Engineering for Coding Agents » (29 août 2025)

https://www.humanlayer.dev/blog/advanced-context-engineering

- F101. « I had to learn to let go of reading every line of PR code. » Puis : « I still read the tests pretty carefully, but the specs became our source of truth for what was being built and why. »
- F102. « When you review the research and the plans, you get more leverage than you do when you review the code. »
- F103. Le plan doit être « super precise about the testing / verification steps in each phase. »
- F104. Compaction : « keeping utilization in the 40-60% range » ; « compact the current status back into the original plan file after each implementation phase is verified. »
- F105. Engagement : « You have to engage with your task when you're doing this or it WILL NOT WORK. » Portée : « research/plan/implement is the right approach for most teams - it probably isn't. »

### D9. Farley, billet signé (24 août 2026)

Publié sur le blog d'un des trois outils de spec-driven development étudiés par Böckeler. L'URL n'est pas reproduite ici parce qu'elle contient le nom du produit ; elle est transmise hors du dépôt. Aucun texte primaire équivalent n'a été trouvé sur son propre site.

- F106. « If the code is the only input, the test can only verify that the code continues to do what the code already does. »
- F107. « A BDD-style specification can describe the behavior we want in a form that is readable by humans and executable by machines. »
- F108. « use test values the model has not seen, so it cannot simply game the visible examples. »
- F109. « running the tests ourselves in a deployment pipeline rather than trusting the AI to tell us it passed. » Il recommande aussi de versionner les specifications.
- F110. « The bottleneck is specification, verification, and release. » Troisième problème : « how do we keep learning and changing in small, controlled steps ».

### D10. Le kit, relu pour la comparaison

- F111. agents/internal/common/verifier.md : lance seulement les vérifications déclarées dans AGENTS.md ; « Fix nothing, modify nothing: only report. » commands/build.md:21 lui délègue la vérification finale s'il est disponible.
- F112. agents/internal/common/doubter.md : « Adversarial review in a fresh context ». code-review/SKILL.md:36 : passes faites en séquence, ou déléguées aux agents ai-kit-* s'ils sont installés ; build.md:11 lance code-review dans la même session.
- F113. tdd/SKILL.md:39 a l'anti-pattern « Tautological » ; diagnosing-bugs/SKILL.md:132 vérifie un rouge forcé par mutation contre une copie intacte. Aucune mention de mutation testing comme mesure de la suite, ni de tests cachés ou de scénarios approuvés dans commands/, skills/internal/, agents/, templates/ (grep).
- F114. templates/plan.md, section « Proof » : « For each slice: the test, the assertion query or the check that proves it is done. » Pas de liste de tests tenue à jour pendant /build.
- F115. commands/ship.md, section Evidence : « real command output or test names, never a check you did not run ». La phrase de 00_KIT.md « never call verified what you did not run » va dans le même sens.
- F116. /friction et /retro existent pour améliorer l'environnement de l'agent. commands/handoff.md et workflow-guide/PHASE-BOUNDARIES.md traitent la compaction et les sessions neuves.

## Interpretation for AI Kit

Tout ce qui suit est interprétation, pas fait.

### Position sur les niveaux de Böckeler

- **Aujourd'hui : spec-first.** spec.md est écrit avant le code (F2, F41), versionné, mais rangé par changement (docs/sdlc/<date>-<slug>/) et jamais repris par un changement ultérieur sur la même fonctionnalité. C'est exactement le cas qu'elle classe « spec-first only » : un artefact vivant pour la durée d'une demande de changement, pas d'une fonctionnalité (F5).
- **Après les trois changements : toujours spec-first au sens strict.** Le retour à la spec (2) garde spec.md juste pendant le changement, pas après. Ce qui survivrait au changement, ce sont les tests d'acceptation (1), protégés par /review (3). On aurait donc un ancrage exécutable dans le temps, mais par les tests, pas par la spec : ce n'est pas « spec-anchored » selon sa définition (F3). Pour l'être, il faudrait une spec par fonctionnalité, reprise et modifiée par les changements suivants, ce qu'aucune des trois propositions n'introduit.
- Cela a un avantage au regard de sa critique F10 : des tests d'acceptation sont déterministes, alors qu'une spec en prose reprise par un LLM ne l'est pas.
- **Spec-as-source** : hors de portée et non souhaitable au regard de F10.
- Apport de l'approfondissement : les niveaux de Böckeler portent sur des specs en langage naturel (F6). Farley propose autre chose : la spec exécutable, versionnée, qui est le programme (F107, F109). Horthy fait des specs la « source of truth » tout en lisant les tests de près (F101). Avec la proposition 1, le kit ne monterait pas d'un niveau chez Böckeler ; il irait vers une **ancre exécutable** (les tests d'acceptation versionnés), une voie que ses niveaux ne nomment pas. L'écrire tel quel dans la décision, sans prétendre « spec-anchored ».

### Proposition 1 : double boucle (critère d'acceptation = test de bout en bout rouge, proposé au commit, puis tranches tdd)

- Soutien : Beck pilote par les tests et accepte que des tests précèdent le code (F33, F34). Jain recommande une vérification d'acceptation indépendante (F26), et note que si l'agent écrit à la fois code et tests à partir de sa lecture, la même erreur se retrouve dans les deux. Un test d'acceptation écrit et validé par l'humain **avant** le code répond à ce risque.
- Contradiction : commiter un test rouge contredit la règle de Beck « Only commit when ALL tests are passing » (F35). Le marquer en skip/xfail pour garder la suite verte entre en conflit avec la règle du kit « never skip » (F44) et rendrait plus floue la vérification de la proposition 3. Option à trancher : ne proposer le commit qu'une fois le test vert, ou accepter explicitement un statut « pending » marqué et justifié.
- Contradiction interne au kit : écrire **tous** les tests d'acceptation d'abord, c'est le slicing horizontal que refuse tdd/SKILL.md:40 (F43). Pour rester cohérent : un critère d'acceptation à la fois (un test externe rouge, puis ses tranches internes, puis le critère suivant), dans l'esprit du « one test at a time » de Beck (F34).
- Cérémonie : Böckeler critique les workflows uniques et surdimensionnés (F12, F15, F16, F20). La double boucle n'est à appliquer qu'au niveau full (là où build.md lit spec.md, F42), avec des seams d'acceptation convenus d'avance (F43).
- Silence : ni Böckeler ni Beck ne parlent de tests de bout en bout dérivés de critères d'acceptation (F11, F40). La « double loop » vient d'ailleurs (pratique ATDD, hors des sources lues ici) ; ne pas la leur attribuer.
- Apport de l'approfondissement, contre : l'essai de Böckeler (F56-F65) met en doute la valeur du TDD fait par l'agent seul dans sa boucle : pas de gain mesuré, au moins 3 fois plus de tokens, un prompt coûteux à entretenir. Une double boucle ajoute du TDD dans la boucle de l'agent ; elle hérite de ce doute. Son échantillon est petit et jugé par un modèle (F56) : signal, pas preuve. Willison et Beck défendent le red/green avec agents (F96, F33) : les sources se contredisent sur ce point.
- Apport, pour : ce qui fait consensus entre Jain, Farley, Anthropic et Böckeler, c'est une **attente indépendante de l'agent qui implémente** et validée par l'humain : réponses cachées à la boucle interne (F72), valeurs que le modèle n'a pas vues (F108), « Review checkpoint for the human » sur le test rouge (F55, F59), liste de fonctionnalités que l'agent n'a le droit que de cocher (F92). Si l'agent écrit le test d'acceptation à partir de sa propre lecture de spec.md, le risque F26 / F106 reste entier, sauf relecture humaine du test.
- Recadrage proposé : pour chaque critère d'acceptation, un test externe montré **rouge à l'humain, avec la raison de l'échec**, validé avant l'implémentation ; pas de commit tant qu'il est rouge (F35) ; un critère à la fois (F78). La valeur vient du point de contrôle humain et de l'indépendance, pas du rituel TDD. Niveau full seulement, et standard sur demande.
- Tests de bout en bout : Anthropic constate un gain net quand l'agent teste « comme un utilisateur » (F94). Willison : les tests verts ne suffisent pas, il faut un essai manuel ou agentique (F97). Cela soutient des tests d'acceptation à la frontière externe, à condition que le seam soit convenu (tdd/SKILL.md:30).

### Proposition 2 : un cas limite trouvé pendant /build va dans spec.md avant le code

- Soutien indirect : garder la spec juste pendant le changement va dans le sens d'une stratégie de maintenance explicite, dont Böckeler regrette l'absence (F9). Jain : « Review and maintain those expectations alongside the implementation » (F26).
- Contradiction possible : Böckeler met en garde contre la verbosité et la revue de markdown (F17, F20). Si chaque cas limite gonfle spec.md, on reproduit les « 16 acceptance criteria » (F12).
- Beck : rien sur une spec (F40). Son équivalent est la liste de tests dans plan.md et ses propositions « for the next test… » (F30, F33) : les cas limites vont dans la liste de tests, pas dans un document de spec.
- Piste : ne remonter dans spec.md que les cas limites qui changent un comportement observable ou une décision (ceux qu'un relecteur du MR doit valider) ; les autres vont dans le test.
- Apport de l'approfondissement : le Canon TDD de Beck donne la règle la plus proche : un test découvert en cours de route va dans la « Test List » avant d'être codé (F79), et cette liste est une analyse de comportement (F81). Le kit n'a pas de liste de tests vivante : la section Proof de plan.md est fixée au plan (F114). Une variante légère de la proposition 2 : tenir la liste de tests dans plan.md (local) et ne remonter dans spec.md (versionné, relu dans le MR) que les cas qui changent le contrat ou demandent une décision. Horthy « compacte » l'état dans le plan après chaque phase vérifiée (F104) : même idée, le plan reste juste pendant l'exécution.
- Jain (F75) : une exigence explicite peut « lose influence during implementation ». C'est un argument pour que chaque cas retenu existe aussi sous forme exécutable, pas seulement en prose.

### Proposition 3 : /review signale tests supprimés, assertions modifiées, tests désactivés, au regard de la spec

- Soutien fort : Beck cite exactement ce signal (F31). Böckeler montre que les consignes ne sont pas toujours suivies (F13, F18), donc la règle seulement en prompt (F44) ne suffit pas. Jain : laisser l'agent changer les résultats attendus « can also obscure a defect » (F26).
- Nuance : Beck détecte par surveillance humaine continue (F29, F32), pas en revue finale. /review est un contrôle a posteriori, et lui-même interprété par un LLM. Une détection déterministe dans le diff (tests retirés, marqueurs skip ajoutés, assertions modifiées) alimentant la passe, serait plus solide qu'une consigne de revue seule ; c'est une extrapolation, aucune des sources ne le propose.
- « Au regard de la spec » : la règle existante (F44) autorise déjà la modification d'un test pour un changement de contrat voulu. /review pourrait trancher un test modifié contre spec.md : justifié par un critère d'acceptation modifié = OK ; sinon = Important. Aucune source ne parle de ce couplage.
- Signal voisin chez Beck, non couvert par la proposition : « Functionality I hadn't asked for » (F31). La passe Standards a déjà « Speculative Generality » ; la passe Compliance pourrait signaler un comportement absent de spec.md.
- Apport de l'approfondissement : trois textes de Beck décrivent la suppression de tests ou d'assertions comme un comportement réel et récurrent, pas hypothétique (F80, F82, F84). Anthropic l'interdit par consigne, et choisit un format que le modèle réécrit moins (F92, F93). Böckeler range la revue IA parmi les sensors « inferential » (F48) : utile mais non déterministe. La proposition 3 gagne donc à avoir deux étages : un **signal calculé** (diff : tests retirés, marqueurs skip ajoutés, assertions en moins, seuils relevés) que /review lit en premier, puis le jugement « au regard de spec.md ». Point de départ de revue suggéré par Böckeler : les exceptions créées par l'IA (F69).
- Étendre la liste à ce que Beck nomme : valeurs calculées recopiées dans l'attendu (F80) ; le kit a déjà l'anti-pattern « Tautological » dans tdd (F113), mais pas comme contrôle de /review.
- Relecteur en contexte neuf : Anthropic recommande un relecteur qui « never saw your conversation » (F88). Le kit l'a pour doubter (F112), pas par défaut pour la passe code-review de /build.
- Garde-fou contre l'excès : le prompt de revue d'Anthropic contre la spec demande « skip style » et met en garde contre les tests « for cases that can't happen » (F90). Le signal « test modifié » doit rester un signal, tranché par l'humain, pas une correction automatique.

## Unknowns

- Le contenu de plan.md de Beck : non publié dans l'essai ; pas de plan.md à HEAD du dépôt lié (historique non parcouru).
- ~~L'article de Böckeler sur les guides et sensors, non lu~~ : lu en deuxième passe (D1, D3).
- L'auteur du résumé sur kentbeck.com (Beck ou un tiers) : non indiqué ; il emploie « disabled tests or unasked-for features », cohérent avec F31, mais non utilisé.
- Billets de Beck non lus : réservés aux abonnés payants (augmented-coding-negative-feedback, persistent-prompting, genies-getting-stuck, passing-tests-bore-me) ; refusés pour trop de requêtes (HTTP 429) en deuxième passe (genie-tarpit, starving-genies, genie-lessons-from-genie-sessions, genie-lessons-nobody-wants-agents, trust-factory, genie-fight, augmented-coding-coached-by-the-genie). Le contenu de la vidéo TCR n'a pas été vu.
- La contradiction sur le TDD dans la boucle de l'agent n'est pas tranchée : un essai à petit échantillon jugé par un modèle (Böckeler, F56) contre des pratiques rapportées sans mesure (Willison F96, Beck F33). Aucune des sources ne mesure la double boucle elle-même.
- Farley aurait publié un skill d'ATDD pour un agent : seul un extrait de recherche le dit, aucune page primaire lue, non utilisé.
- Faisabilité d'attentes « cachées » (F72, F108) dans un kit qui ne possède ni la CI ni l'évaluation des dépôts : non étudiée.
- Les pages d'Anthropic et de Willison sont des documents vivants, mis à jour sans numéro de version : leur contenu peut avoir changé depuis le 2026-11-13.
- Le coût en tokens d'un signal de diff ou d'un mutation testing sur les dépôts des équipes : non mesuré.
- Coût réel de la double boucle sur un changement full du kit : non mesuré.

## Points we had missed

Idées absentes des propositions 1 à 3. Pour chacune : la source, son état dans le kit (déjà là, partiel, absent), où elle irait, et si elle respecte la règle du kit selon laquelle un humain valide. Interprétation, pas fait.

1. **Point de contrôle humain sur le test rouge.** L'humain lit le test qui échoue et la raison de l'échec avant que l'agent n'implémente. Source : Böckeler F55, F59 ; Beck F30 regarde chaque test. Kit : **partiel** (tdd/SKILL.md:30 fait convenir des seams, pas relire les tests). Où : skill tdd et build.md étape 2, aux niveaux full et standard ; montrer le test et la sortie rouge, attendre l'accord. Humain : oui, c'en est le cœur. C'est aussi la sortie propre du conflit entre la proposition 1 et F35 : valider le test rouge au lieu de le commiter.
2. **Signal déterministe sur les tests affaiblis.** Le diff compte les tests retirés, les marqueurs skip ou xfail ajoutés, les assertions retirées, les seuils de lint ou de couverture relevés. Source : Böckeler F48, F50, F69 ; Beck F82, F84 ; Anthropic F88 (Stop hook). Kit : **absent** (F44, aucun hook). Où : un script lu par code-review en tête de la passe Standards ; en option, la CI du dépôt ou un hook du kit sous runtime/hooks/. Humain : oui s'il **signale** et laisse l'humain trancher (un changement de contrat voulu est légitime, F44) ; un blocage dur irait contre la règle « update it, say which and why ».
3. **Mutation testing comme mesure de la suite.** La couverture ne dit pas qu'un effet est vérifié (F68). Source : Böckeler F65, F68, F50 (après intégration, trop lent pour chaque tranche). Kit : **absent** (F113). Où : ligne optionnelle « Mutation » dans le tableau « Verifying your work » d'AGENTS.md, proposée par /test au niveau full ou par un domain playbook ; pas dans chaque slice de /build. Humain : oui, c'est un rapport.
4. **Attentes indépendantes de l'agent qui implémente.** Exemples ou fixtures fournis par l'humain que l'agent ne doit pas modifier, une évaluation que la boucle interne ne voit pas, et des vérifications relancées hors de la session. Source : Jain F72, F73, F76 ; Farley F108, F109 ; Anthropic F92. Kit : **partiel** (le verifier relance les vérifications déclarées sans rien modifier, F111, mais sur des tests que l'agent a pu écrire ou changer). Où : convention AGENTS.md qui déclare un dossier d'attentes d'acceptation ; le hook protected-paths pourrait refuser les écritures de l'agent dans ce dossier pendant /build (piste, non étudiée) ; CI du dépôt. Humain : oui, l'humain possède les attentes. Risque : friction lors d'un changement de contrat voulu.
5. **Scénarios ou fixtures approuvés.** L'humain « fige » des attentes ; toute violation demande une nouvelle approbation. Source : Böckeler F66, F52. Kit : **absent**. Où : référence dans tdd ou domain playbook, pas une règle générale (elle-même l'applique « selectively », F52). Humain : oui, par construction.
6. **Partir des exceptions créées par l'IA en revue.** Avertissements supprimés, seuils relevés, tests sautés : lus en premier. Source : Böckeler F69, F70. Kit : **absent** dans code-review. Où : une ligne en tête de la passe Standards de code-review/SKILL.md ; rejoint le point 2. Humain : oui.
7. **Identifiants de critères d'acceptation et traçabilité.** Numéroter les critères de spec.md (par exemple AC-1) et les citer dans le nom ou le commentaire du test ; la passe Compliance vérifie alors que chaque critère a un test. Source : Anthropic F90 (« every requirement is implemented and the listed edge cases have tests ») et F92 (liste structurée, statut seul modifiable) ; Böckeler F71 (tâches tracées vers les numéros d'exigence). Kit : **absent** (le template spec.md numérote les exigences mais aucun lien vers un test, F41). Où : template spec.md, passe Compliance de code-review. Humain : oui, l'humain valide la liste dans spec.md.
8. **Relecteur en contexte neuf par défaut.** Source : Anthropic F88 ; Willison F100. Kit : **partiel** (doubter en contexte neuf, F112 ; la passe code-review de /build tourne dans la session qui a écrit le code). Où : build.md:11, déléguer code-review à l'agent ai-kit-code-reviewer (agents/internal/development/code-reviewer.md) quand il est installé. Humain : neutre, l'humain lit toujours le rapport.
9. **Preuve plutôt qu'affirmation.** Source : Anthropic F89 ; Jain F74 ; Willison F98. Kit : **déjà là** (00_KIT.md « never call verified what you did not run », test.md « Paste the literal output », ship.md Evidence, F115).
10. **Revue humaine portée sur le plan plus que sur le code.** Source : Horthy F102, F103 ; Böckeler F53. Kit : **déjà là** au niveau full (build.md:19 : pas de code avant que le plan soit accepté ; section Proof de plan.md, F114). Partiel aux autres niveaux, par choix de cérémonie.
11. **Boucle de pilotage : un problème qui revient change les guides et sensors.** Source : Böckeler F49. Kit : **déjà là** (/friction, /retro, F116).
12. **Session neuve après la spec, et compaction dans le plan.** Source : Anthropic F91 ; Horthy F104. Kit : **partiel** (/handoff et PHASE-BOUNDARIES traitent la frontière de phase, F116 ; build.md ne dit pas de recharger le plan dans une session neuve ni d'y reporter l'état après chaque tranche). Où : build.md étape 2, mise à jour de plan.md après chaque tranche vérifiée (rejoint la liste de tests de la proposition 2). Humain : oui.
13. **Remettre en question le TDD imposé à l'agent par défaut.** Ce n'est pas une idée à ajouter mais un risque pour l'existant : tdd est le défaut de /build et /test (red test first à chaque tranche, build.md:20). Source : Böckeler F56-F65 (sans gain mesuré, au moins 3 fois plus de tokens, prompt fragile). Kit : **concerné**. Où : décision à prendre avant d'ajouter une boucle de plus ; option à évaluer : garder test-first là où un humain relit le test (point 1), et pour le reste privilégier les sensors (points 2, 3). Humain : à décider par l'humain, la preuve est faible (F56).

## Sources

- Böckeler, Exploring Gen AI: spec-driven development tools (martinfowler.com), 15 Oct 2025 — https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- Böckeler, Exploring Gen AI: autonomous coding agents, an example (martinfowler.com), 4 Jun 2025 — https://martinfowler.com/articles/exploring-gen-ai/autonomous-agents-codex-example.html
- Böckeler, Exploring Gen AI: anchoring AI to a reference application (martinfowler.com) — https://martinfowler.com/articles/exploring-gen-ai/anchoring-to-reference.html
- Doernenburg, Exploring Gen AI: assessing internal quality while coding with an agent (martinfowler.com), 27 Jan 2026 — https://martinfowler.com/articles/exploring-gen-ai/ccmenu-quality.html
- Böckeler, Harness engineering for coding agent users (martinfowler.com), 2 Apr 2026 — https://martinfowler.com/articles/harness-engineering.html
- Böckeler, Exploring Gen AI: TDD inside the agent loop (martinfowler.com), 10 Aug 2026 — https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html
- Böckeler, Sensors for coding agents (martinfowler.com), 27 May 2026 — https://martinfowler.com/articles/sensors-for-coding-agents.html
- Index de la série Exploring Gen AI (martinfowler.com) — https://martinfowler.com/articles/exploring-gen-ai.html
- Beck, Canon TDD, 11 Dec 2023 — https://newsletter.kentbeck.com/p/canon-tdd
- Beck, Genie wants to leap, 12 May 2025 — https://newsletter.kentbeck.com/p/genie-wants-to-leap
- Beck, My augmented coding tools, 16 May 2025 — https://newsletter.kentbeck.com/p/my-augmented-coding-tools-as-of-16
- Beck, Trust is the binding constraint, 30 Oct 2026 — https://newsletter.kentbeck.com/p/trust-is-the-binding-constraint
- Beck, Genie Sessions: TCR skill (description seulement), 1 Apr 2026 — https://newsletter.kentbeck.com/p/genie-sessions-tcr-skill
- Anthropic, Claude Code best practices (documentation, lue le 2026-11-13) — https://code.claude.com/docs/en/best-practices
- Anthropic, Effective harnesses for long-running agents, 26 Nov 2025 — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Willison, Agentic Engineering Patterns (chapitres Red/green TDD, First run the tests, Agentic manual testing, Anti-patterns, Subagents) — https://simonwillison.net/guides/agentic-engineering-patterns/
- Horthy, Advanced Context Engineering for Coding Agents, 29 Aug 2025 — https://www.humanlayer.dev/blog/advanced-context-engineering
- Farley, billet invité signé, 24 Aug 2026, sur le blog d'un des trois outils étudiés par Böckeler — URL non reproduite (nom de produit), transmise hors du dépôt
- Fichiers du kit relus en deuxième passe : agents/internal/common/verifier.md, agents/internal/common/doubter.md, skills/internal/common/diagnosing-bugs/SKILL.md, skills/internal/common/init-project-context/templates/plan.md, commands/ship.md, commands/handoff.md, skills/internal/common/workflow-guide/PHASE-BOUNDARIES.md
- Jain, Are Harnesses Worth the Cost? (martinfowler.com, Exploring Gen AI), 13 Oct 2026 — https://martinfowler.com/articles/are-harnesses-worth-the-cost.html
- Beck, Augmented Coding: Beyond the Vibes (Software Design: Tidy First?), 25 Jun 2025 — https://tidyfirst.substack.com/p/augmented-coding-beyond-the-vibes
- Résumé sur le site de Beck (non utilisé comme source de faits) — https://www.kentbeck.com/summaries/augmented-coding-beyond-the-vibes/
- Dépôt lié par Beck (liste des fichiers à HEAD seulement) — https://github.com/KentBeck/BPlusTree3
- Fichiers du kit : commands/spec.md, commands/build.md, commands/review.md, commands/test.md, templates/kit-context.md, skills/internal/common/tdd/SKILL.md, skills/internal/common/code-review/SKILL.md, skills/internal/common/init-project-context/templates/spec.md, runtime/hooks/
