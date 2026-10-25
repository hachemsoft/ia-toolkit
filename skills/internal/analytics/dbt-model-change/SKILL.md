---
name: dbt-model-change
description: "Créer, modifier, tester ou documenter un modèle dbt sur BigQuery. Déclencheurs : nouveau modèle, modifier ce modèle, ajouter une colonne ou un test dbt, matérialisation, incrémental, ref et source, dbt run ou dbt test."
---

# dbt-model-change

Lire dbt_project.yml, les versions et modèles voisins. Définir le grain, les sources et dépendances ; utiliser source() et ref() selon les conventions du repo. Choisir la matérialisation à partir des besoins et volumes connus. Pour un incrémental, vérifier unique_key, données tardives et comportement au rejeu. Travailler en test-first selon le skill tdd : écrire d’abord le test dbt (unique, not_null, accepted_values, test singulier) qui décrit le comportement attendu, le voir échouer sur le target de développement, puis modifier le modèle. Garder les tests compatibles avec la version installée ; ne pas supposer la disponibilité des unit tests natifs. Compiler puis exécuter les validations sur le target de développement explicitement identifié. Ne pas lancer full-refresh ou build de production sans instruction correspondante. Comparer volumes et résultats attendus.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « dbt compile passe, le modèle est bon » | Compiler ne teste ni le grain ni les volumes ; lancer les tests sur le target de développement. |
| « Je rajouterai les tests après » | Le test vient avant la modification, c’est lui qui dit quand c’est fini. |
| « Un full refresh ne coûte rien ici » | Estimer d’abord ; sur la production, jamais sans instruction. |
| « La version dbt supporte sûrement les unit tests » | Vérifier la version installée ; ne pas supposer une fonctionnalité. |

## Interdits
Pas de `dbt run`, `dbt build` ou `--full-refresh` sur un target de production. Pas de modification du modèle avant le test dbt qui la décrit. Pas de test supprimé ou affaibli pour faire passer un run.
