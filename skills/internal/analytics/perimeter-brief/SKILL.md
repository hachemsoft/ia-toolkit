---
name: perimeter-brief
description: "Produire la fiche d’un périmètre Data à partir d’un repo dbt et de sa doc : sources, couches, modèles clés et leur grain, KPI, règles, propriétaires, questions ouvertes ; plus un quiz et les termes candidats au glossaire. Déclencheurs : fiche du périmètre, onboarding sur un domaine, présente-moi ce périmètre, première leçon."
---

# perimeter-brief

Le document qu’on donne à quelqu’un qui arrive sur un périmètre, et la première leçon de `/learn` quand le sujet est un domaine Data. Tout vient du repo et de sa doc : rien d’inventé.

## Déroulé
1. Inventorier : `dbt_project.yml`, sources déclarées, modèles par couche (source, staging, intermédiaire, mart), exposures, tests, descriptions ; `GLOSSARY.md`, ADR, README, dashboards référencés. Noter ce qui manque.
2. Pour chaque modèle clé (les marts et ce dont ils dépendent directement) : grain tel que documenté ou déduit de la clé, sources, fraîcheur, tests présents. Signaler tout grain non documenté comme question ouverte, pas comme certitude.
3. Lister les KPI exposés avec leur définition quand elle existe ; sinon, la marquer « non définie » et renvoyer vers `kpi-definition`.
4. Relever les règles transverses : dates de référence, fuseaux, exclusions, périmètres d’habilitation, targets dbt et environnements.
5. Produire la fiche en HTML autonome, lisible et imprimable, sans dépendance externe obligatoire : titre, résumé en cinq lignes, schéma des couches (texte ou SVG simple), tableau des modèles clés, tableau des KPI, règles, propriétaires, questions ouvertes, sources consultées avec chemins. L’enregistrer sous `docs/learn/<périmètre>/reference/perimeter-brief.html` avec l’accord de la personne.
6. Produire un quiz de dix questions à choix multiples fondées sur la fiche ; réponses de même longueur, position de la bonne réponse variée, explication d’une ligne par question. Même dossier, `quiz-01.html`.
7. Lister les termes candidats au `GLOSSARY.md` au format de `domain-modeling` ; proposer, ne pas écrire sans accord.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Le grain est évident d’après le nom du modèle » | Un nom n’est pas un contrat ; lire la clé et les tests, sinon marquer « à confirmer ». |
| « Le KPI est défini dans le dashboard » | Retrouver la requête ; si elle n’est pas dans le repo, le KPI est non défini ici. |
| « Je complète avec ce que je sais du domaine » | Le savoir général n’est pas le périmètre de cette équipe ; citer un fichier ou poser la question. |
| « Une fiche courte suffit, on verra les détails plus tard » | Courte oui, mais les questions ouvertes y figurent : c’est elles qui coûtent plus tard. |

## Interdits
Aucune affirmation sans chemin de fichier à l’appui. Pas d’écriture dans le repo sans accord. Pas de quiz sur ce qui n’est pas dans la fiche.
