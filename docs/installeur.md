# L’installeur : ce qu’il fait, ce qu’il ne fait pas

Page de référence pour qui déploie ou maintient le kit. Pour installer : [démarrer](getting-started.md). Où chaque fichier est posé, CLI par CLI : [matrice des CLI](cli/matrice.md). Les couches de contexte et leur priorité : [personnalisation](customization.md).

## Ce qu’il fait

- Ne choisit ni le mode d’authentification ni le modèle : connexion Google, Code Assist sous licence (`code_assist`), Vertex AI (`vertex`) ou clé API, et `model` seulement si vous le déclarez dans `overrides.json`. Voir [personnalisation](customization.md#authentification-et-modèle).
- Détecte une identité déclarative (compte actif de la CLI, git, session OS), la fait confirmer et l’écrit en tête de `30_USER.md` à sa création. Voir [identité](identity.md).
- Stocke profil, identité, surcharges, empreintes et sauvegardes dans `~/.ai-toolkit`.
- Refuse d’écraser les couches, skills, agents ou MCP gérés qui ont été modifiés à la main.
- Retire les anciens fichiers gérés lors d’un changement de profil ou de version s’ils sont intacts.
- Prévalide les conflits, sauvegarde, puis écrit les fichiers ; tente une restauration en cas d’erreur d’écriture.
- Ne touche à aucun repo projet, ne lance aucun serveur MCP, ne télécharge rien.

Les réglages existants doivent être du JSON strict. Un fichier JSON invalide ou contenant des commentaires est refusé sans modification. Les liens symboliques sur les chemins gérés ne sont pas pris en charge.

Les couches de contexte et `30_USER.md` sont écrits dans `~/.gemini/` quand Gemini CLI est installé (il ne lit que son dossier), sinon dans `~/.ai-toolkit/context/`, que les autres CLI incluent ou recopient. Les scripts des garde-fous sont dans `~/.ai-toolkit/hooks/`.

## Commandes

| Action | Mac | Windows PowerShell |
| --- | --- | --- |
| Installer / changer de profil | `sh scripts/bootstrap.sh setup` | `.\scripts\bootstrap.ps1 setup` |
| Appliquer une nouvelle version (après `git pull`) | `sh scripts/bootstrap.sh update` | `.\scripts\bootstrap.ps1 update` |
| Diagnostiquer | `sh scripts/bootstrap.sh doctor --live` | `.\scripts\bootstrap.ps1 doctor --live` |
| Relevé d’usage | `sh scripts/bootstrap.sh usage` | `.\scripts\bootstrap.ps1 usage` |

Options de `setup` et `update` : `--profile <id>`, `--user <email>`, `--target auto|gemini|agy|codex|both|all` (voir [démarrer](getting-started.md)), `--home <dossier>`, `--dry-run`, `--no-live`. Exemple non interactif : `python3 -m installer setup --profile general --user prenom.nom@societe.fr`. Si la politique de l’entreprise bloque les scripts PowerShell : `py -3 -m installer setup`, sans modifier la politique.

## Essai sans toucher à son compte

```sh
python3 -m installer setup --profile data-analyst --home ./sandbox-user --dry-run
python3 -m installer setup --profile data-analyst --home ./sandbox-user
python3 -m installer doctor --home ./sandbox-user
```

Sous Windows remplacer `python3` par `py -3`. `--home` ne s’applique qu’au kit, pas à la configuration réellement chargée par une CLI lancée normalement. `setup` et `update` finissent par un appel réel au modèle ; `--no-live` (ou `AI_KIT_NO_LIVE=1`) le saute, par exemple en CI.

## MCP

Le catalogue propose un serveur de documentation, BigQuery et dbt. Aucun serveur n’est activé par défaut : vos endpoints, transports et authentifications ne sont pas connus. Voir [la configuration MCP](mcp.md).

## Limites

- Chaque CLI a ses limites, décrites sur sa page : [Gemini CLI](cli/gemini.md), [Antigravity CLI](cli/agy.md), [Codex CLI](cli/codex.md).
- Pratiques entreprise et d’équipe proposées comme base, à faire valider par chaque organisation avant diffusion.
- Les skills du socle sont repris d’un dépôt amont sous licence MIT (`skills/LICENSE-UPSTREAM-MIT`), en anglais ; leur mise à jour est manuelle.
- `research` et `implement-spec` (en option) délèguent à des sous-agents de la CLI ; sans eux, fonctionnement dégradé. `/map`, `/triage` et `to-tickets` attendent un gestionnaire de tickets déclaré par repo avec `setup-workflow`.
- Les skills du socle ont été écrits pour un autre outil : `00_KIT.md` donne au modèle la table de correspondance (sous-agents, `CLAUDE.md`, PR) ; leur marque « sur commande seulement » n’est comprise par aucune des CLI actuelles ; le kit la rappelle en contexte sans pouvoir la garantir.
- Pas de secrets embarqués, de gestion de parc ou de politique administrateur. L’identité détectée ne donne aucun droit.
- Pas de configuration de rôle, dataset, target dbt ou KPI spécifique aux projets.
- `doctor` vérifie fichiers, réglages, identité et exécutables, pas l’authentification, les droits IAM ou les appels MCP.
- Tests automatisés exécutables sur Mac/Windows/Linux ; cette version a été testée sous macOS. Découverte des couches et des skills vérifiée sur chaque CLI en bac à sable (versions dans la [matrice des CLI](cli/matrice.md)) ; la recette sur vos postes reste à faire.
- Le contexte utilisateur global est chargé dans tous vos projets : utiliser un compte professionnel.
