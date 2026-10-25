# Connexions MCP

Les définitions du catalogue sont des fiches de préparation, pas des serveurs opérationnels. Le kit configure chaque CLI à partir des surcharges utilisateur, dans la forme qu’elle lit ([matrice](cli/matrice.md)). L’équipe pourra préremplir ces configurations lors d’une version ultérieure.

## Serveur distant approuvé

Dans `~/.ai-toolkit/overrides.json`, ajouter une entrée avec `enabled: true` et `server`. Exemple illustratif uniquement : remplacer l’URL par votre serveur approuvé avant activation.

```json
{
  "extra_skills": [],
  "disabled_skills": [],
  "mcp": {
    "documentation": {
      "enabled": true,
      "server": {
        "httpUrl": "https://mcp.example.org/mcp"
      }
    }
  }
}
```

Lancer `update`, puis redémarrer la CLI et vérifier ses serveurs MCP avec sa commande (voir sa page). Selon le serveur, suivre son flux d’authentification. Le kit ne gère ni OAuth ni tokens. Pour un transport SSE approuvé, utiliser `url` au lieu de `httpUrl`.

## Serveur local approuvé

Le champ `server` peut contenir `command`, `args` et les réglages du serveur. Le kit ne télécharge et n’exécute jamais cette commande. Les exécutables requis doivent être disponibles sur le poste ; privilégier un endpoint distant ou un runtime déjà présent. Une commande comportant un chemin propre à Mac devra être adaptée sur Windows.

Conserver les références de variables d’environnement exigées par le serveur ; ne pas placer de secrets en clair dans les fichiers. Ne pas activer `trust: true` : ce kit le refuse. Les sauvegardes peuvent contenir votre configuration préexistante ; les traiter comme des fichiers personnels sensibles.

## Désactivation

Passer `enabled` à false ou retirer l’entrée puis lancer `update`. Seule la connexion préfixée `ai-kit-` et précédemment gérée est retirée. Les autres MCP sont conservés. Si un MCP géré a été modifié directement dans les settings, le kit demande de résoudre le conflit.

## BigQuery et dbt

- Faire choisir le serveur et le mode d’authentification par l’équipe plateforme.
- Limiter réellement les droits via IAM et les outils autorisés ; les instructions ne sont pas un contrôle d’accès.
- Garder les projets GCP, datasets, targets dbt et budgets spécifiques dans le repo propriétaire.
- Vérifier la compatibilité des outils dbt avec vos versions et votre mode de déploiement.
- Tester la découverte, la connexion et les opérations permises depuis chaque CLI sur un environnement de développement.

`doctor` contrôle la présence de la configuration et de l’exécutable local s’il y en a un. Il ne fait pas de ping, de requête, de validation d’identité ou de test de permissions.
