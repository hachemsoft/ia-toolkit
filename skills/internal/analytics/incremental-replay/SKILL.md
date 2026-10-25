---
name: incremental-replay
description: "Concevoir ou corriger un modèle incrémental et son rejeu : clé unique, données tardives, fenêtre de retraitement, idempotence, full refresh. Déclencheurs : incrémental, rejeu, backfill, données tardives, le modèle double des lignes, full-refresh."
---

# incremental-replay

Un incrémental se définit par son rejeu : si on ne sait pas dire ce qui se passe quand on retraite une période, le modèle n’est pas prêt.

## Déroulé
1. Établir le grain du modèle et la clé qui l’identifie. Vérifier l’unicité de la clé sur la source avec une requête d’assertion avant toute chose.
2. Choisir la stratégie en la justifiant : insertion seule, fusion sur clé, suppression puis insertion par partition. Pour BigQuery, dire si la table est partitionnée et sur quelle colonne ; la stratégie par partition est la seule qui rend le rejeu d’une période trivial.
3. Définir la fenêtre de retard tolérée (données tardives) et la fenêtre de retraitement à chaque exécution ; les écrire dans la doc du modèle, pas seulement dans le code.
4. Écrire le scénario de rejeu : commande exacte pour retraiter une période, effet sur les lignes existantes, coût estimé, durée. Tester le scénario sur le target de développement : exécuter deux fois la même période et vérifier que le résultat est identique (idempotence) par une requête de comparaison.
5. Documenter quand un `--full-refresh` est nécessaire (changement de logique, de grain, de clé) et ce qu’il coûte ; ne jamais le lancer sur la production sans instruction et sans estimation.
6. Ajouter les tests : unicité de la clé, non-nullité, volume par partition comparé à la source, fraîcheur.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Les doublons viennent de la source, ce n’est pas le modèle » | Le modèle a une clé ; si elle n’est pas unique en sortie, le modèle est faux, quelle que soit la source. |
| « On fera un full refresh si ça dérive » | Un full refresh sur une grosse table coûte et bloque ; concevoir le rejeu par période maintenant. |
| « Les données tardives sont rares » | Rares n’est pas zéro ; fixer la fenêtre et mesurer combien arrivent au-delà. |
| « Deux exécutions donnent le même résultat, forcément » | Prouver l’idempotence par une comparaison avant/après sur une période ; ne pas le supposer. |
| « dbt gère l’incrémental tout seul » | dbt applique la stratégie choisie ; la clé, la fenêtre et le rejeu restent des décisions à écrire. |

## Interdits
Pas de modèle incrémental sans clé vérifiée unique. Pas de rejeu non testé sur le target de développement. Pas de `--full-refresh` en production sans instruction écrite.
