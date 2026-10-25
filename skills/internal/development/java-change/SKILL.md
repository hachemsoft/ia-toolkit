---
name: java-change
description: "Développer ou revoir une fonctionnalité Java dans un repo existant (Maven ou Gradle, Spring ou autre). Déclencheurs : ajouter un endpoint, modifier un service Java, corriger un bug Spring, migrer une dépendance, relire ce code Java."
---

# java-change

Lire les instructions du repo, le `pom.xml` ou le `build.gradle`, la version de Java et du framework, et deux classes voisines qui font déjà quelque chose de semblable. Suivre leurs patterns : découpage en couches, injection de dépendances, gestion des exceptions, mapping des DTO, logs. Ne pas introduire de bibliothèque, d’annotation ou de style nouveau (Lombok, réactif, records) si le repo ne l’utilise pas déjà. Préserver les contrats publics : signatures d’API, schémas JSON, migrations de base déjà appliquées, propriétés de configuration. Développer selon le skill tdd : test JUnit rouge au niveau le plus bas qui prouve le comportement, code minimal, refactor ; un test d’intégration seulement quand le comportement traverse une frontière (base, HTTP, file de messages). Lancer la commande de vérification du repo (`./mvnw verify`, `./gradlew check` ou celle de `AGENTS.md`) et rapporter sa sortie. Les secrets restent dans la configuration externe, jamais dans le code ni les tests. Décrire la livraison avec le skill mr.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Le build est trop long, je ne le lance pas » | Lancer au moins le module touché (`-pl`, ou la tâche Gradle du sous-projet) et dire ce qui n’a pas été lancé. |
| « J’ajoute Lombok, ce sera plus court » | Une dépendance nouvelle est une décision d’équipe ; suivre le style du repo. |
| « Je mocke tout, c’est plus rapide » | Un mock par frontière externe ; la logique métier se teste avec de vrais objets. |
| « Je renomme ce champ JSON pendant que j’y suis » | C’est un changement de contrat ; il se décide et se versionne à part. |
