# Outils

Des utilitaires indépendants du flux, utilisables à tout moment. Un outil = une commande, un skill dessous, une fiche ici. Un outil sans fiche n’entre pas dans le noyau.

Chaque fiche suit le même gabarit : quand, commande, produit, demande, skill, exemple.

## `/guide` — par quoi commencer
- **Quand** : on hésite sur la commande, l’outil ou le niveau de cérémonie. **Pas** pour lancer le travail.
- **Commande** : `/guide <question>`.
- **Produit** : une réponse courte dans la langue de la personne, avec un exemple de prompt.
- **Demande** : rien.
- **Skill** : `guide` (interne). `workflow-guide` en option pour la carte complète du flux amont.
- **Exemple** : `/guide je dois changer la définition d’un KPI, je commence où ?`

## `/learn` — apprendre un périmètre ou un concept
- **Quand** : nouvel arrivant sur un périmètre, montée en compétence sur un sujet, sur plusieurs sessions. **Pas** pour une question ponctuelle (`/explain`).
- **Commande** : `/learn <sujet>`.
- **Produit** : dans le repo, `docs/learn/<sujet>/` avec leçons HTML courtes, quiz, fiches de référence imprimables, composants partagés ; hors repo, `~/.ai-kit/learning/<sujet>/` avec mission, notes et journal d’apprentissage. Les termes métier vont dans le `GLOSSARY.md` du repo.
- **Demande** : accès au repo et à ses docs ; accès web utile pour les sources.
- **Skill** : `teach`. Playbook `perimeter-brief` pour un périmètre Data quand il est installé.
- **Exemple** : `/learn le périmètre facturation : sources, modèles, KPI, règles de dates`.

## `/explain` — carte ou reformulation
- **Quand** : zone de code ou flux de données inconnu ; ou la dernière réponse n’a pas été comprise.
- **Commande** : `/explain <zone>` ou `/explain` seul après une réponse obscure.
- **Produit** : une carte un niveau au-dessus (modules, modèles, appelants, dépendances) dans les termes du glossaire, ou une reformulation simple ; proposition d’enregistrer une fiche dans `docs/learn/`.
- **Demande** : `GLOSSARY.md` de préférence.
- **Skills** : `zoom-out`, `wait-what`.
- **Exemple** : `/explain le parcours de la table commandes jusqu’au mart ventes`.

## `/ask` — questionnaire pour un propriétaire métier
- **Quand** : l’information n’est ni dans le code ni dans l’équipe. Option pour les deux profils : `"extra_commands": ["ask"]` dans `overrides.json`, puis `update`.
- **Commande** : `/ask <destinataire et décision à débloquer>`.
- **Produit** : un fichier questionnaire, une idée par question, réponse à compléter sous chacune ; les réponses alimentent `/intent`, `spec.md` ou le glossaire.
- **Demande** : rien.
- **Skill** : `to-questionnaire`.
- **Exemple** : `/ask au responsable produit : définition de « client actif » pour le KPI de rétention`.

## `/retro` — améliorer l’environnement de l’agent
- **Quand** : fin de session, surtout si elle a dérapé.
- **Commande** : `/retro` ou `/retro <chemin du journal>` après un `/clear`.
- **Produit** : propositions à accepter une par une : lignes pour `AGENTS.md`, checks à automatiser, standards pour `REVIEW.md`, skills à ajouter ou retirer, commandes manquantes.
- **Demande** : la session courante.
- **Skill** : `retro`.
- **Exemple** : `/retro`.

## `/handoff` — passation (option)
- **Quand** : changer de session, de dossier, de personne ou confier une tâche latérale.
- **Commande** : `/handoff [destination]`.
- **Produit** : un fichier de passation, `docs/sdlc/handoff-<date>.md` ou l’emplacement que le repo réserve à ces notes (note locale, non commitée sauf demande) : objectif, état, décisions et raisons, questions ouvertes, prochaines étapes exactes.
- **Skill** : `handoff`.

## `/research` — sources primaires (option)
- **Quand** : un fait de documentation ou d’API à établir, lecture longue à déléguer.
- **Commande** : `/research <question>`.
- **Produit** : `docs/research/<sujet>.md` avec chaque affirmation sourcée.
- **Demande** : sous-agents de préférence, accès web.
- **Skill** : `research`.

## `/wizard` — étapes humaines (option)
- **Quand** : identifiants, consoles tierces, approbations, migration unique. **Pas** si l’agent peut faire l’étape lui-même.
- **Commande** : `/wizard <procédure>`.
- **Produit** : un script bash interactif. Sur Windows, le kit demande au modèle de donner l’équivalent PowerShell ou les étapes manuelles.
- **Skill** : `wizard`.

## `/audit` — santé du code (option, développeurs)
- **Quand** : un moment libre pour rendre le code plus facile à opérer par un agent.
- **Commande** : `/audit [dossier]`.
- **Produit** : rapport HTML dans le dossier temporaire, recommandation prioritaire, idée à reprendre par `/intent`.
- **Demande** : sous-agents de préférence.
- **Skill** : `improve-codebase-architecture`.

## `/friction` — noter ce qui a coincé
- **Quand** : quelque chose a ralenti, surpris ou obligé à contourner le kit : une commande qui ne fait pas ce que dit sa description, un skill qui se déclenche pour rien, un garde-fou gênant, une page fausse, un outil manquant. Tout de suite, en une phrase, sans quitter le travail.
- **Commande** : `/friction <une phrase>` ou `/friction` seul, l’agent demande.
- **Produit** : une ligne (date, catégorie, commande en cours, phrase, plus la version du kit, le profil, la CLI et le système, ajoutés automatiquement) ajoutée à `~/.ai-kit/frictions.jsonl`, sur le poste seulement.
- **Ce qui se note sans vous** : un échec de `doctor --live` (authentification, quota, modèle) devient une ligne `auth` d'office ; le relevé d'usage compte aussi, dans les journaux, les commandes inconnues tapées et les demandes répétées dans une même session. L'agent, lui, vous propose `/friction` quand vous le corrigez, quand une vérification est rouge après « c'est fait », quand vous abandonnez ou reposez la même demande, quand il contourne un skill ou un garde-fou, ou quand la cérémonie était disproportionnée ; il n'écrit rien sans vous, sauf si vous avez mis `"frictions": "auto"` dans `overrides.json` (`"off"` coupe ces propositions). `/retro` propose aussi de noter ce qu'il trouve sur le kit. Rien n’est envoyé. Le relevé d’usage les compte ; `usage --json` les exporte quand la personne choisit de partager ; `scripts/usage-aggregate.py` les regroupe pour la [revue d’usage](usage-review.md), qui en fait des tickets.
- **Demande** : Python (le script `~/.ai-kit/bin/friction.py` est installé par le kit) ; dans agy, une permission d’exécution la première fois.
- **Skill** : aucun ; la commande suffit.
- **Exemple** : `/friction /test a relancé toute la suite alors que je voulais un seul modèle`.

## Activer un outil marqué « option »

Une ligne dans `~/.ai-kit/overrides.json`, puis `update` : `{"extra_commands": ["handoff", "research"]}`. La commande et ses skills sont installés ; `disabled_commands` fait l’inverse. Voir [personnalisation](customization.md).

## Ajouter un outil
Un dossier de skill, une entrée dans `skills/catalog.json` avec `category: tool`, un fichier `commands/<nom>.md` au [format pivot](format.md), une fiche ici, un cas dans `evals/cases/`.
