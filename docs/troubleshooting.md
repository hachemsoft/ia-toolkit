# Dépannage

Ce qui est propre à une CLI est sur sa page : [Gemini CLI](cli/gemini.md#dépannage-propre-à-gemini), [Antigravity CLI](cli/agy.md#dépannage), [Codex CLI](cli/codex.md).

- **Python introuvable** : vérifier `python3 --version` sur Mac, `py -3 --version` ou `python --version` sur Windows. Ne pas modifier les politiques entreprise ; demander le support IT si nécessaire.
- **Scripts PowerShell bloqués** : utiliser `py -3 -m installer setup` dans le dossier du kit. Ne pas contourner la politique.
- **Settings illisibles** : corriger le JSON existant avec une sauvegarde préalable. Le kit n’accepte pas le JSON avec commentaires (JSONC).
- **Skill du kit masqué** : une copie personnelle de même nom, dans un dossier que la CLI lit en priorité, cache le skill du kit. `doctor` liste les skills masqués. Retirer ou renommer la copie personnelle.
- **Évaluations en erreur d’infrastructure** : `evals/run.py` distingue une réponse d’API indisponible (401, 402 crédits épuisés, 403, 429) d’un échec de comportement ; régler l’authentification ou la facturation de la CLI avant de conclure sur un skill.
- **Skill existant non géré par le kit** : un skill du même nom a été installé hors du kit (par une commande de la CLI, par exemple). Soit le retirer pour laisser le kit fournir le sien, soit l’ajouter à `disabled_skills` dans overrides.json. Le kit n’écrase jamais un fichier qu’il ne gère pas.
- **Skill modifié** : sauver les adaptations dans un nouveau skill ou les sources du kit, restaurer l’ancienne sortie générée intacte, relancer update.
- **Couche de contexte modifiée** (`00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md`) : ces fichiers sont générés. Déplacer la modification vers `30_USER.md`, restaurer le fichier depuis une sauvegarde, relancer update.
- **Contexte non chargé** : vérifier avec la commande de la CLI que les couches globales apparaissent avant l’`AGENTS.md` du projet ; la marche à suivre est sur la page de chaque CLI.
- **Identité détectée erronée** : relancer `setup --user votre.email@societe` ; l’en-tête de `30_USER.md` se corrige à la main. L’identité ne donne aucun droit.
- **Doctor signale un compte hors domaine** : la CLI est connectée avec un compte qui n’est pas dans `allowed_domains`. Se reconnecter avec le compte professionnel avant de travailler sur des données d’entreprise.
- **Skills non visibles** : les lister avec la commande de la CLI, vérifier leur activation et les politiques administrées. La présence des fichiers ne garantit pas leur activation.
- **MCP non configuré** : c’est normal, aucun serveur n’est activé par défaut ; voir [MCP](mcp.md). Un MCP facultatif absent ne fait pas échouer doctor.
- **Doctor retourne 1** : au moins un contrôle local nécessite une action ; 2 indique une erreur de configuration. Les actions setup/update retournent 0 en cas de succès, 2 en cas d’erreur.

## Retour arrière manuel

Fermer la CLI. Chaque installation qui modifie des fichiers crée un dossier daté dans `~/.ai-toolkit/backups`. Il contient les fichiers antérieurs, avec leur chemin relatif au dossier personnel, et un manifeste des fichiers nouvellement créés.

Copier les fichiers sauvegardés vers les mêmes chemins sous votre dossier personnel. Pour les fichiers listés dans `created`, les retirer uniquement s’ils n’ont pas reçu de changements personnels depuis. Ne jamais supprimer globalement le dossier de la CLI ou ses skills. Le manifeste n’est pas un programme de restauration automatique.
