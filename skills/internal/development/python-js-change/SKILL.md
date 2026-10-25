---
name: python-js-change
description: "Développer ou revoir une fonctionnalité Python ou JavaScript dans un repo existant."
---

# python-js-change

Lire les instructions, dépendances et exemples voisins du repo. Identifier les frontières d’API, erreurs attendues et effets de bord. Réutiliser les patterns présents et éviter une migration de framework implicite. Préserver les contrats publics, les logs structurés existants et les règles de gestion des secrets. Développer selon le skill tdd : test rouge, code minimal, refactor. Avant d’ajouter une interface, appliquer le vocabulaire du skill codebase-design : interface petite, implémentation profonde, couture testable. Vérifier le diff et exécuter les validations utiles ; décrire la livraison avec le skill mr. Laisser les conventions propres à un repo dans ce repo.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Trop simple pour un test » | Alors l’écrire prend une minute ; sinon dire en une ligne pourquoi le changement est trivial. |
| « Je l’ai testé à la main » | Une exécution manuelle n’est pas rejouable ; en faire un test ou coller la sortie exacte. |
| « Je migre le framework au passage » | Hors périmètre ; une migration est un changement à part entière avec son propre plan. |
| « Les tests existants couvrent déjà ça » | Les nommer ; si on ne peut pas, ils ne couvrent pas. |
