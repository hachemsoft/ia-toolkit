# Références

Documentation des CLI prises en charge, à relire quand une version change. Les versions vérifiées sont dans la [matrice des CLI](cli/matrice.md) ; les politiques administrées d’une organisation peuvent changer le comportement, d’où une recette sur la version utilisée en interne.

**Gemini CLI**
- Contexte (`GEMINI.md`, `context.fileName`) : https://geminicli.com/docs/cli/gemini-md/
- Skills : https://geminicli.com/docs/cli/skills/
- Sous-agents : https://geminicli.com/docs/core/subagents/
- Configuration : https://geminicli.com/docs/reference/configuration/
- MCP : https://geminicli.com/docs/tools/mcp-server/

**Antigravity CLI** : documentation intégrée (`agy --help`, `agy plugin validate`) ; ce que le kit en utilise est décrit dans [Antigravity CLI](cli/agy.md).

**Codex CLI** : https://developers.openai.com/codex/ (contexte `AGENTS.md`, `config.toml`, skills, hooks) ; ce que le kit en utilise est décrit dans [Codex CLI](cli/codex.md).

## Inspirations

- **Workflow** : [« The AI-native SDLC playbook »](https://claude.com/fr/resources/articles/the-ai-native-sdlc-playbook), Anthropic. Six étapes (Plan, Design, Build, Test, Deploy, Maintain), chacune close par un artefact versionné que l’étape suivante lit : `intent.md`, `spec.md`, `plan.md`, le diff et ses tests, la MR et ses constats de revue, le rapport d’incident qui redevient un `intent.md`.
- **Skills du socle** : [mattpocock/skills](https://github.com/mattpocock/skills), Matt Pocock, licence MIT. Repris et adaptés (en anglais, `pr` devient `mr`, deux skills renommés), redistribués avec leur licence (`skills/LICENSE-UPSTREAM-MIT`) ; provenance dans `skills/upstream.lock.json`. D’eux vient l’effort en amont : entretien, glossaire, ADR, skills petits et composables.
- **Discipline des skills** : [agent-skills](https://github.com/addyosmani/agent-skills), Addy Osmani. Tables d’excuses (anti-rationalisation) dans chaque playbook, revue adverse par un agent de doute (`/review full`), un verbe par étape.
- **pstack** : [cursor/plugins › pstack](https://github.com/cursor/plugins/tree/main/pstack).
- **Comparaison des packs de skills** par Switch Dimension : la cérémonie suit les enjeux, chaque skill installé a un coût de contexte, d’où la revue d’usage.

Les playbooks métier (Java, infrastructure, architecture, Data) et l’installeur sont propres au kit.

**Catalogues tiers à évaluer**, non redistribués :
- https://github.com/dbt-labs/dbt-agent-skills
- https://github.com/google/skills
