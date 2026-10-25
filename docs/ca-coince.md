# Ça coince ?

Premier réflexe, toujours : `sh scripts/bootstrap.sh doctor --live` (Mac) ou `.\scripts\bootstrap.ps1 doctor --live` (Windows). Il fait un appel réel au modèle et, pour chaque panne connue, donne le diagnostic et la commande qui la règle. Les symptômes ci-dessous sont ceux rencontrés sur de vrais postes ; chaque nouveau ticket en ajoute un.

| Symptôme | Cause | Ce qu’on fait |
| --- | --- | --- |
| « Your prepayment credits are depleted », HTTP 402 | la clé AI Studio n’a plus de solde | recharger, ou passer en Vertex : `"vertex": {"project": "<projet>"}` dans `overrides.json` puis `update` |
| « API Keys are Disallowed » | la politique Google Cloud interdit les clés | `gcloud auth application-default login`, Vertex dans `overrides.json`, retirer `GEMINI_API_KEY` de l’environnement |
| « aiplatform.googleapis.com has not been used », HTTP 403 | API Vertex non activée sur le projet | `gcloud services enable aiplatform.googleapis.com --project <projet>` |
| Gemini ne répond jamais, « Model fallback activated » en boucle | modèle par défaut indisponible sur votre accès | `"model": "gemini-2.5-flash"` (ou un autre modèle disponible chez vous) dans `overrides.json`, puis `update` |
| « This account requires setting the GOOGLE_CLOUD_PROJECT… » | licence Code Assist Standard ou Enterprise sans projet déclaré | `"code_assist": {"project": "<projet>"}` dans `overrides.json`, puis `update` |
| « When using Vertex AI, you must specify… » | projet et région absents | `"vertex": {"project": "<projet>", "location": "<région>"}` dans `overrides.json`, puis `update` |
| Les variables Vertex sont ignorées | `selectedType` vaut encore `gemini-api-key` | `update` avec `vertex` dans `overrides.json` le règle ; sinon `/auth` dans Gemini |
| « Skill conflict detected » au démarrage, la commande ne fait pas ce que dit la doc | une copie personnelle dans `~/.agents/skills` ou `.agents/skills` du repo masque le kit | `doctor` liste les masqués ; retirer ou renommer la copie |
| agy demande une permission à chaque commande shell | fonctionnement normal : les permissions agy sont à chaque personne | répondre ; « toujours autoriser » enregistre la règle dans vos réglages agy, le kit n’y touche pas |
| « Il ne voit pas mon glossaire » | Gemini lancé hors du repo | `cd` dans l’app, puis `gemini` ; le kit est global, le repo ne l’est pas |
| `/spec`, `/review` ou `/explain` introuvable pour un analyste | commande hors du profil analyste | `"extra_commands": ["spec"]` dans `overrides.json`, puis `update` ; `00_KIT.md` liste les commandes installées |
| `/intent` ou `/build` introuvable | commande non installée, ou skill désactivé | `doctor` ; vérifier `disabled_skills` et `disabled_commands` dans `overrides.json` |
| « Skill existant non géré par le kit » à l’`update` | un skill homonyme installé hors du kit | le retirer, ou l’ajouter à `disabled_skills` |
| dbt refuse de tourner : « Refusé par le kit : target de production » | garde-fou actif | utiliser le target de développement ; une personne autorisée exporte `AI_KIT_ALLOW_PROD=1` |
| `update` s’arrête sur « modifié localement » | un fichier généré a été édité | déplacer la modification vers `30_USER.md` ou un skill de repo, restaurer, relancer |

Règle d’équipe : un ticket de support ne se règle jamais deux fois à l’oral. Il devient un contrôle de `doctor`, une ligne ici, ou un cas dans `evals/`.
