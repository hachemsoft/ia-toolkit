# References

Documentation for the supported CLIs, to reread when a version changes. The verified versions are in the [CLI matrix](cli/matrice.md). An organization's managed policies can change the behavior, hence acceptance testing on the version used internally.

**Gemini CLI**
- Context (`GEMINI.md`, `context.fileName`): https://geminicli.com/docs/cli/gemini-md/
- Skills: https://geminicli.com/docs/cli/skills/
- Subagents: https://geminicli.com/docs/core/subagents/
- Configuration: https://geminicli.com/docs/reference/configuration/
- MCP: https://geminicli.com/docs/tools/mcp-server/

**Antigravity CLI**: built-in documentation (`agy --help`, `agy plugin validate`); what the kit uses from it is described in [Antigravity CLI](cli/agy.md).

**Codex CLI**: https://developers.openai.com/codex/ (`AGENTS.md` context, `config.toml`, skills, hooks); what the kit uses from it is described in [Codex CLI](cli/codex.md).

## Inspirations

- **Workflow**: ["The AI-native SDLC playbook"](https://claude.com/resources/articles/the-ai-native-sdlc-playbook), Anthropic. Six steps (Plan, Design, Build, Test, Deploy, Maintain), each closed by a versioned artifact that the next step reads: `intent.md`, `spec.md`, `plan.md`, the diff and its tests, the merge request (MR) and its review findings, the incident report that becomes an `intent.md` again.
- **Core skills**: [mattpocock/skills](https://github.com/mattpocock/skills), Matt Pocock, MIT licence. Taken and adapted (in English, `pr` becomes `mr`, two skills renamed), redistributed with their licence (`skills/LICENSE-UPSTREAM-MIT`); provenance in `skills/upstream.lock.json`. From them comes the upfront effort: interview, glossary, ADR, small composable skills.
- **Skill discipline**: [agent-skills](https://github.com/addyosmani/agent-skills), Addy Osmani. Rationalization tables (anti-rationalization) in each playbook, adversarial review by a doubter agent (`/review full`), one verb per step.
- **pstack**: [cursor/plugins › pstack](https://github.com/cursor/plugins/tree/main/pstack).
- **Comparison of skill packs** by Switch Dimension: ceremony matches the stakes, and each installed skill has a context cost, hence the usage review.

The domain playbooks (Java, infrastructure, architecture, Data) and the installer are specific to the kit.

**Third-party catalogs to evaluate**, not redistributed:
- https://github.com/dbt-labs/dbt-agent-skills
- https://github.com/google/skills
