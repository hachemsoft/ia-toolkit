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

**Skills du socle** : repris d’un dépôt amont sous licence MIT, adaptés et redistribués avec leur licence (`skills/LICENSE-UPSTREAM-MIT`) ; provenance dans `skills/upstream.lock.json`. Les playbooks métier sont propres au kit.

**Catalogues tiers à évaluer**, non redistribués :
- https://github.com/dbt-labs/dbt-agent-skills
- https://github.com/google/skills
