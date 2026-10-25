# Kit IA
Profil : {profile}
Ce contexte s’applique aux activités professionnelles de l’équipe. Il est chargé dans tous les projets.

## Priorité entre les couches
1. Les pratiques entreprise et d’équipe (fichiers 10 et 20) s’appliquent par défaut ; pour y déroger, la personne le demande explicitement et la dérogation est notée dans la réponse.
2. Le fichier 30_USER.md ajuste la forme des réponses et le workflow par défaut.
3. Les instructions du projet courant (GEMINI.md, AGENTS.md, docs du repo) l’emportent sur 30_USER.md en cas de conflit.
4. Une demande explicite dans la conversation l’emporte sur 30_USER.md.

## Langue
Répondre dans la langue de la personne. Les titres de sections des artefacts (intent.md, spec.md, plan.md, REVIEW.md) restent en anglais, comme dans les gabarits ; leur contenu est dans la langue de l’équipe.

## Commandes
La cérémonie suit les enjeux : une retouche se fait sans artefact, une fonctionnalité passe par les étapes, la production exige la revue complète. `/guide` aide à choisir.
Seules les commandes ci-dessous sont installées pour ce profil. Ne jamais en proposer une autre ; si une commande absente conviendrait, dire qu’elle s’active d’une ligne (`extra_commands` dans `~/.ai-kit/overrides.json`, puis `update`).
{commands}

## Playbooks métier
Activés automatiquement quand la tâche s’y prête ; `/intent`, `/build`, `/diagnose` et `/learn` les enchaînent.
{playbooks}

## Lire les skills du socle
Les skills de workflow sont repris tels quels d’un socle écrit pour d’autres outils. Correspondance à appliquer sans le dire :
- « Skill tool », « call the skill », « activate the X skill » : l’outil d’activation de skill, jamais `invoke_agent` (un skill n’est pas un agent). Si cet outil est absent, suivre les consignes de la commande sans chercher d’agent du même nom.
- « sub-agent », « background agent », « dispatch » : utiliser les agents `ai-kit-*` installés ; sinon faire le travail soi-même, dans la conversation.
- `CLAUDE.md` : lire et écrire `AGENTS.md` (ou `GEMINI.md` si le repo l’utilise). Ne jamais créer de `CLAUDE.md`.
- « PR », « pull request » : merge request (MR) ; « GitHub » : le gestionnaire de tickets et de dépôt déclaré par le repo (`docs/agents/issue-tracker.md`), sans en supposer un.
- `/setup-workflow`, `/pr`, `/tdd`, `/code-review`, `/implement-spec` : les skills `setup-workflow`, `mr`, `tdd`, `code-review`, `implement-spec`, pas des commandes.
- Un skill dont l’en-tête porte `disable-model-invocation: true` ne s’active que si la personne tape sa commande ou le demande nommément.
- Un script bash proposé par un skill : sur Windows, donner l’équivalent PowerShell ou les étapes manuelles.

## Artefacts et git
Un dossier par changement : `docs/sdlc/<AAAA-MM-JJ>-<slug>/`. `spec.md` et `REVIEW.md` sont versionnés (contrat relu dans la MR). `intent.md` et `plan.md` sont des notes de travail locales, ignorées par git, sauf règle contraire dans `AGENTS.md`. Ne jamais commiter sans l’accord de la personne.

{frictions}Lire le contexte du projet courant avant d’agir ; ne pas inventer ses règles métier. Monorepo : lancé à la racine d’un repo dont des sous-dossiers ont leur propre AGENTS.md, demander d’abord dans quelle zone on travaille ; dans une zone, suivre son AGENTS.md et écrire ses artefacts dans `<zone>/docs/sdlc/`.
