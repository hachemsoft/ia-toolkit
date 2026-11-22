# AI Kit – Fiche d'installation Windows (pilote)

Environ 15 minutes, sans droits administrateur : à la fin, `ai-kit doctor` ne signale plus rien à corriger et votre CLI IA démarre avec le contexte de l'entreprise.

## 1. Avant de commencer

Vérifiez ces quatre points dans un terminal (PowerShell ou Invite de commandes). S'il en manque un, demandez-le à l'IT avant d'aller plus loin : le kit ne télécharge rien pour le contourner.

| Besoin | Vérifier avec | Attendu |
| --- | --- | --- |
| Python 3.11 ou plus, avec `venv` et `pip`, utilisable par votre compte | `python --version` (ou `py -3 --version`) | `Python 3.11.x` ou plus récent |
| Git 2.29 ou plus | `git --version` | `git version 2.29` ou plus récent |
| Un compte sur le GitLab de l'entreprise, avec accès au projet du kit et à celui de votre Team | ouvrir la page du projet dans le navigateur | la page s'affiche |
| Votre CLI IA installée et connectée (Claude Code, Codex CLI, Gemini CLI ou Antigravity) | la lancer une fois | elle répond |

Si vous aviez fait `pip install .` lors d'un essai précédent, retirez cette copie d'abord : `pip uninstall ai-kit`.

## 2. Installer

1. Ouvrez la page **Releases** du projet du kit sur le GitLab de l'entreprise et téléchargez `ai-kit-<version>.zip` de la dernière version (4.24.1 ou plus récente). Le fichier `SHA256SUMS.txt` à côté sert à vérifier le téléchargement si on vous le demande.
2. Clic droit sur le ZIP, **Extraire tout**, dans un dossier à vous (par exemple `Documents\ai-kit-4.24.1`).
3. Dans le dossier extrait, double-cliquez sur **`Installer.cmd`**. Il crée l'environnement privé du kit dans votre dossier personnel, installe le kit depuis le ZIP (aucun téléchargement), puis lance la configuration.
4. Répondez aux questions dans la fenêtre :
   - **Identité** : « Detected identity: … », appuyez sur Entrée pour confirmer, ou tapez votre adresse e-mail.
   - **Première utilisation du Core** : le kit affiche l'URL, le tag et le commit du dépôt Core. Vérifiez que l'URL est bien celle du GitLab de l'entreprise, puis confirmez.
   - **Connexion GitLab** : une fenêtre de connexion Git peut s'ouvrir la première fois ; connectez-vous avec votre compte GitLab.
   - **Commande `ai-kit` dans le PATH** : acceptez (oui par défaut). Elle est ajoutée au PATH de votre utilisateur, sans droits administrateur.
5. Fermez la fenêtre et **ouvrez un nouveau terminal** : la commande `ai-kit` n'existe que dans les terminaux ouverts après l'installation.

Gardez le dossier extrait jusqu'à la fin du pilote : il sert à relancer l'installation si besoin.

## 3. Vérifier

Dans le nouveau terminal :

| Commande | Ce que vous devez voir |
| --- | --- |
| `ai-kit status` | la version du kit (4.24.1 ou plus) et le Core actif avec son tag `vX.Y.Z` |
| `ai-kit doctor` | un résumé sans ligne `[Check]` ; chaque `[Check]` dit quoi faire |

`ai-kit doctor` n'appelle pas le modèle et ne modifie rien. N'utilisez pas `ai-kit doctor --live` sans raison : il fait un vrai appel au modèle, qui peut être facturé.

## 4. Rejoindre sa Team

Votre référent vous donne le nom de votre Team et l'URL de son dépôt. La première fois :

```
ai-kit team use <nom-team> --url https://<hôte-gitlab>/<groupe>/<projet-team>.git
```

