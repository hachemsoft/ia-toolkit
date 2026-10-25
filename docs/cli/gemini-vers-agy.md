# Passer de Gemini CLI à Antigravity CLI : ce qui change, ce qui ne change pas

Une page pour les personnes qui passent de Gemini CLI à agy. À lire en deux minutes.

## Ce qui ne change pas

- **Les commandes** : `/guide`, `/intent`, `/build`, `/test`, `/ship`, `/diagnose`, `/learn`, et pour les développeurs `/spec`, `/review`, `/design`, `/map`, `/triage`, `/explain`, `/retro` ; les options (`/ask`, `/handoff`, `/research`, `/wizard`, `/audit`) et votre `extra_commands` restent les mêmes. Mêmes noms, mêmes artefacts (`docs/sdlc/<date>-<slug>/intent.md`, `spec.md`, `plan.md`).
- **Votre fichier** : `~/.gemini/30_USER.md`. Il est lu par les deux outils.
- **Les repos** : `AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`, `.agents/skills/`. Rien à migrer.
- **Les garde-fous et le relevé d’usage** : mêmes réglages dans `~/.ai-toolkit/overrides.json`.

## Ce qui change

- **Lancer** : `agy` au lieu de `gemini`, toujours depuis le dossier de l’app.
- **Voir ce qui est installé** : `/help` dans agy liste les commandes, qui sont des skills ; `agy plugin list` montre le plugin `ai-kit`.
- **Un redémarrage** d’agy après chaque `update` du kit, pour qu’il redécouvre le plugin.
- **Les permissions** : agy demande l’accord avant une commande shell ou une écriture. Répondre ; « toujours autoriser » enregistre la règle dans vos réglages agy, que le kit ne modifie jamais. En mode automatique (`agy -p`), les outils refusés arrêtent la réponse.

## Si ça coince

1. `sh scripts/bootstrap.sh doctor --live` (Mac) ou `.\scripts\bootstrap.ps1 doctor --live` (Windows) : il dit quoi faire.
2. La page [Ça coince ?](../ca-coince.md).
3. Sinon, un ticket : il deviendra un contrôle `doctor`, une ligne de la page, ou un cas d’évaluation, jamais une explication orale répétée.

## Pour installer ou mettre à jour

Depuis le dossier du kit : `sh scripts/bootstrap.sh update` (Mac) ou `.\scripts\bootstrap.ps1 update` (Windows). Le kit détecte Gemini et agy et installe pour les deux.
