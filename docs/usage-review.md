# Revue d’usage

La revue d’usage est la procédure par laquelle une équipe fait maigrir le kit sur des faits plutôt que sur des avis. Le kit livre volontairement un noyau large au départ, parce qu’on ne sait pas encore ce qui servira ; la revue d’usage est le mécanisme qui corrige ce pari, régulièrement, à partir de ce que les gens tapent vraiment.

## Pourquoi c’est nécessaire

**Chaque skill installé a un coût permanent, même quand personne ne l’utilise.** Sa description est injectée dans le contexte de chaque prompt pour que le modèle sache qu’il existe (`doctor` affiche ce poids). Plus il y a de skills, plus le contexte est consommé avant même la question, et plus le modèle a de chances d’activer un skill à côté de la demande. Un noyau de vingt skills jamais activés fait payer cette taxe à chaque message de chaque personne.

**Chaque brique est un ticket de support potentiel.** Un skill qui se déclenche sans qu’on le veuille, une commande que personne ne comprend, un agent qui n’est jamais appelé : autant de choses à expliquer, documenter, tester et maintenir à chaque mise à jour des skills amont. Le kit existe pour réduire le support, pas pour l’alimenter.

**La cérémonie doit suivre les enjeux.** La règle du kit est de ne pas tout installer. Mais décider a priori de ce qu’un analyste ou un développeur utilisera est une supposition. Le relevé d’usage remplace la supposition par une mesure.

**Les commandes que personne ne tape sont un signal, pas un échec.** Si `/retro` n’est jamais tapé, la question n’est pas « faut-il le retirer » mais « `/guide` le propose-t-il, et la fiche est-elle claire ». La revue sert aussi à ça.

## Ce que la revue fait, et ne fait pas

| La revue peut | La revue ne fait jamais |
| --- | --- |
| passer un skill du noyau (`core`) en option (`optional`) : une ligne `extra_skills` le réactive pour qui le veut | supprimer un skill du dépôt ou d’un poste sans décision d’équipe |
| remplacer un skill amont dont l’équipe s’écarte par une version maison courte, même nom, même commande | renommer une commande ou changer un artefact (`intent.md`, `spec.md`, `plan.md`, `REVIEW.md`) : c’est le contrat avec l’équipe |
| corriger `/guide`, une fiche ou un prompt quand une commande n’est jamais tapée | toucher aux garde-fous : ils ne dépendent pas de la fréquence d’usage |
| raccourcir `00_KIT.md` et les gabarits | agir automatiquement : le relevé propose, des personnes décident |

Les playbooks Data et les skills de vocabulaire (`domain`, `reference`) ne sont jamais proposés au retrait : ils s’activent par la nature de la tâche, pas par la fréquence. Un playbook de revue de coût BigQuery sert deux fois par an et c’est très bien.

## Le relevé

```sh
python3 -m installer usage                           # fenêtre de 42 jours
python3 -m installer usage --since 90 --json releve.json
python3 -m installer usage --min-sessions 5 --min-prompts 20
```

Le relevé lit, localement et sans rien envoyer, les journaux de session que chaque CLI écrit déjà sur le poste (emplacements dans la [matrice](cli/matrice.md)). Sur la fenêtre, il compte :

- les commandes du kit tapées, par nom ;
- les skills activés par le modèle, quand la CLI les enregistre (voir sa page) ;
- les agents du kit appelés ;
- les erreurs ;
- les frictions notées avec `/friction` (`~/.ai-kit/frictions.jsonl` : date, catégorie, commande, une phrase), comptées par catégorie ;
- puis, par différence, les commandes, skills et agents installés qui n’ont jamais servi.

Il ne contient ni le texte des prompts, ni les noms de fichiers des repos, ni l’identité de la personne. Le JSON peut être partagé tel quel.

**Seuil de données.** En dessous de dix sessions et cinquante prompts sur la fenêtre (modifiable avec `--min-sessions` et `--min-prompts`), le relevé affiche les comptages mais ne recommande rien : trop peu de matière pour conclure. Au-dessus, il liste les candidats à passer en option : les skills du noyau de catégorie `workflow` ou `tool` jamais activés, et qui ne sont requis ni par une commande tapée, ni par un skill activé (les dépendances `requires` du catalogue sont suivies). Un skill jamais activé mais requis par `/intent`, lui-même tapé, n’est pas un candidat.

**Ce que le relevé ne mesure pas.** La qualité. Un skill activé une fois a pu éviter une journée de travail ; un skill activé vingt fois a pu gêner vingt fois. Le relevé dit « jamais », « rarement », « souvent » ; la revue dit « utile » ou « pas utile ». C’est pour cela que la revue reste humaine.

