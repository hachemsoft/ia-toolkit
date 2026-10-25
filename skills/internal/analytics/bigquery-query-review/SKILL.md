---
name: bigquery-query-review
description: "Optimiser une requête BigQuery lente ou coûteuse et vérifier scans, partitions, jointures et plan. Déclencheurs : requête lente, trop chère, octets lus, filtre de partition, plan d’exécution, slots, cette requête scanne tout."
---

# bigquery-query-review

Obtenir le SQL, les schémas et le périmètre autorisé. Examiner filtres de partition, colonnes lues, cardinalités et agrégations. Utiliser un dry run pour estimer les octets si disponible ; ce chiffre ne donne ni temps réel ni consommation de slots. Inspecter les métriques du job existant pour les problèmes d’exécution. Proposer une modification conservant la sémantique et la vérifier sur un périmètre représentatif ; une seule modification entre deux mesures, comme dans le skill diagnosing-bugs. Fixer un budget maximum avant toute nouvelle exécution coûteuse. Rapporter mesures avant/après, hypothèses et compromis. Ne jamais prétendre qu’un LIMIT réduit forcément les octets lus.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Un LIMIT réduit les octets lus » | Non ; seul un filtre de partition ou de cluster réduit le scan. |
| « Le dry run suffit » | Il ne donne ni le temps ni les slots ; lire le job réel pour une requête lente. |
| « C’est plus rapide, donc moins cher » | Mesurer les octets et les slots après, avec les mêmes chiffres qu’avant. |

## Interdits
Pas d’exécution d’une requête coûteuse sans budget fixé et sans dry run quand il est disponible. Pas de réécriture qui change la sémantique sans la vérifier sur un périmètre connu. Pas deux modifications entre deux mesures.