Ensuite, `ai-kit team list` montre les Teams connues (l'active est marquée `*`), et `ai-kit team use none` quitte la Team. Comme pour le Core, la première utilisation affiche l'URL, le tag et le commit à confirmer.

## 5. Première session

1. Ouvrez un terminal dans un de vos dépôts et lancez votre CLI IA.
2. Tapez `/guide where do I start?` (dans Codex : `$guide`). Les phrases normales marchent aussi : les commandes sont des raccourcis.
3. Présentez-vous à l'agent : tapez `/me` dans la CLI, ou `ai-kit user edit` dans un terminal pour éditer votre fiche `USER.md`. Redémarrez ensuite la session.
4. Une gêne pendant le pilote ? Tapez `/friction` : elle est notée en local, pour la revue d'usage.

## 6. Mettre à jour

Deux choses évoluent séparément :

| Ce qui change | Exemple | Comment le recevoir |
| --- | --- | --- |
| Le contenu : Core et Team | contexte, commandes, skills, annonces | `ai-kit sync` (suit les tags `vX.Y.Z` des dépôts) |
| Le moteur du kit | un correctif de la commande `ai-kit` ou des hooks | télécharger le nouveau ZIP sur la page Releases, l'extraire, double-cliquer sur `Installer.cmd`, ouvrir un nouveau terminal |

Rien à désinstaller avant une mise à jour : votre `aikit.toml`, votre `USER.md` et votre Team sont conservés. `ai-kit status` indique si un tag plus récent a été vu à la dernière synchronisation, et `ai-kit rollback` revient à la configuration précédente.

## 7. Si ça coince

| Message ou symptôme | Quoi faire |
| --- | --- |
| `Python 3.11 or newer was not found` (ou « older than 3.11 ») | demander à l'IT Python 3.11+ avec `venv` et `pip` |
| `This Python has no venv or pip support` | demander à l'IT une installation Python complète |
| `ai-kit` n'est pas reconnu | ouvrir un **nouveau** terminal ; sinon relancer `Installer.cmd` |
| `doctor` : « The `ai-kit` command on your PATH is another copy of the kit » | `pip uninstall ai-kit` avec le Python utilisé pour un ancien `pip install .`, puis nouveau terminal |
| `git ls-remote failed (auth)` | se connecter au GitLab : lancer une fois `git ls-remote <URL du dépôt>` dans un terminal et se connecter, puis relancer la commande |
| `git ls-remote failed (network)` avec `CRYPT_E_NO_REVOCATION_CHECK` | `git config --global http.schannelCheckRevoke false` (pris en compte par le kit depuis 4.19.1), ou demander à l'IT de le régler dans la configuration Git |
| `First use of <URL> needs your confirmation in a terminal` | lancer `ai-kit sync` dans un terminal et confirmer l'URL, le tag et le commit |
| `Another run of the kit installer is in progress` | attendre la fin de l'autre fenêtre |

Toujours bloqué : envoyez la sortie complète de `ai-kit doctor` à votre référent du pilote (relisez-la avant : elle montre votre identité et des chemins de votre poste).

## 8. Ce que le kit fait sur votre poste

- Aucun droit administrateur : tout est écrit dans votre dossier personnel (`~\.ai-kit` et les dossiers de vos CLI).
- Une seule modification hors de ces dossiers : la commande `ai-kit` dans le PATH de votre utilisateur, retirée à la désinstallation.
- Aucun appel au modèle, sauf `ai-kit doctor --live` quand vous le demandez.
- Une sauvegarde dans `~\.ai-kit\backups` à chaque exécution qui modifie des fichiers.

Pour désinstaller : `ai-kit uninstall --dry-run` montre ce qui serait retiré, puis `ai-kit uninstall` demande confirmation. Sont gardés : votre `USER.md`, votre `aikit.toml`, `lock.toml`, le cache des sources, les sauvegardes, les frictions et `~/.ai-kit/learning` ; un fichier que vous avez modifié est gardé et nommé.
