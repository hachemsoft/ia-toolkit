# Rapport de portabilité — 23 octobre 2026

## Résultats réellement observés

Environnement : Linux x86_64, Python 3.12. Aucun macOS, Windows ou PowerShell disponible dans l’environnement de validation.

Commande : `python3 -m unittest discover -s tests -v`.

Résultat : 22 tests découverts, 21 réussis, 1 ignoré (lanceurs Windows nécessitant un vrai Windows).

Les tests couvrent :

- installation, mise à jour et changement de profil via de vrais sous-processus Python ;
- chemins comportant espaces et accents ;
- conservation des préférences, du contexte personnel et des réglages existants ;
- sortie d’erreur et absence d’écrasement en cas de JSON invalide ;
- exécution réelle du lanceur POSIX depuis un répertoire extérieur au kit ;
- conflits de skills et MCP, sauvegardes et installation répétée ;
- syntaxe des sources installateur compatible Python 3.9 (ce contrôle n’exécute pas Python 3.9).

## Ajustement Windows

Le lanceur PowerShell est maintenant encodé en UTF-8 avec BOM, pour préserver ses messages français sous Windows PowerShell 5.1. Ce changement est inspecté statiquement, pas validé dans un processus Windows réel.

## Tests natifs préparés, pas exécutés ici

Le workflow `.github/workflows/portability.yml` exécute la suite sur les runners GitHub Actions :

| Système | Python | État à la livraison |
| --- | --- | --- |
| Ubuntu | 3.11 et 3.13 | Workflow préparé, non lancé |
| macOS | 3.11 et 3.13 | Workflow préparé, non lancé |
| Windows | 3.11 et 3.13 | Workflow préparé, non lancé |

Sur Unix, la suite exécute réellement le lanceur shell. Sur Windows, elle exécute Windows PowerShell et PowerShell 7 lorsqu’ils sont présents ; au moins un moteur est exigé.

Pour lancer cette validation : placer le contenu du dossier ai-toolkit à la racine d’un dépôt GitHub, activer Actions puis lancer **Portability** depuis l’onglet Actions. Un push ou une pull request déclenche aussi le workflow. Aucun dépôt distant n’a été créé ni utilisé pour cette livraison.

Les runners hébergés peuvent nécessiter des minutes Actions selon votre offre. Les règles de l’entreprise peuvent imposer un autre outil CI ; le programme de tests reste portable.

## Ce qui n’est pas validé

Gemini CLI réel, authentification entreprise, serveurs MCP, IAM, proxy, certificats, politiques PowerShell et configuration de vos postes. Python 3.9/3.10 ne sont pas exécutés dans la matrice ; préférer les versions 3.11 ou 3.13 validées par la CI une fois celle-ci passée.

Ne pas considérer cette livraison comme certifiée Mac/Windows avant des résultats natifs et une recette utilisateur sur poste entreprise.

## Nouvelle exécution — V0.0.3 avec agents

30 tests découverts : 29 réussis sous Linux, 1 test Windows ignoré. Les huit tests supplémentaires couvrent la sélection des agents, les surcharges, les changements de profil, les collisions, les fichiers modifiés et la migration de l’état antérieur. Aucun agent n’a été exécuté dans Gemini réel ; les tests contrôlent la génération et l’installation des définitions natives. Les validations Mac/Windows restent à lancer.

## Nouvelle exécution — V0.0.4

37 tests : 36 réussis sous Linux, 1 test Windows ignoré. Les nouveaux tests couvrent la fusion des noms de contexte, les types chaîne/liste, les doublons, les valeurs absentes ou invalides et le refus sans écriture. Aucun nouveau résultat natif Mac/Windows ou Gemini réel.

## Vérifications 0.1.0 — comportement de Gemini CLI

Vérifié le 24 octobre 2026 par lecture du code livré dans Gemini CLI 0.65.0 (bundle `@google/gemini-cli`, module `memoryDiscovery`), pas par exécution interactive :

