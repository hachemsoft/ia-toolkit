# Identité de la personne connectée

Le kit détecte une identité pour deux usages : écrire un en-tête dans `30_USER.md` à sa création et proposer un profil par défaut. Cette identité est déclarative et confirmée par la personne. Elle ne donne aucun droit et n’est pas une authentification.

## Sources, dans l’ordre

| Ordre | Source | Lecture | Limite |
| --- | --- | --- | --- |
| 1 | compte Google actif de Gemini | `~/.gemini/google_accounts.json`, champ `active` | vide avant connexion ou après déconnexion ; absent en mode clé API ou Vertex |
| 2 | Git global | `git config --global user.email` et `user.name` | dépend de git et d’une configuration renseignée |
| 3 | session OS | nom de login | pas un email |

Le nom git complète l’email du compte de la CLI quand les deux existent. Les jetons OAuth ne sont jamais lus.

## Comportement

- En interactif, `setup` affiche « Identité détectée : … » et attend Entrée pour confirmer, ou un email pour corriger.
- En non interactif, `--user votre.email@societe` enregistre l’identité ; sans cette option, rien n’est enregistré et une ligne le signale.
- `update` conserve l’identité enregistrée, sauf `--user`.
- L’état (`~/.ai-kit/state.json`) garde `user.email`, `user.name`, `user.source`.
- L’en-tête « Personne : … » est écrit dans `30_USER.md` seulement à sa création. Le corriger à la main ensuite.

## Profil proposé

`profiles/directory.json` associe des emails à un profil. Si l’email détecté y figure, ce profil est proposé par défaut au prompt, ou retenu en non interactif quand `--profile` est absent. `--profile` l’emporte toujours. Garder ce fichier minimal : il est distribué avec le kit.

## Contrôles de doctor

- Identité enregistrée et sa source.
- Écart entre le compte actif de la CLI et l’email enregistré.
- Compte actif de la CLI hors des domaines listés dans `profiles/directory.json` (`allowed_domains`). Liste vide : aucun contrôle.

## Hors périmètre

Le kit ne force pas le type d’authentification de la CLI, ne bloque pas l’installation sur l’identité et ne lit pas les jetons. L’accès aux données reste contrôlé par l’IT et Google Workspace.
