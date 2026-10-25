# Pilote : procédure

Objectif : corriger le kit sur des tickets réels avant de l’ouvrir à toute l’équipe, et vérifier que personne n’a besoin d’aide pour démarrer. Un petit groupe suffit, par exemple deux analystes et un développeur, pendant une à deux semaines. Le choix des personnes et des dates appartient à l’organisation.

## Jour 1, par personne (quinze minutes)

1. Récupérer le kit : `git clone <url du dépôt> ai-toolkit` dans `Documents` (sans git : « Télécharger ZIP » sur la page du dépôt, puis extraire).
2. Si l’organisation impose un mode d’authentification (Code Assist avec projet, Vertex AI) ou un modèle, écrire la clé correspondante dans `~/.ai-toolkit/overrides.json` avant l’étape suivante ; voir [personnalisation › Authentification et modèle](customization.md#authentification-et-modèle). Sinon, rien à faire.
3. Dans ce dossier : `sh scripts/bootstrap.sh` (Mac) ou `.\scripts\bootstrap.ps1` (Windows). Confirmer l’identité, choisir le profil. L’installation se termine par un appel réel au modèle : si ce n’est pas vert, suivre le remède affiché, ne pas appeler.
4. Ouvrir son repo habituel, lancer sa CLI (`gemini` ou `agy`), taper `/guide je commence par quoi ?`.
5. Première fois dans le repo : « Initialise le contexte du projet », puis `setup-workflow` pour déclarer le gestionnaire de tickets de l’équipe.

## Pendant le pilote

- Travailler normalement, en passant par les commandes.
- Quand ça coince : `doctor --live`, puis la page « Ça coince ? », puis un ticket.
- Fin de chaque session un peu longue : `/retro`, et noter ce qu’il propose.
- Dans agy, répondre aux demandes de permission : « toujours autoriser » enregistre la règle dans vos propres réglages agy, le kit n’y touche pas.

## Ticket de support, gabarit

```
Commande ou action :
Ce que j’attendais :
Ce qui s’est passé (sortie copiée) :
Sortie de doctor --live :
```

Chaque ticket est traité par la règle : contrôle `doctor`, ligne de « Ça coince ? », ou cas d’évaluation. Jamais une explication orale répétée.

## Fin de pilote

1. `python3 -m installer usage --json <poste>.json` sur chaque poste ; agrégation par l’équipe.
2. Les cas d’évaluation passés sur chaque CLI depuis un poste pilote.
3. Revue des tickets : ce qui a été transformé en contrôle, page ou cas.
4. Décision : ouverture à toute l’équipe confirmée ou non, périmètre des commandes analyste confirmé ou ajusté, première [revue d’usage](usage-review.md) si le relevé a assez de matière.

## Ce que le pilote doit répondre

- Un analyste comprend-il `/guide` et `/intent` sans lire la doc ?
- `doctor --live` suffit-il à régler les pannes d’authentification sans intervention ?
- Les skills de commande se déclenchent-ils sans qu’on les tape, et est-ce gênant ?
- Les garde-fous activés gênent-ils le travail normal ?
- Les demandes de permission d’agy sont-elles comprises et acceptées sans aide ?
