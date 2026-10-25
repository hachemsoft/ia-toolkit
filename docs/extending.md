# Ajouter ou remplacer un skill

Trois portées, trois endroits. Le choix dépend de qui doit voir le skill, pas de ce qu'il fait.

| Pour | Où le mettre | Vu par | Mise à jour du kit |
| --- | --- | --- | --- |
| vous seul | le dossier des skills de votre CLI ([matrice](cli/matrice.md)), `<nom>/SKILL.md` | votre CLI | intact : le kit ne touche qu'aux dossiers qu'il a lui-même installés |
| un repo et toute son équipe | `<repo>/.agents/skills/<nom>/SKILL.md`, versionné | les CLI qui lisent `.agents/skills/` ([matrice](cli/matrice.md)) | sans effet |
| toute l'organisation | `skills/internal/<catégorie>/<nom>/` dans le kit, plus le catalogue | tous les postes à la prochaine distribution | c'est le kit |

Un skill est un dossier avec un `SKILL.md` qui commence par un en-tête `name` et `description`, puis des consignes courtes. Les fichiers annexes (gabarits, références) vont dans le même dossier. Le skill `write-a-skill` et la référence `writing-great-skills`, tous deux en option (`extra_skills`), aident à l'écrire ; la règle qui compte : la description dit quand s'en servir, le corps dit quoi faire, rien d'autre.

```markdown
---
name: revue-dashboard
description: "Relire un tableau de bord avant publication : filtres, périodes, totaux, libellés. Déclencheurs : relire ce dashboard, avant de publier, le total ne colle pas."
---

# revue-dashboard
1. Lister les filtres actifs et la période ; comparer au titre.
2. Recalculer un total sur une période connue ; écart toléré : aucun.
3. ...
```

## Pour vous seul

Créer `<nom>/SKILL.md` dans le dossier des skills de votre CLI ([matrice](cli/matrice.md)), avec un **nom qui n'existe pas dans le kit**. La CLI le lit au prochain lancement ; `update` le laisse tel quel. Pour vérifier, lister les skills dans la CLI (la commande est sur sa page, voir la [matrice](cli/matrice.md)).

Deux pièges. Un dossier de même nom qu'un skill du kit dans ce dossier bloque `update` (« existant non géré par le kit ») : le kit refuse d'écraser ce qu'il n'a pas posé. Et certaines CLI lisent un second dossier de skills qui l'emporte à nom égal et masque le skill du kit (voir la page de votre CLI) ; `doctor` liste les skills ainsi masqués. Pour remplacer un skill du kit sans ces effets, passer par un repo ou par le kit, ci-dessous.

## Pour un repo

Créer `<repo>/.agents/skills/<nom>/SKILL.md` et le versionner. Dans un monorepo, préfixer le nom par la zone (`finance-cloture-mensuelle`) : les skills de repo valent pour toutes les équipes. Les CLI qui lisent `.agents/skills/` le trouvent dans ce repo, et un skill de repo **l'emporte sur un skill du kit de même nom**, vérifié sur les CLI prises en charge ([matrice](cli/matrice.md)) : c'est la façon propre de remplacer, pour un projet, un playbook livré (`sql-review` adapté aux conventions du repo, par exemple). `AGENTS.md` peut le mentionner en une ligne pour que les humains le trouvent aussi.

Une commande du kit se surcharge de la même façon, sous la forme que lit la CLI ([matrice](cli/matrice.md)).

## Pour l'organisation : dans le kit

Deux dossiers, deux niveaux d'engagement. `skills/internal/` : livré et maintenu par les mainteneurs du kit, dans les profils. `skills/contrib/` : proposé par une personne ou une équipe qui en reste propriétaire, jamais installé par défaut (`tier: optional`, `origin: contrib`, `owner` dans le catalogue), activable d'une ligne par qui le veut. Un skill contribué qui sert largement passe sous `internal` à une revue d'usage ; un skill sans propriétaire joignable en sort. Les règles sont dans `skills/contrib/README.md` et vérifiées par les tests. La marche ci-dessous vaut pour les deux, seuls le dossier et les champs `origin`, `owner`, `tier` changent.