## À quoi ça ressemble

Sur un poste, après trois semaines :

```
$ python3 -m installer usage
Fenêtre : 42 jours | 14 sessions | 86 prompts | 2 erreurs
Commandes tapées : intent ×9, build ×7, test ×6, guide ×4, diagnose ×2, friction ×2
Skills activés : grill-with-docs ×9, implement ×7, tdd ×6, dbt-model-change ×5, sql-review ×2
Agents appelés : ai-kit-verifier ×5
Jamais utilisés : 2 commandes, 9 skills, 2 agents.
Frictions notées : 2 (docs ×1, command ×1) ; /friction pour en noter une.
Candidats à sortir du noyau (jamais activés, non requis par une commande utilisée) : retro
Procédure : docs/usage-review.md. Les journaux lus sont locaux ; rien n’est envoyé.
```

Chaque personne exporte (`usage --json prenom.json`) et partage si elle le veut ; l'équipe agrège :

```
$ python3 scripts/usage-aggregate.py releves/*.json
# Bilan d’usage agrégé

6 postes | 71 sessions | 412 prompts | 9 erreurs

### Commandes tapées
| Nom | Total |
| --- | --- |
| `intent` | 41 |
| `build` | 33 |
| `test` | 29 |
...
### Candidats du noyau jamais activés sur aucun poste
`retro`

### Frictions (7)
| Catégorie | Commande | Friction |
| --- | --- | --- |
| command | /test | relance toute la suite quand je voulais un seul modèle |
| command | /test | ne trouve pas les tests quand AGENTS.md manque |
| docs | /intent | la page dit « spec » mais la commande écrit intent.md |
...
Par catégorie : command ×4, docs ×2, guardrail ×1
```

Lecture : deux frictions sur `/test` disent la même chose, c'est un ticket ; `retro` jamais activé sur six postes est un candidat à passer en option, sauf si quelqu'un explique en une ligne pourquoi il reste.

## Quand la tenir

Aucune date n’est imposée par le kit. Une revue a du sens quand plusieurs postes ont dépassé le seuil, typiquement après une phase pilote ou quelques semaines d’usage, puis à chaque fois que l’équipe envisage d’ajouter des skills : l’ajout d’une brique est le bon moment pour en retirer une.

## Déroulé

1. Chaque personne lance `usage --json <fichier>` et partage le fichier ; les relevés sont par poste. L’équipe agrège avec `python3 scripts/usage-aggregate.py <fichiers>` : totaux, commandes, skills, agents, candidats jamais activés sur aucun poste, et la liste des frictions par catégorie, en Markdown prêt à coller.
2. Le bilan liste déjà les groupes de deux frictions ou plus (même catégorie, même commande) et les signaux mesurés (commandes inconnues, demandes répétées). Pour chaque groupe : un ticket, traité par la règle de support (contrôle `doctor`, ligne de « Ça coince ? », cas d’évaluation, ou correction du prompt). Une friction isolée reste dans le bilan jusqu’à la revue suivante.
3. Pour chaque candidat du noyau : le passer en `optional` dans `skills/catalog.json`, ou écrire en une ligne pourquoi il reste. Les deux sont des décisions valables ; l’absence de décision ne l’est pas.
4. Pour chaque commande jamais tapée : vérifier que `/guide` la propose dans les bons cas et que sa fiche se comprend sans la doc. Sinon, corriger le routeur ou la fiche, pas la commande.
5. Relire les propositions de `/retro` accumulées et les tables « Excuses entendues et réponses » des playbooks : chaque erreur répétée devient une ligne d’`AGENTS.md`, un cas d’évaluation, ou une ligne de table. Jamais un prompt de plus à retaper.
6. Un skill amont dont l’équipe s’écarte est réécrit en version maison courte, même nom, même commande ; l’ancien reste disponible via `extra_skills`. Un skill contribué (`skills/contrib/`) largement utilisé passe sous `skills/internal/` ; un skill contribué sans propriétaire joignable est retiré.
7. Rejouer les tests et `evals/run.py`, publier la version, noter dans le `CHANGELOG` ce qui a bougé et pourquoi.
8. Quand une correction répond à des frictions, le dire en une ligne dans le `CHANGELOG` (« `/test` ne relance plus toute la suite, signalé trois fois ») : les gens notent davantage quand ils voient que ça sert.

## Données et confidentialité

Les journaux lus sont ceux que les CLI écrivent déjà sur le poste. Le relevé ne les copie pas, ne les envoie nulle part et n’en extrait que des comptages par nom de commande, de skill et d’agent. Partager le JSON est un choix de la personne ; l’agrégation se fait sur les fichiers partagés, pas sur les postes.
