# Démarrer

Cette page est pour quelqu’un qui n’a jamais vu le kit. Quinze minutes, dans l’ordre.

## 1. Installer (une fois)

1. Récupérer le kit dans un dossier durable, par exemple `Documents` : `git clone <url du dépôt> ai-toolkit`. Sans git : bouton « Télécharger ZIP » sur la page du dépôt, puis extraire dans `Documents/ai-toolkit`.
2. Ouvrir un terminal **dans ce dossier**. Mac : clic droit sur le dossier, « Nouveau terminal au dossier ». Windows : dans l’Explorateur, ouvrir le dossier puis taper `powershell` dans la barre d’adresse et Entrée.
3. Lancer :
   - Mac : `sh scripts/bootstrap.sh`
   - Windows : `.\scripts\bootstrap.ps1` (si les scripts sont bloqués : `py -3 -m installer setup`)
4. Confirmer l’identité détectée (votre email professionnel), puis choisir le profil :
   - **1. Général** : le workflow et les outils, sans playbook métier ; le bon choix en cas de doute.
   - **2. Développeur Java** : Maven ou Gradle, Spring, JUnit ; revue de code et de sécurité.
   - **3. DevOps** : Terraform, Kubernetes, Helm, pipelines CI/CD ; revue d’infrastructure et de sécurité.
   - **4. Architecte** : décisions d’architecture (ADR), conception, revue de design.
   - **5. Data Analyst** : vous écrivez surtout du SQL, du dbt, des requêtes BigQuery, des indicateurs.
   - **6. Développeur Data** : les mêmes, plus du code Python ou JavaScript.

   Le profil se change à tout moment en relançant `setup`. Un skill ou un agent d’un autre profil s’ajoute dans `~/.ai-toolkit/overrides.json` (voir [personnalisation](customization.md)).
5. **Quelle CLI ?** Rien à choisir dans le cas courant : le kit configure les CLI qu’il trouve sur le poste (Gemini CLI, Antigravity CLI, Codex CLI), et Gemini CLI si aucune n’est encore installée. Pour forcer : ajouter `--target` à la commande, par exemple `sh scripts/bootstrap.sh setup --target codex`.

   | `--target` | CLI configurées |
   | --- | --- |
   | `auto` (défaut) | celles présentes sur le poste ; Gemini CLI si aucune |
   | `gemini`, `agy`, `codex` | cette CLI seule |
   | `both` | Gemini CLI et Antigravity CLI |
   | `all` | les trois |

   Une CLI installée plus tard est prise en compte au prochain `update`.
6. L’installation se termine par un appel réel au modèle. **Vert** : c’est fini. Sinon, le message dit exactement quoi faire (une ligne à ajouter, une commande à lancer) ; le faire puis relancer `doctor --live`.