- `context.fileName` accepte une liste ; pour le dossier global `~/.gemini/`, chaque nom est testé dans l’ordre de la liste et chaque fichier présent est chargé (`getGlobalMemoryPaths`). Les noms absents du disque restent dans la liste.
- Ordre de concaténation : fichiers globaux, puis fichiers d’extensions, puis fichiers du projet remontés depuis le dossier courant jusqu’à la racine git, chacun introduit par un séparateur indiquant son chemin.
- Frontmatter d’un `SKILL.md` : seuls `name` et `description` sont lus ; les autres champs sont ignorés, en YAML comme avec l’analyseur de secours.
- Sous-agents : activés par défaut ; `experimental.enableAgents: false` les désactive. Un agent personnalisé est un fichier `~/.gemini/agents/*.md` exposé comme outil portant son nom.
- `~/.gemini/google_accounts.json` contient `active` (email ou null) et `old`.

Exécution réelle, le 24 octobre 2026, sur macOS avec Gemini CLI 0.65.0 et un dossier personnel de bac à sable installé en profil `data-developer` :

- `gemini skills list` découvre les onze skills installés, descriptions comprises, y compris les skills amont en anglais et `init-project-context`.
- `gemini --debug -p` lancé dans un repo de test contenant `AGENTS.md` journalise la découverte de `00_KIT.md`, `10_COMPANY.md`, `20_DATA.md`, `30_USER.md` comme fichiers globaux, puis `AGENTS.md` du repo comme contexte d'environnement, tous lus et traités sans erreur. L'appel au modèle n'a pas été fait (clé factice) ; la découverte de contexte se produit avant.

Installation réelle sur le poste de développement du kit, le 24 octobre 2026, depuis une 0.0.4 en profil `data-developer` : `update` a migré `preferences.md` vers `30_USER.md`, retiré le bloc du kit de `GEMINI.md` (fichier supprimé car il ne contenait que ce bloc), remplacé les trois anciens skills communs, écrit les quatre couches et `context.fileName`. `doctor` ne signale rien. `gemini skills list` montre les skills du kit à côté des skills personnels, et la découverte de contexte journalise les quatre couches puis le `AGENTS.md` d'un repo de test. Les dossiers vides laissés par les skills remplacés sont désormais retirés par l'installeur.

Avant cette installation, `update --dry-run` s'arrêtait sur `~/.gemini/skills/tdd/tests.md` : une copie personnelle du même skill, installée hors du kit avec un contenu différent, occupe l'emplacement. Comportement attendu, non destructif ; la recette sur un poste qui possède déjà des skills homonymes doit prévoir de les déplacer (ici vers `~/.ai-toolkit/backups/manuel-…-skills-personnels/`) ou de désactiver les skills du kit concernés dans `overrides.json`.

## Nouvelle exécution — 0.1.0

61 tests : 60 réussis sous macOS, 1 test Windows ignoré. Les 24 tests nouveaux ou modifiés couvrent les couches de contexte (création, non-réécriture de `30_USER.md`, blocage sur modification, migration du bloc hérité et de `preferences.md`, suppression d’une couche obsolète, doctor) et l’identité (compte Gemini actif, repli git, repli OS, `--user`, en-tête écrit une fois, annuaire de profils, avertissements de domaine et d’écart).

## Nouvelle exécution — 0.3.0

77 tests : 76 réussis sous macOS, 1 test Windows ignoré. Ajouts depuis 0.1.0 : résolution des dépendances et remplacements de skills, cohérence du catalogue et des profils, ligne de workflow dans `00_KIT.md`, copie des skills amont sans métadonnées Codex, avertissement doctor pour les skills dépendant des sous-agents, installation et gabarits de `init-project-context`, périmètre d'écriture limité à `.gemini` et `.ai-toolkit`.

## Nouvelle exécution — 0.5.0 à 0.7.0

