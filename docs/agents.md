# Agents

A skill describes a procedure. An agent receives a bounded mission in a separate context and returns its findings to the parent. The kit uses each CLI's native sub-agents; it does not impose a delegation or parallel-agent workflow.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

| Agent | Default profiles | Mission |
| --- | --- | --- |
| `ai-kit-repo-investigator` | all | Understand the repo's flows and dependencies |
| `ai-kit-verifier` | all | Run the checks declared by the repo and report, without fixing |
| `ai-kit-doubter` | all except Data Analyst (with `/review full`) | Read-only adversarial review: doubt every claim of the change, look for evidence or a counter-example |
| `ai-kit-code-reviewer` | General, Java Developer, Architect, Data Developer | Code review: contracts, exceptions, compatibility and regressions |
| `ai-kit-security-reviewer` | Java Developer, DevOps | Secrets, injections, access control, permissions and exposure, dependencies |
| `ai-kit-infra-reviewer` | DevOps | Blast radius of an infrastructure or pipeline change: deletions, permissions, versions, rollback |
| `ai-kit-architecture-reviewer` | Architect | Architecture proposal or ADR: options, criteria, consequences, consistency with existing decisions |
| `ai-kit-sql-reviewer` | Data Analyst, Data Developer | Grain, joins, aggregations, dates and NULL |
| `ai-kit-dbt-reviewer` | Data Analyst, Data Developer | dbt models, incremental logic, tests and documentation |

## Usage

After setup or update, restart the CLI, then list the agents with its command (see its page: [Gemini CLI](cli/gemini.md), [Antigravity CLI](cli/agy.md), [Codex CLI](cli/codex.md), [Claude Code](cli/claude-code.md)).

Examples:

```text
@ai-kit-repo-investigator Explain the path of this data through the repo.
@ai-kit-code-reviewer Review this change; here is the diff and the expected criteria: ...
@ai-kit-sql-reviewer Review models/marts/ventes.sql and its grain.
@ai-kit-dbt-reviewer Examine the replay risks of this incremental model.
@ai-kit-infra-reviewer Review this Terraform plan: deletions, permissions, rollback.
@ai-kit-architecture-reviewer Review this ADR and its options.
```

The agent can also choose to delegate based on the description. These instructions guide the model; they do not guarantee an invocation. Availability depends on the CLI version and company policies. The kit forces no sub-agent activation setting; `doctor` reports when they are disabled.

## Tools and limits

Review agents are read-only: they read and search files, without modifying or running anything. `ai-kit-verifier` is the exception: it can also list folders and run commands, because its role is to run the check commands declared in `AGENTS.md` (build, tests, lint, `dbt test` on the development target) and report their real output at the end of a `/build`. It fixes nothing; the `dbt-prod-guard` guardrail also applies to it. They propose checks to the main agent.

How far the tool list holds depends on the CLI (the `AGENT_TOOLS` contract of each adapter, [matrix](cli/matrice.md)):

| CLI | Agent tool list | What it means |
| --- | --- | --- |
| Gemini CLI | native | the agent only gets the tools listed in its header: a reviewer cannot write or run the shell |
| Antigravity CLI | instruction | the header carries the list, but agy applying it is not verified: the prompt says "read only", nothing technical prevents a write |
| Codex CLI | instruction | a role holds instructions only; the session's sandbox and approvals apply, as for the main agent |
| Claude Code | native | the agent only gets the tools in its header (`Read`, `Grep`, plus `Glob` and `Bash` for the verifier) |

Where it is only an instruction, the kit never claims a reviewer cannot write: the prompt asks it, the CLI's sandbox and approvals are the barrier. The parent must provide the diff or relevant results when they are not accessible.

Company and team practices are included in their prompt at install time: we do not assume an isolated agent receives the parent's full context. Personal context (`30_USER.md`) is not copied there: it shapes the parent's answers, not the delegated mission. Project instructions must be read and missing facts reported. Skills are not assumed to be automatically available in sub-agents. When a base skill mentions a "sub-agent" or "background agent", `00_KIT.md` tells the model to use these `ai-kit-*` agents, or to do the work itself if they are absent.

Agents inherit the model of the session: the kit names no model. Each agent has a limit of 12 turns and 5 minutes, except the verifier (15 turns, 10 minutes), which must leave time for tests to run. Delegation adds model calls and can increase latency and usage: keep it for missions that benefit from this separation.

Future access to an MCP server must use explicitly allowed tools and be validated for each agent. Do not widen to `*` to fix a configuration problem.

## Layout

- `agents/catalog.json`: shared catalog.
- `agents/internal/<category>/<name>.json`: role and instructions, independent of any CLI.
- `agents/defaults.json`: default tools and settings, shared by all CLIs.
- `profiles/*.json`: agents selected per role.
- Output: one file per agent, in the format and location each CLI reads: `ai-kit-<name>.md` for Gemini and agy, `~/.codex/ai-kit/agents/<name>.toml` declared in `config.toml` for Codex, `~/.claude/agents/ai-kit-<name>.md` for Claude Code ([matrix](cli/matrice.md)).

The installer generates the files, records them in its state, protects local modifications and removes old untouched outputs when the profile changes.

Customization in `~/.ai-kit/overrides.json`: add `extra_agents` and `disabled_agents` as lists of catalog names (without the ai-kit prefix). Keep the file's other keys.

Repo-specific agents stay in that repo (`.agents/`). The same agents are installed in the Antigravity plugin; see [agy](cli/agy.md).

Formats and checks specific to each CLI: see its page. Whether an agent is actually invoked always depends on the model.