Si votre organisation impose un projet Google Cloud ou un modèle, c’est une ligne dans `~/.ai-toolkit/overrides.json`, donnée par votre équipe plateforme ; voir [personnalisation](customization.md#authentification-et-modèle). Sinon il n’y a rien à déclarer.

## 2. Première session (cinq minutes)

1. Aller dans votre repo : `cd <dossier du repo>`. Sans cela, l’agent ne voit pas le contexte du projet.
2. Lancer votre CLI : `gemini`, `agy` ou `codex`. Dans Gemini et agy, les commandes s’écrivent `/guide` ; dans Codex, `$guide`. Cette page les écrit avec `/`.
3. Taper : **« Initialise le contexte du projet »**. L’agent propose, fichier par fichier et avec votre accord, `AGENTS.md` (une page sur le repo), `GLOSSARY.md` (les mots du métier), `REVIEW.md` (ce qu’une revue vérifie) et deux lignes de `.gitignore` pour les notes de travail. Si quelqu’un l’a déjà fait dans ce repo, passer.
4. Taper : `/guide je dois …` avec votre besoin du jour. Il répond : quel niveau de cérémonie, quelle commande, ce qu’elle produit, un exemple de prompt.

## 3. Travailler : une commande par étape

| Vous voulez | Tapez | Vous obtenez |
| --- | --- | --- |
| cadrer une idée, un ticket, un incident | `/intent <ce que vous voulez>` | un entretien, puis `intent.md` (note locale) |
| transformer l’intent en contrat | `/spec` | `spec.md`, relu dans la MR |
| réaliser | `/build <ticket ou spec>` | `plan.md` à accepter, puis code et tests, une tranche à la fois |
| vérifier | `/test` | la sortie réelle des vérifications du repo |
| faire relire avant de fusionner | `/review main` (`full` pour la production) | constats classés par passe et gravité |
| décrire la merge request | `/ship` | la description, preuves incluses ; rien n’est poussé |
| comprendre un bug ou un chiffre faux | `/diagnose <symptôme>` | cause prouvée, correctif, test de non-régression |
| apprendre un périmètre | `/learn <sujet>` | leçons, quiz, fiches dans `docs/learn/<sujet>/` |
| comprendre une zone ou la dernière réponse | `/explain <zone>` ou `/explain` | une carte en termes du glossaire, ou une reformulation |
| améliorer l’environnement de l’agent | `/retro` | des propositions pour `AGENTS.md`, les checks, les skills |
| noter ce qui a coincé, sans s’arrêter | `/friction <une phrase>` | une ligne locale, reprise à la revue d’usage ; rien n’est envoyé |

Ce que chaque profil installe :

<!-- table-profils:début -->
| Profil | Étapes du workflow | Autres commandes | Agents |
| --- | --- | --- | --- |
| **Général** (`general`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter |
| **Développeur Java** (`java-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, code-reviewer, security-reviewer |
| **DevOps** (`devops`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, infra-reviewer, security-reviewer |
| **Architecte** (`architect`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/guide` `/friction` `/learn` `/explain` `/retro` `/research` `/audit` | repo-investigator, verifier, doubter, architecture-reviewer, code-reviewer |
| **Data Analyst** (`data-analyst`) | `/intent` `/build` `/test` `/ship` `/diagnose` | `/guide` `/friction` `/learn` | repo-investigator, sql-reviewer, dbt-reviewer, verifier |
| **Développeur Data** (`data-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter, sql-reviewer, dbt-reviewer |
<!-- table-profils:fin -->

`/design` façonne une interface ou répond à une question de conception par un prototype jetable ; `/map` découpe un gros chantier en tickets de décision ; `/triage` fait avancer les tickets entrants ; `/research` instruit une question sur des sources primaires ; `/audit` repère les modules à approfondir. `/ask`, `/handoff`, `/research`, `/wizard` et `/audit` s’ajoutent à tout profil qui ne les a pas : `{"extra_commands": ["handoff"]}` dans `~/.ai-toolkit/overrides.json`, puis `update`. Le détail des agents : [agents](agents.md).

La règle qui évite de tout dérouler : **la cérémonie suit les enjeux**. Une retouche se fait sans commande. Une petite fonctionnalité : `/intent` court puis `/build`. Seuls une grande évolution ou un changement en production passent par `/spec` et `/review full`. Chaque commande dit en une ligne le niveau qu’elle a retenu.

## 4. Ce que vous verrez, et ce qui est normal

- `/help` liste les commandes avec une description en anglais ; l’agent vous répond dans votre langue. Les artefacts gardent des titres anglais, leur contenu est dans la langue de l’équipe.
- `intent.md` et `plan.md` sont des notes locales, ignorées par git ; `spec.md` et `REVIEW.md` sont versionnés. L’agent ne commite jamais sans votre accord.
- Les playbooks métier de votre profil (Java, infrastructure, architecture, SQL et dbt…) s’activent seuls quand la tâche s’y prête ; vous n’avez pas à les nommer.
- Dans agy, une demande de permission avant une commande shell est normale : répondre ; « toujours autoriser » retient votre choix dans vos réglages agy, le kit n’y touche pas.
- Sans MCP connecté, l’agent ne lit pas vos données réelles : donner le SQL et les schémas autorisés, ou faire configurer la connexion par l’équipe plateforme.

## 5. Quand ça coince

1. Depuis le dossier du kit : `sh scripts/bootstrap.sh doctor --live` (Mac) ou `.\scripts\bootstrap.ps1 doctor --live` (Windows). Il dit quoi faire.
2. La page [Ça coince ?](ca-coince.md) : un symptôme, une cause, une commande.
3. Sinon un ticket, avec le gabarit de la page [pilote](pilote.md). Et à chaud, `/friction <une phrase>` : la revue d’usage la reprendra. Il deviendra un contrôle, une ligne de la page ou un cas d’évaluation, jamais une explication orale répétée.

## 6. Plus tard

- Vos préférences (langue, style, domaines) : `30_USER.md`, créé pour vous et jamais réécrit par le kit. Il est dans `~/.gemini/` si Gemini CLI est installé, sinon dans `~/.ai-toolkit/context/` ; `doctor` affiche son chemin.
- Ajouter ou retirer des commandes, skills, agents, MCP, garde-fous : `~/.ai-toolkit/overrides.json`, puis `update`. Voir [personnalisation](customization.md).
- Écrire votre propre skill, ou remplacer un skill du kit pour vous, pour un repo ou pour l’équipe : [ajouter ou remplacer un skill](extending.md).
- Quand l’équipe veut que l’agent lise et crée des tickets : `setup-workflow` dans le repo (demande `glab` ou `gh`).
- Mise à jour du kit : `git pull` puis `update` depuis son dossier (sans git : retélécharger le ZIP, remplacer le dossier, puis `update`).
