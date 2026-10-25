---
name: kpi-definition
description: "Définir ou redéfinir un KPI avant de le calculer : grain, population, période, exclusions, source de vérité, propriétaire. Déclencheurs : définir un indicateur, le KPI ne colle pas, deux chiffres différents pour la même mesure, nouvelle métrique."
---

# kpi-definition

Un KPI sans définition écrite produit deux chiffres différents dès la deuxième personne qui le calcule. La définition précède la requête.

## Déroulé
1. Lire `GLOSSARY.md` et les définitions existantes (doc dbt, dashboards, tickets). Si le terme existe, partir de lui ; ne pas créer un synonyme. Si le repo a un `GLOSSARY-MAP.md` (plusieurs équipes), dire de quel glossaire vient la définition ; un indicateur partagé par plusieurs équipes a une seule définition, dans le glossaire commun, avec un propriétaire nommé, et les glossaires d’équipe y renvoient au lieu de le redéfinir. Si deux définitions existent, le signaler et demander qui tranche avant d’écrire.
2. Fixer, dans cet ordre, en posant une question à la fois quand c’est ambigu : le grain (une ligne par quoi), la population (qui entre, qui sort, et la règle qui le dit), la période (fenêtre, fuseau, date de référence : événement, enregistrement ou traitement), les exclusions (tests, annulations, doublons, comptes internes), la formule (numérateur, dénominateur, agrégation), la source de vérité (table ou modèle, et pourquoi elle), la fraîcheur attendue, le propriétaire métier.
3. Écrire la définition dans le format du glossaire : un terme, une définition de deux phrases, les synonymes à éviter ; le détail (formule, exclusions, source) dans la doc du modèle qui le porte.
4. Écrire la requête d’assertion qui valide la définition sur un cas connu (un mois, un périmètre dont le chiffre est admis) avant la requête de production. Elle devient un test.
5. Si la définition change un chiffre publié, le dire explicitement et proposer un ADR.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Tout le monde sait ce qu’est un client actif » | Deux équipes ont déjà deux définitions ; écrire la règle d’activité et sa fenêtre. |
| « On prendra la date de la table, c’est pareil » | Date d’événement, d’enregistrement et de traitement divergent sur les données tardives ; choisir et nommer. |
| « Le dénominateur est évident » | Le ratio change avec la population du dénominateur ; l’écrire et le tester sur un mois connu. |
| « On exclura les cas bizarres après » | Les exclusions font partie de la définition ; les lister maintenant, sinon le chiffre bouge à chaque exécution. |
| « Le dashboard fait déjà foi » | Un dashboard n’est pas une définition ; retrouver sa requête, la lire, la documenter ou la corriger. |

## Interdits
Pas de requête de production avant la définition écrite. Pas de nouveau terme quand le glossaire en a un. Pas de chiffre publié sans assertion sur un cas connu.
