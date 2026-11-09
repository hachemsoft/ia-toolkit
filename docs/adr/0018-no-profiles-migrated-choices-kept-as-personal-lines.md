---
status: accepted
since: 4.0.0
---
# No profiles: the Core is the base, a Team chooses, a person adds or removes

The engine knows no profile and no bundle other than a Team.

- **Core default** (`aikit-default: "true"`, and every command without `default: false`): what everyone needs, 14 commands,
  19 skills and 4 agents (repo-investigator, verifier, doubter, code-reviewer). The list is generated into
  `docs/getting-started.md` by `scripts/selection_table.py`.
- **Core optional** (`aikit-default: "false"`, shipped in the Core): generic method tools, the domain playbooks and the
  specialised review agents.
- **Team**: a Git repository whose `aikit.toml` `[defaults]` turns optional resources on (`extra_*`) or off (`disabled_*`),
  with its own skills, agents, context and MCP servers.
- **Person**: `[user] extra_*` and `disabled_*` in `~/.ai-kit/aikit.toml`, resource by resource. `USER.md` is read by the
  agent, never by the engine for the selection.

**Why**: a profile selected skills, agents, commands and MCP names, while its practices were identical everywhere; named
bundles per job would rebuild that layer. A per-resource choice is not a profile. Keeping domain playbooks in the Core as
optional lets a person without a Team still get them, and teams do not fork the same public files.

**Consequences**: `NEWS.md` entries target teams (`teams:`), frictions record the team, and the rendered context names no
profile. `ai-kit validate` refuses a content tree that still holds `profiles/`, `practices/` or `organization.toml`.

**Considered**: install everything for everyone (dozens of skill descriptions on every turn, domain triggers in unrelated
repos; acceptable for a pilot); public Team templates per job (profiles under another name; a copyable example,
`examples/team-repo/`, is enough).