1. **Le dossier** : `skills/internal/<catégorie>/<nom>/SKILL.md` (catégories existantes : `common` pour le workflow et les outils, puis une par métier : `development`, `operations`, `architecture`, `analytics`), ou `skills/contrib/<nom>/SKILL.md` pour une contribution. Le nom du dossier et le `name` de l'en-tête sont identiques.
2. **Le catalogue** `skills/catalog.json`, une entrée par skill :
   ```json
   "revue-dashboard": {
     "path": "skills/internal/analytics/revue-dashboard",
     "origin": "internal",
     "description": "Relire un tableau de bord avant publication : filtres, périodes, totaux, libellés.",
     "category": "domain",
     "tier": "profile",
     "requires": []
   }
   ```
   `category` : `workflow` (une étape, derrière une commande), `tool` (utilitaire, derrière une commande), `domain` (playbook métier, activé par la tâche), `reference` (vocabulaire lu par d'autres skills), `setup`. `tier` : `core` (dans tous les profils, un test le vérifie), `profile` (selon le profil), `optional` (via `extra_skills` ou `extra_commands`). `requires` installe les dépendances avec lui ; `needs_agents: true` signale qu'il délègue à des sous-agents.
3. **Les profils** `profiles/*.json` : l'ajouter aux profils qui doivent l'avoir, ou le laisser `optional`. Un playbook métier n'est jamais dans le profil `general`.
4. **Une commande, si c'est une étape ou un outil** : un fichier `commands/<nom>.md`, en-tête (`name`, `description` en anglais, `category`, `stage` pour un workflow, `skills`, `order`) et prompt avec `{{args}}` ; voir [le format pivot](format.md). Chaque adaptateur en fait la commande de sa CLI. Une fiche dans `docs/tools.md` pour un outil.
5. **Un cas d'évaluation** `evals/cases/NN-<nom>.json` avec le prompt qui doit déclencher le skill et un critère observable, puis `python3 -m unittest discover -s tests` et `python3 evals/run.py`.
6. **Distribuer** : commit, MR, tag ; les postes font `git pull` puis `update`.

## Exemple complet : un outil `/dashboard-check` en vingt minutes

Le besoin : relire un tableau de bord avant publication. Un skill, une commande, un cas d'évaluation, et il existe dans chaque CLI prise en charge.

1. Le skill, `skills/contrib/dashboard-check/SKILL.md` (contribution d'une analyste qui en reste propriétaire) :

   ```markdown
   ---
   name: dashboard-check
   description: "Relire un tableau de bord avant publication : filtres, période, totaux, libellés. Déclencheurs : relire ce dashboard, avant de publier, le total ne colle pas."
   ---

   # dashboard-check
   1. Lister les filtres actifs et la période ; vérifier qu'ils correspondent au titre.
   2. Recalculer un total sur une période dont le chiffre est connu ; écart toléré : aucun.
   3. Relire chaque libellé avec le GLOSSARY.md du repo ; proposer les termes manquants.
   4. Rendre : ce qui est vérifié, ce qui ne l'est pas, ce qu'il faut corriger avant publication.

   ## Interdits
   Pas de validation sur un échantillon ; pas de total "à peu près".
   ```

2. L'entrée de catalogue, dans `skills/catalog.json` :

   ```json
   "dashboard-check": {
     "path": "skills/contrib/dashboard-check",
     "origin": "contrib",
     "owner": "equipe-reporting",
     "description": "Relire un tableau de bord avant publication : filtres, période, totaux, libellés.",
     "category": "tool",
     "tier": "optional"
   }
   ```

3. La commande, `commands/dashboard-check.md` :

   ```markdown
   ---
   name: dashboard-check
   description: "Review a dashboard before publishing: filters, period, totals, labels"
   category: tool
   skills: [dashboard-check]
   order: 140
   ---

   Activate the dashboard-check skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

   Input: {{args}} (the dashboard, its SQL or a screenshot description).

   Answer in the user's language. State in one line whether this is a quick check or a full review. Follow the skill's four steps and end with what blocks publication.
   ```

4. Le cas d'évaluation, `evals/cases/05-dashboard-check-totals.json` :

   ```json
   {
     "name": "dashboard-check-totals",
     "prompt": "/dashboard-check le tableau de bord ventes mensuelles, total octobre 1 240 commandes",
     "cwd": "dbt-mini",
     "expect": { "regex": ["(total|1 240)", "(filtre|période)"] }
   }
   ```

5. Vérifier et distribuer : `python3 -m unittest discover -s tests`, `python3 evals/run.py --only dashboard-check-totals`, puis commit, MR et tag ; les postes font `git pull` puis `update`. Qui veut l'outil l'active d'une ligne : `{"extra_commands": ["dashboard-check"]}` dans `~/.ai-kit/overrides.json`, puis `update` ; `/dashboard-check` apparaît dans chaque CLI prise en charge.

## Remplacer un skill du kit pour l'organisation

Garder le nom et, s'il y en a une, la commande : les autres skills et les docs s'y réfèrent. Deux cas.

- **Skill interne** (`origin: internal`) : modifier le `SKILL.md` en place, rejouer tests et évaluations.
- **Skill du socle** (`origin: upstream`, repris tel quel sous licence MIT) : ne pas l'éditer, il sera écrasé à la prochaine recopie amont. Écrire une version maison courte dans `skills/internal/<catégorie>/<nom>/`, même nom, changer `path` et `origin` dans le catalogue. L'ancienne version reste disponible en la gardant sous un autre nom en `optional`. C'est ce que la [revue d'usage](usage-review.md) appelle « version maison ».

## Retirer un skill

Pour soi : `"disabled_skills": ["<nom>"]` dans `~/.ai-kit/overrides.json`, puis `update`. Un skill requis par un autre ne se désactive pas seul ; `update` le dit. Pour l'organisation : le passer en `optional` dans le catalogue plutôt que de le supprimer, ce qui le laisse accessible d'une ligne.

## Ce qui ne se personnalise pas par un skill

Les préférences de forme et de langue : `30_USER.md` dans le dossier de la CLI. Les règles d'un repo : son `AGENTS.md`. Les garde-fous déterministes : `overrides.json` sous `hooks` et le fichier `.ai-kit/protected-paths` du repo. Les agents : `extra_agents` et `disabled_agents`, ou un fichier dans `agents/internal/` du kit. Voir [personnalisation](customization.md).
