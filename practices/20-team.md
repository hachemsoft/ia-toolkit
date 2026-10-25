# Pratiques d’équipe — base proposée à valider
Ces pratiques s’appliquent à tout le monde ; chaque repo les précise dans son `AGENTS.md`.
- Lire les instructions du repo et ses conventions avant de modifier quoi que ce soit.
- Garder architecture, commandes, données de référence, indicateurs et décisions (ADR) dans le repo propriétaire.
- Réutiliser les outils et abstractions existants ; proportionner les changements au besoin.
- Pour une transformation de données ou une requête : établir le grain, les cardinalités des jointures, les règles de dates et les NULL.
- Vérifier la logique métier sur des cas représentatifs, pas seulement la compilation.
- Mesurer coûts et performances avant/après quand ils motivent le changement.
- Exécuter les vérifications pertinentes et rapporter les résultats réellement observés.
- Utiliser les périmètres et environnements explicitement définis par le projet ; jamais la production sans instruction.
