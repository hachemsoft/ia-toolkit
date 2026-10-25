# Conformité et gouvernance

Cette page aide le service conformité, sécurité ou juridique d’une organisation à analyser le kit. Elle ne revendique aucune conformité : le kit n’est ni certifié ni évalué par un tiers. Elle dit ce que le kit fait, ce qu’il ne fait pas, et ce qui reste à la charge de l’organisation.

## Ce qu’est le kit, en termes de gouvernance

Le kit est un outil de configuration. Il installe des fichiers texte (contexte, commandes, skills, agents, garde-fous) dans les dossiers de CLI d’agent de code déjà présentes sur le poste : Gemini CLI, Antigravity CLI, Codex CLI. Il ne fournit pas de modèle, n’appelle aucun service à l’installation, sauf l’appel de vérification au modèle que `setup` fait avec la CLI et le compte de la personne (`--no-live` le saute), et ne traite aucune donnée métier. Les prompts, le code et les données que voit l’agent partent chez le fournisseur du modèle selon le contrat de la CLI choisie (compte Google, Gemini Code Assist, Vertex AI, OpenAI) : c’est ce contrat qui régit leur traitement, pas le kit.

## Cadres de référence

| Cadre | Nature | Ce qu’il vise |
| --- | --- | --- |
| Règlement européen sur l’IA (AI Act) | règlement, obligatoire dans l’UE | surtout les fournisseurs de modèles et les systèmes à haut risque ; pour tous les déployeurs, une obligation de maîtrise de l’IA par le personnel |
| NIST AI RMF | cadre volontaire de gestion des risques | quatre fonctions : gouverner, cartographier, mesurer, gérer |
| ISO/IEC 42001 | norme de système de management de l’IA | certifie une organisation, jamais un outil |

Un assistant de code n’entre pas, en principe, dans les usages à haut risque de l’AI Act. La qualification dépend de l’usage réel et doit être confirmée par l’organisation.

## Ce que le kit apporte

| Thème | Ce que fait le kit | Où le vérifier |
| --- | --- | --- |
| Supervision humaine | la personne lance chaque commande ; l’agent ne commite, ne pousse, ne déploie et ne lance un `apply` d’infrastructure qu’avec son accord ; la cérémonie (spec, revue complète) monte avec les enjeux | `practices/`, `commands/`, [workflow](workflow.md) |
| Garde-fous déterministes | refus d’une commande dbt sur un target de production ; refus d’écrire sous des chemins protégés déclarés par le repo ; désactivés par défaut, activés par l’organisation | `runtime/hooks/`, [garde-fous](hooks.md) |
| Revue | agents de revue en lecture seule (code, sécurité, infrastructure, architecture, SQL, dbt) et agent de doute pour les changements à enjeu | `agents/`, [agents](agents.md) |
| Permissions | aucun mode qui saute les confirmations ; le kit n’écrit jamais les permissions des CLI ni les approbations de garde-fous de Codex | test `test_invariants.py` |
| Données sur le poste | aucune télémétrie ; relevé d’usage et frictions lus et écrits en local ; aucun identifiant stocké | [revue d’usage](usage-review.md), `runtime/friction.py` |
| Authentification | jamais choisie par le kit ; seulement ce que l’organisation déclare dans `overrides.json` | [personnalisation](customization.md) |
| Traçabilité de l’installation | chaque fichier installé est suivi par empreinte ; sauvegarde avant chaque écriture ; refus d’écraser un fichier modifié à la main | `~/.ai-kit/state.json`, `~/.ai-kit/backups/` |
| Maîtrise de l’IA par le personnel | parcours « Démarrer », `/guide` qui explique quelle commande et quel niveau de cérémonie choisir, `/learn` et `/explain` pour comprendre un périmètre ou du code | [démarrer](getting-started.md), [outils](tools.md) |
| Qualité mesurée | évaluations du comportement de l’agent sur des cas fixes, rejouables à chaque changement du kit | `evals/`, [évaluations](evals.md) |
| Code ouvert | sources lisibles, licence MIT, provenance des skills repris | `LICENSE`, [sources](sources.md) |

## Ce que le kit ne fait pas

- **Pas de journal des actions de l’agent.** Les CLI tiennent leurs propres journaux de session ; le kit les lit pour le relevé d’usage, sans les conserver ni les centraliser.
- **Pas de preuve signée des revues.** Une revue par un agent produit un texte, pas une attestation vérifiable.
- **Pas de contrôle des données envoyées au modèle.** Le kit ne filtre ni le code ni les données que l’agent lit ; les règles du repo (`AGENTS.md`, chemins protégés) guident l’agent, elles ne bloquent pas la lecture.
- **Pas de gestion de parc.** Le kit ne s’impose pas aux postes, ne remonte rien et ne vérifie pas qui l’a installé.
- **Pas d’inventaire des modèles.** Le modèle utilisé dépend de la CLI et du compte ; `overrides.json` peut l’imposer, sans le garantir.

## Ce qui reste à la charge de l’organisation

1. Choisir les CLI et les contrats des fournisseurs de modèles, et vérifier ce qu’ils prévoient pour les données (conservation, entraînement, localisation).
2. Classer les données et les repos : ceux qu’un agent peut lire, ceux qui exigent une revue complète, ceux qui sont exclus.
3. Valider les pratiques entreprise et d’équipe (`practices/`), proposées comme base.
4. Activer les garde-fous utiles et déclarer les chemins protégés de chaque repo.
5. Former le personnel (parcours « Démarrer », pilote), puis suivre l’usage avec la [revue d’usage](usage-review.md).
6. Si un journal des actions ou une preuve de revue est exigé, l’obtenir de la CLI ou de la plateforme (journaux d’audit du fournisseur, revue de MR obligatoire), le kit ne le fournit pas.
