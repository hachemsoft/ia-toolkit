# Garde-fous

Un skill est un contrôle consultatif : il rend une violation rare. Un hook de la CLI est déterministe : il la rend quasi impossible. Le kit en livre deux, désactivés par défaut, à activer dans `~/.ai-toolkit/overrides.json` :

```json
{
  "hooks": {
    "dbt-prod-guard": true,
    "protected-paths": true
  }
}
```

Puis `update`. Les scripts sont installés une fois, dans `~/.ai-toolkit/hooks/`, et déclarés à chaque CLI dans la forme qu’elle lit ([matrice](cli/matrice.md)) ; vos propres hooks sont conservés. Les mêmes scripts comprennent l’appel d’outil de chaque CLI prise en charge. `doctor` indique les garde-fous actifs. Les hooks s’exécutent avec le Python qui a lancé l’installeur.

## `dbt-prod-guard`

Refuse toute commande shell `dbt` (aussi `./dbt`, `/chemin/dbt`, `dbt.exe`, toute casse) dont le target est `prod`, `production` ou `prd`, écrit `--target prod`, `--target=prod`, `-t prod`, `-tprod`, avec ou sans guillemets, ou `DBT_TARGET=prod`. Liste modifiable par la variable `AI_KIT_PROD_TARGETS`, séparée par des virgules. Une personne autorisée peut exporter `AI_KIT_ALLOW_PROD=1` dans sa session ; le hook laisse alors passer et l’affiche.

Le refus est renvoyé à l’agent comme une erreur d’outil avec le message du kit, qui le redirige vers le target de développement déclaré dans `AGENTS.md`.

Sans `--target` ni `DBT_TARGET`, il lit le target par défaut dans `profiles.yml` (`--profiles-dir`, puis `DBT_PROFILES_DIR`, puis le repo, puis `~/.dbt`) et refuse s’il est en production, en le disant. Lecture minimale sans PyYAML : les lignes `target:` indentées sous un profil ; avec plusieurs profils dans le fichier, le hook peut refuser par excès, `AI_KIT_ALLOW_PROD=1` reste l’échappatoire.

## `protected-paths`

Refuse l’écriture d’un fichier par un outil de l’agent sous les motifs listés dans `<repo>/.ai-kit/protected-paths`, un motif glob par ligne, commentaires avec `#` :

```
# Sorties générées et contrats figés
target/**
models/legacy/**
dbt_project.yml
*.lock
```

Sans ce fichier, tout est autorisé. L’ancien emplacement `<repo>/.gemini/protected-paths` est toujours lu, en plus ; `.ai-kit/` est neutre, valable pour toutes les CLI. Le fichier se versionne avec le repo ; c’est la place des chemins que `AGENTS.md` déclare sous « Things the agent gets wrong : never edit … ». Le garde-fou lit le fichier du dossier où l’agent est lancé et celui de chaque dossier parent jusqu’à la racine du repo, chacun relatif à son propre dossier : dans un monorepo, les chemins protégés de la racine s’appliquent aussi depuis une zone. La comparaison ignore la casse (`TARGET/x.sql` est protégé par `target/**`) et respecte les frontières de dossier (`targets/x.sql` ne l’est pas). Sur Windows, un fichier sur un autre lecteur que le repo est hors des motifs, donc autorisé.

## Limites

- Les hooks ne couvrent que les actions passées par les outils de la CLI. Un script lancé hors de la CLI n’est pas concerné.
- Ils protègent un poste. Les règles non négociables d’une organisation relèvent de politiques administrées côté plateforme, pas du kit.
- Un hook qui plante laisse passer l’action et n’interrompt pas la CLI : les scripts renvoient toujours un JSON, même sur entrée invalide.

## Ajouter un garde-fou

Un script Python dans `runtime/hooks/` (partagé par toutes les CLI), une entrée dans `hooks.json` (événement, matcher, script, description), des tests dans `tests/test_hooks.py` qui lui passent le JSON d’entrée de chaque CLI prise en charge, une section ici.
