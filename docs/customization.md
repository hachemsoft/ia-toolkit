# Personnalisation

Le dossier utilisateur est celui de Windows ou macOS, pas celui du projet.

## Les couches de contexte

Le kit installe des fichiers courts, chargés par l’agent dans tous vos projets, dans cet ordre. Ils sont dans `~/.gemini/` si Gemini CLI est installé (il ne lit que son dossier), sinon dans `~/.ai-toolkit/context/` ; détail par CLI : [matrice](cli/matrice.md#ajouter-une-cli).

| Fichier | Propriétaire | Contenu |
| --- | --- | --- |
| `00_KIT.md` | kit | profil, règle de priorité entre les couches |
| `10_COMPANY.md` | kit | pratiques entreprise |
| `20_TEAM.md` | kit | pratiques d’équipe |
| `30_USER.md` | vous | langue, style, niveau, domaines, workflow par défaut |

Les fichiers du kit sont des sorties générées : les modifier bloque `update`. Tout ce qui vous est propre va dans `30_USER.md`, créé une fois au `setup` et jamais réécrit ensuite. Une modification y prend effet au prochain lancement de la CLI, sans `update`.

Règle de priorité, écrite dans `00_KIT.md` : les pratiques s’imposent ; `30_USER.md` ajuste la forme et le workflow ; l’`AGENTS.md` du projet l’emporte sur `30_USER.md` en cas de conflit. L’agent lit les fichiers les uns après les autres, il n’y a pas de surcharge mécanique : c’est la rédaction qui fait la priorité.

## Le format des rapports

`/build`, `/test`, `/diagnose` et `/review` finissent par un rapport. Pour en changer la forme, ajouter une section `## Report` : dans `30_USER.md` pour soi, dans l’`AGENTS.md` du repo pour l’équipe, qui l’emporte. Sans section, le format par défaut du kit s’applique. Exemple pour un repo Data :

```markdown
## Report
- One line: what the change does, in business terms.
- Models touched, with their grain before and after.
- Verification: commands run, pass/fail, rows compared on a known period.
- Risks for the dashboards that read these models.
- What is left, and who must decide it.
```

`/build` et `/diagnose` s’arrêtent aussi d’eux-mêmes après trois corrections ratées sur la même vérification, et rapportent ce qu’ils ont essayé au lieu de boucler.

## Surcharger par projet

Une commande du kit se surcharge dans le repo, sous la forme que lit la CLI ([matrice](cli/matrice.md)) ; le projet l’emporte.

Chaque repo fournit son `AGENTS.md`, lu après les couches globales. Pour y redéfinir une préférence, reprendre le même titre que dans `30_USER.md` (« Langue et style », « Mon workflow par défaut ») et écrire la règle du projet. 

## Commandes, skills, agents et MCP

`~/.ai-toolkit/overrides.json` : sélection des commandes, skills, agents et MCP. Conserver un JSON valide.

**Commandes.** `extra_commands` ajoute des commandes à celles du profil, avec leurs skills ; `disabled_commands` en retire. Un analyste qui veut `/spec` et `/review` :

```json
{ "extra_commands": ["spec", "review"] }
```

**Skills.** Exemple : un analyste ajoute le skill Python/JS (qui s’appuie sur `codebase-design`, ajouté automatiquement) et désactive le playbook de coût BigQuery :

```json
{
  "extra_skills": ["python-js-change"],
  "disabled_skills": ["bigquery-cost-review"],
  "mcp": {}
}
```

Les skills ajoutés doivent exister dans `skills/catalog.json`. Un skill requis par un autre (`requires`) ne peut pas être désactivé seul ; `update` le signale. Un ancien nom (`clarify-request`, `debug-systematically`, `verify-change`) est redirigé vers son remplaçant. Appliquer avec `update` depuis le dossier du kit. Voir [workflow](workflow.md) pour le rôle de chaque skill.

Les réglages propres à la CLI restent éditables dans ses propres fichiers ; le kit préserve les clés existantes. Pour changer une valeur par défaut déjà installée, modifier la valeur dans les réglages de la CLI.

Un skill de projet de même nom peut supplanter le skill global ; utiliser des noms explicites. Les trois façons d’ajouter ou de remplacer un skill (pour soi, pour un repo, pour l’organisation) sont dans [ajouter ou remplacer un skill](extending.md). En cas de modification locale d’un skill géré, update s’arrête : sauvegarder votre variante hors du répertoire géré, puis restaurer le fichier de distribution avant de relancer. Pour une variante permanente, utiliser un autre nom et la gérer au bon niveau.

## Exemple complet de `overrides.json`

Une développeuse qui veut `/ask` et `/handoff`, le prototypage, pas de recherche déléguée, l'agent de doute en plus, le garde-fou dbt actif, un projet Code Assist d'entreprise et un modèle fixé :

```json
{
  "extra_commands": ["ask", "handoff"],
  "disabled_commands": [],
  "extra_skills": ["prototype"],
  "disabled_skills": ["research"],
  "extra_agents": ["doubter"],
  "disabled_agents": [],
  "mcp": {},
  "hooks": { "dbt-prod-guard": true },
  "code_assist": { "project": "mon-projet-gcp" },
  "model": "gemini-2.5-flash",
  "models": { "fast": "gemini-2.5-flash", "deep": "gemini-2.5-pro" },
  "frictions": "propose"
}
```

`frictions` règle ce que fait l’agent sur les cinq signaux de friction : `propose` (par défaut) il propose `/friction` et vous validez ; `auto` il note lui-même, sans demander, et le dit en une ligne ; `off` il ne dit rien. Dans tous les cas, la ligne reste sur votre poste. `models` donne un modèle par capacité d’agent (`fast`, `deep`), voir [agents](agents.md#profils-de-capacité). Puis `update`. Chaque clé est facultative ; une clé absente ne change rien. Un skill ajouté par `extra_commands` l'est avec ses dépendances ; un skill requis par un autre ne se désactive pas seul, `update` le dit.

## Authentification et modèle

Le kit ne choisit ni le mode d’authentification ni le modèle : chaque organisation a le sien. Sans déclaration dans `overrides.json`, le kit ne touche à aucun réglage d’authentification ni de modèle ; la CLI se configure alors comme d’habitude. Les clés ci-dessous concernent les CLI qui passent par Google Cloud ; leur effet exact par CLI est sur sa page ([Gemini CLI](cli/gemini.md#authentification-et-modèle)). `doctor --live` reconnaît les pannes de chaque mode et donne la clé à écrire.

| Votre situation | Dans `overrides.json` | Ce que fait `update` |
| --- | --- | --- |
| Connexion Google, compte individuel (Gemini Code Assist gratuit) | rien | rien |
| Connexion Google, licence Code Assist Standard ou Enterprise (« This account requires setting the GOOGLE_CLOUD_PROJECT… ») | `"code_assist": {"project": "<projet-gcp>"}` | `selectedType` sur `oauth-personal`, `GOOGLE_CLOUD_PROJECT` dans `~/.gemini/.env` |
| Vertex AI avec identifiants applicatifs (`gcloud auth application-default login`) | `"vertex": {"project": "<projet-gcp>", "location": "<région>"}` | `selectedType` sur `vertex-ai`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` dans `~/.gemini/.env` |
| Clé API AI Studio | rien | rien : `GEMINI_API_KEY` reste à vous |
| Le modèle par défaut boucle (« Model fallback activated ») ou n’est pas disponible sur votre accès | `"model": "<nom du modèle>"` | `model.name` dans `~/.gemini/settings.json` |

Côté agy, l’équivalent de Vertex est la variable d’environnement `AGY_ADC_AUTH=1` (voir [agy](cli/agy.md#authentification--compte-ou-projet-google-cloud)) ; le kit ne la règle pas. `vertex` et `code_assist` s’excluent. La région Vertex vaut `us-central1` si elle est omise. Dans `~/.gemini/.env`, vos lignes sont conservées ; celles du kit sont signalées par un commentaire `# ai-kit :` et retirées si vous supprimez la clé de `overrides.json` (`selectedType` reste alors tel quel, à régler avec `/auth` si besoin). Les identifiants eux-mêmes (connexion Google, `gcloud`, clé) ne passent jamais par le kit.

## Garde-fous

Deux hooks déterministes, désactivés par défaut, s’activent dans `overrides.json` sous `hooks`. Voir [garde-fous](hooks.md).

## Identité

Voir [identité](identity.md) : comment le kit détecte la personne connectée, ce qu’il en fait et ce qu’il n’en fait pas.
