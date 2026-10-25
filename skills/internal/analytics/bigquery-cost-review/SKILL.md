---
name: bigquery-cost-review
description: "Revoir le coût d’une requête, d’un modèle ou d’un job BigQuery avant et après un changement : octets lus, partitions, clustering, slots, fréquence. Déclencheurs : coût BigQuery, facture, octets scannés, requête chère, optimiser le coût, pourquoi ça coûte."
---

# bigquery-cost-review

Le coût se mesure, il ne s’estime pas à l’œil. Une seule modification entre deux mesures.

## Déroulé
1. Obtenir le SQL, le schéma des tables lues (partitionnement, clustering), la fréquence d’exécution et le mode de facturation (à la demande ou slots).
2. Mesurer avant : estimation d’octets par dry run, et pour un job déjà exécuté, octets facturés, slots-ms et durée dans l’historique des jobs. Noter les trois chiffres ; un dry run ne donne ni temps ni slots.
3. Chercher dans cet ordre : filtre de partition absent ou non poussé (fonction sur la colonne de partition, jointure avant filtre), colonnes lues inutilement, tables non partitionnées lues en entier, jointures qui multiplient avant d’agréger, sous-requêtes répétées, résultats intermédiaires qui mériteraient une table.
4. Proposer une modification à la fois, qui conserve la sémantique. Vérifier l’égalité des résultats sur un périmètre représentatif par une requête de comparaison. Mesurer après, avec les mêmes trois chiffres.
5. Ramener au coût mensuel : octets ou slots par exécution fois la fréquence. C’est ce chiffre qui décide si le changement vaut sa complexité.
6. Fixer un budget maximal avant toute nouvelle exécution coûteuse ; refuser de lancer une requête dont l’estimation dépasse ce budget sans accord.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Un LIMIT réduit les octets lus » | Non : BigQuery lit les colonnes entières ; seul un filtre de partition ou de cluster réduit le scan. |
| « Le dry run dit que c’est petit » | Le dry run ignore les slots et le temps ; regarder le job réel pour une requête lente. |
| « C’est une petite requête » | Une petite requête lancée toutes les cinq minutes coûte plus qu’une grosse mensuelle ; compter la fréquence. |
| « SELECT * est plus simple à maintenir » | Chaque colonne lue est facturée ; nommer les colonnes. |
| « On a optimisé, c’est forcément moins cher » | Mesurer après, avec les mêmes chiffres qu’avant ; sinon ce n’est pas une optimisation, c’est une hypothèse. |

## Interdits
Pas de recommandation sans mesure avant et après. Pas d’exécution au-delà du budget fixé. Pas de changement de sémantique présenté comme une optimisation.