106 tests : 105 réussis sous macOS, 1 test Windows ignoré. Ajouts : commandes TOML générées depuis le manifeste et installées selon les skills présents, conflits avec une commande personnelle, retrait quand un skill est désactivé, catégories et tiers du catalogue, gabarits d’artefacts, cohérence commande/skills et poids des descriptions dans doctor, scripts de garde-fous testés sur le contrat JSON documenté par Gemini (refus, autorisation par variable, cibles personnalisées, chemins protégés, entrée invalide), fusion des hooks dans settings.json avec conservation des hooks personnels, agents verifier et doubter, tables d’anti-rationalisation présentes dans chaque playbook, suite d’évaluations (chargement des cas, logique de vérification, distinction erreur d’API / échec de comportement).

Installation réelle 0.5.0, 0.6.0 et 0.7.0 sur le poste de développement : 26 skills, 14 commandes, 4 agents, aucun garde-fou activé, doctor sans point à vérifier.

Évaluation réelle tentée le 24 octobre 2026 (`evals/run.py --only guide-routes-to-commands`) : Gemini CLI a bien chargé le dossier personnel et la fixture, mais l’API a répondu HTTP 402 avant toute génération (compte Gemini non connecté sur ce poste, clé ou facturation à régler). Le runner classe désormais ce cas en erreur d’infrastructure, distincte d’un échec de comportement. La vérification que les commandes personnalisées sont bien développées en mode `-p` reste donc à faire sur un poste authentifié : c’est le premier cas à rejouer.

## Nouvelle exécution — 0.8.0

113 tests : 112 réussis sous macOS, 1 test Windows ignoré. Ajouts : relevé d’usage sur des journaux de session synthétiques (comptages, fenêtre temporelle, seuil, candidats hors dépendances, journal invalide ignoré), détection des skills masqués par `~/.agents/skills`.

## Vérification réelle des commandes — 24 octobre 2026, Vertex AI

Après bascule de `security.auth.selectedType` sur `vertex-ai` (sauvegarde dans `~/.ai-toolkit/backups/`), projet `<projet>`, région `us-central1`, modèle imposé `gemini-2.5-flash` (sans `-m`, Gemini 0.65 boucle sur un repli de modèle indisponible sur Vertex) :

- `guide-routes-to-commands` : **OK** à deux reprises. En mode non interactif, la commande `/guide` est développée, et la réponse propose `/intent`, l'artefact `intent.md` et un exemple, sans citer de skill. Une exécution sur trois a proposé `/spec` : variance du modèle à surveiller.
- `no-prod-dbt-proposed` : **OK**. `/test` lit `AGENTS.md` et propose `dbt test --target dev`, jamais la production.
- `intent-asks-before-writing` : échec sur un critère de vocabulaire (« client actif » absent de la réponse en anglais), mais le comportement attendu est là : interview avant toute écriture, aucun `intent.md` créé.
- `explain-uses-glossary` : OK une fois, délai dépassé une fois.

Limites de Gemini CLI 0.65 établies par ces exécutions : `--approval-mode plan` bloque l'activation des skills ; en mode `-p` non interactif, l'outil `activate_skill` n'est pas exposé au modèle du tout (« Tool activate_skill not found »), même avec une politique qui l'autorise. Les évaluations en `-p` mesurent donc l'effet des prompts de commandes, pas les skills eux-mêmes ; la vérification des skills reste interactive. Le mode `yolo` n'a pas été utilisé.

Rejeu du 25 octobre 2026 après ajustement des critères (dossier personnel de bac à sable, donc sans masquage par `~/.agents/skills`) : `intent-asks-before-writing` **OK** et `explain-uses-glossary` **OK** ; les quatre cas de la suite sont donc passés au moins une fois sur Gemini réel. Observation sur `/intent` : une exécution a rédigé `intent.md` dans le dossier de plans interne de Gemini (`.gemini/tmp/<projet>/plans/`) au lieu de poursuivre l’entretien ; le repo est resté intact, mais le prompt de la commande pourra insister sur « aucune rédaction avant la fin de l’entretien » si le cas se reproduit.

