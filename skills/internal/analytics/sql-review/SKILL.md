---
name: sql-review
description: "Revoir du SQL BigQuery ou dbt et investiguer des agrégations, doublons ou résultats métier suspects. Déclencheurs : le chiffre est faux, doublons, total qui ne colle pas, relire cette requête, jointure qui multiplie, NULL inattendus."
---

# sql-review

Identifier le grain de chaque CTE et de la sortie. Vérifier les clés et la cardinalité avant/après chaque jointure ; mesurer les multiplications et ne pas masquer un défaut avec DISTINCT. Contrôler NULL, dénominateurs nuls, fuseaux, bornes temporelles, déduplication et données tardives. Vérifier les exclusions avec la définition métier du projet. Proposer des contrôles de volumes, unicité, totaux et cas limites. Distinguer défaut certain et hypothèse à confirmer ; pour un résultat faux dont la cause n’est pas évidente, suivre la boucle du skill diagnosing-bugs avec une requête d’assertion comme signal. Présenter les corrections SQL et les validations sans lancer d’opération destructive.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Un DISTINCT règle les doublons » | Il les masque ; trouver la jointure qui multiplie et corriger son grain. |
| « Le total est à peu près bon » | À peu près n’est pas une validation ; comparer au chiffre de référence sur une période connue. |
| « Les NULL sont rares, on ignore » | Rares dans le numérateur, catastrophiques dans un dénominateur ; les traiter explicitement. |
| « On a toujours utilisé cette date » | Événement, enregistrement et traitement divergent sur les données tardives ; vérifier laquelle la définition veut. |

## Interdits
Pas de DISTINCT pour cacher une multiplication. Pas de correction proposée sans la requête d’assertion qui la prouve. Aucune opération d’écriture ou de suppression sur les tables : la revue lit, propose, et c’est la personne qui applique.
