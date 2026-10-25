# Couche projet

Le kit prépare le poste ; le repo porte son propre contexte. L’agent lit, après les couches globales, l’`AGENTS.md` du repo et des dossiers traversés (et les fichiers propres à sa CLI, voir la [matrice](cli/matrice.md)). C’est là que se jouent les règles métier, les commandes et les surcharges de préférences.

## Fichiers attendus dans un repo

| Fichier | Rôle | Tenu par |
| --- | --- | --- |
| `AGENTS.md` | table des matières courte : démarrer, tester, données, conventions, où est le reste | `writing-for-agents` |
| `GLOSSARY.md` | un terme, une définition, les synonymes à éviter | `domain-modeling` |
| `docs/adr/NNNN-slug.md` | décisions coûteuses à défaire, surprenantes sans contexte, issues d’un vrai arbitrage | `domain-modeling` |
| `REVIEW.md` | passes de revue, sens d’Important, plafond de nits | `init-project-context`, `/review` |
| `docs/sdlc/<date>-<slug>/` | `intent.md`, `spec.md`, `plan.md` d’un changement ; un dossier par changement ; `spec.md` versionné, `intent.md` et `plan.md` locaux (`.gitignore`) | `/intent`, `/spec`, `/build` |
| `docs/agents/issue-tracker.md` | gestionnaire de tickets et labels de triage, seulement quand `setup-workflow` a été lancé | `setup-workflow`, `/map`, `/triage` |
| `.agents/skills/<nom>/` | skills propres au repo, prioritaires sur le kit à nom égal | l’équipe du repo |

Un repo qui a déjà un fichier de contexte propre à une CLI le garde ; il y renvoie vers `AGENTS.md` pour éviter la duplication (une ligne `@AGENTS.md`, par exemple ; voir la page de la CLI dans la [matrice](cli/matrice.md)).

## Première mise en place

Dans le repo, demander « Initialise le contexte du projet ». Le skill `init-project-context` lit le repo, propose `AGENTS.md`, `GLOSSARY.md` et `REVIEW.md` à partir de ses gabarits, propose les lignes de `.gitignore` pour `intent.md` et `plan.md`, attend une confirmation par fichier et ne remplace jamais un fichier existant. Il ne copie pas les gabarits d’artefacts dans le repo et ne crée pas d’ADR vide : le dossier `docs/adr/` apparaît avec la première décision.

## Monorepo : plusieurs équipes, un repo

Un repo partagé par plusieurs équipes (par exemple un projet dbt commun à la finance et au marketing) s’organise en zones : la racine porte ce qui est commun, chaque dossier d’équipe porte ce qui lui est propre.

| Où | Quoi | Propriétaire |
| --- | --- | --- |
| racine | `AGENTS.md` commun (dont « Verifying your work »), `REVIEW.md`, `.ai-kit/protected-paths`, `GLOSSARY.md` commun ou `GLOSSARY-MAP.md` | l’équipe qui tient la plateforme |
| `<zone>/` | `AGENTS.md` de la zone, son glossaire si elle en a un, ses artefacts dans `<zone>/docs/sdlc/` | l’équipe de la zone |

- **Lancer l’agent depuis le dossier de sa zone** (`cd finance` puis la CLI). Il lit alors l’`AGENTS.md` de la racine et celui de la zone. Lancé à la racine, il demande dans quelle zone on travaille.
- **Les vérifications** suivent la règle générale : ce qui a changé et ce qui en dépend, quelle que soit l’équipe. `/test`, `/review` et `/ship` nomment les autres zones touchées (pour dbt, les modèles qui dépendent des modèles modifiés), pour que leurs propriétaires relisent. Avec un manifest de production, `dbt build --select state:modified+ --defer --state <manifest>` ne reconstruit que ce qui a changé et lit le reste depuis la production.
- **Les chemins protégés** de la racine s’appliquent aussi quand l’agent est lancé dans une zone ; une zone peut ajouter son propre `.ai-kit/protected-paths`.
- **Un indicateur partagé** a une seule définition, dans le glossaire commun, avec un propriétaire nommé ; les glossaires de zone y renvoient.
- **Les skills de repo** vivent dans `.agents/skills/` à la racine et valent pour tout le monde : les préfixer par la zone (`finance-cloture-mensuelle`) et dire dans leur description à quoi ils s’appliquent.
- **Trop de contexte** : lancé à la racine, l’agent peut lire aussi les `AGENTS.md` des sous-dossiers ; chaque CLI a son moyen de limiter ce qu’il parcourt (voir sa page).
- **Qui relit quoi** : un fichier `CODEOWNERS` le fait respecter par GitLab ou GitHub.

```
# CODEOWNERS
/AGENTS.md            @equipe/plateforme
/REVIEW.md            @equipe/plateforme
/.ai-kit/             @equipe/plateforme
/finance/             @equipe/finance
/marketing/           @equipe/marketing
```

## Surcharger les préférences

Pour qu’un projet impose une règle différente de `30_USER.md` (langue, niveau de détail, workflow), l’écrire dans `AGENTS.md` sous le même titre que dans le fichier personnel. `00_KIT.md` indique à l’agent que le projet l’emporte.

## Ce que le kit ne fait pas

Il n’écrit pas dans les repos, ne pousse rien et ne crée pas de MR. Les skills écrivent les artefacts à la demande ; un commit n’a lieu que si la personne l’a accepté dans la session (`/build` le demande une fois) ; rien n’est poussé.