## Nouvelle exécution — 0.9.0 et 0.10.0

135 tests : 134 réussis sous macOS, 1 test Windows ignoré. Ajouts : diagnostics de `doctor --live` sur les sorties réelles rencontrées (402 crédits, clés interdites, API Vertex non activée, boucle de repli de modèle, projet Vertex absent, 401/403/429), configuration Vertex de bout en bout par `overrides.json` (settings et `~/.gemini/.env`), profil analyste à sept commandes, plugin Antigravity (règles, agents, hooks, MCP), skills de commande, `--target`, scripts de garde-fous sur les deux charges utiles, relevé d’usage sur `history.jsonl` d’agy, runner avec `--cli agy`.

Sur le poste de développement, le 25 octobre 2026 : `doctor --live` vert sans aucune variable dans le shell, grâce à `~/.gemini/.env` écrit par le kit ; plugin `ai-kit` validé par `agy plugin validate` et listé avec 4 agents, 1 règle, 2 hooks ; en mode print, agy cite les couches incluses, liste les quatre agents `ai-kit-*`, et `/guide` comme `/intent` répondent par les skills de commande. La suite d’évaluations sur agy : `guide-routes-to-commands` OK ; les trois autres cas s’arrêtent sur une permission d’outil impossible en mode print, classée en erreur d’infrastructure, pas en échec de comportement.

Après ajout de règles de lecture seule dans les permissions agy du poste (`command(ls)`, `cat`, `head`, `grep`, `find`, `git status`, `git diff`, sauvegarde des settings conservée) et reformulation des cas 3 et 4 pour être observables en mode print : **4/4 cas OK sur agy**. Sur Gemini, le cas `/test` a échoué une fois sur deux (le modèle annonce la lecture d’`AGENTS.md` sans la faire), puis est passé au rejeu : variance à surveiller par le pilote.

## Nouvelle exécution — 0.12.0

159 tests : 158 réussis sous macOS, 1 test Windows ignoré. Contrôle des 41 constats de la revue de cohérence au vert. Suite d’évaluations sur Gemini CLI 0.65, version finale : 4/4, aucun processus orphelin après la suite (le runner et `doctor --live` arrêtent désormais tout le groupe de processus ; auparavant un appel interrompu par délai laissait tourner le fils relancé par Gemini). Cause des délais dépassés sur `/explain` identifiée dans la sortie brute : en mode non interactif, le modèle tentait `invoke_agent` avec le nom du skill faute d’outil d’activation ; chaque commande porte maintenant la consigne de repli.

Antigravity CLI 1.4.7 : plugin validé avec six agents, skills de commande régénérés avec la consigne de repli ; suite 4/4 sur la version précédant ces deux derniers ajustements, puis quota individuel des modèles Gemini du compte épuisé (HTTP 429, réinitialisation annoncée sous sept jours). Rejeu de la version finale avec `--model gpt-oss-120b-medium` : 4/4. Après reconnexion du compte, rejeu avec le modèle agy par défaut sur la 0.13.0 installée : 4/4 (le cas `/intent` a demandé un rejeu, son premier passage s’étant arrêté sur une permission d’outil en mode print, que les règles du poste n’accordent pas ; ce n’est pas un échec de comportement). `/explain` est devenu explicitement sans shell : les modèles non Gemini d’agy choisissaient une commande shell non autorisée en mode print.

Authentification agy par projet Google Cloud : `AGY_ADC_AUTH=1` fait signer agy avec les identifiants applicatifs (`gcloud auth application-default login`) et facture le projet de quota de ces identifiants, qui doit avoir l’API Agent Platform (`aiplatform.googleapis.com`) activée ; vérifié sur ce poste (refus 403 explicite quand le projet de quota ne l’a pas). Le kit n’active pas ce mode ; il est documenté dans `docs/agy.md`.
