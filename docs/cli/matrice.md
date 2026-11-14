# CLI matrix

The kit content (context, commands, skills, agents, guardrails) is written once, with nothing specific to a CLI. Each CLI
receives it through its adapter (`installer/adapters/`), in the place and form it reads. This page says where.

## Status

| CLI | Adapter | Verified on | Page |
| --- | --- | --- | --- |
| Gemini CLI | integrated | 0.65 | [Gemini CLI](gemini.md) |
| Antigravity CLI (agy) | integrated | 1.4.12 | [Antigravity CLI](agy.md) |
| Codex CLI | integrated | 0.164 (files, repo skills and evals) | [Codex CLI](codex.md) |
| Claude Code | integrated | 2.1.316 (files and evals in `claude -p`) | [Claude Code](claude-code.md) |

`doctor` says when a newer CLI version than the verified one runs. `.github/workflows/cli-drift.yml` checks each week,
with `--version` and `--help` only, that the latest CLIs still offer what the kit relies on (`scripts/cli_drift.py`).

## Concept by concept

| Kit concept | Gemini CLI | Antigravity CLI (agy) | Codex CLI | Claude Code |
| --- | --- | --- | --- | --- |
| CLI folder | `~/.gemini/` | `~/.gemini/` and the plugin `~/.gemini/config/plugins/ai-kit/` | `~/.codex/` | `~/.claude/` and `~/.claude.json` |
| Context layers (`00_KIT`, `10_COMPANY`, `20_TEAM`) | copies in `~/.gemini/`, declared in `context.fileName` | included by path from the plugin's `rules/AGENTS.md` | managed block at the top of `~/.codex/AGENTS.md` | imported by path from a managed block in `~/.claude/CLAUDE.md` |
| `USER.md` (always `~/.ai-kit/context/USER.md`) | a copy in `~/.gemini/USER.md` | included by path | copied into the block | imported by path |
| Repository context | `AGENTS.md` or `GEMINI.md`, root and folders traversed | `AGENTS.md`, `GEMINI.md`, `.agents/rules/` | `AGENTS.md` (and `AGENTS.override.md`) | `AGENTS.md` when the repo has no `CLAUDE.md`; otherwise `CLAUDE.md`, and the block asks to read `AGENTS.md` |
| Kit skills | `~/.gemini/skills/<name>/` | the same | `~/.codex/skills/<name>/`, user-only honoured | `~/.claude/skills/<prefix><name>/` (`ai-kit-` by default), user-only honoured |
| Name taken by one of your skills or commands | the kit's installed as `<prefix><name>`, yours kept | the same | the same; the block says which name to type | skills always prefixed; commands only when taken |
| Your own skills | `~/.gemini/skills/<name>/` | the same | `~/.codex/skills/<name>/` | `~/.claude/skills/<name>/` |
| Repository skills | `.agents/skills/` or `.gemini/skills/`; a repo skill named like a kit skill replaces it, in a trusted folder | `.agents/skills/`; a same-name repo skill is ignored | `.agents/skills/`; both are listed, the model chooses | `.claude/skills/` (not verified) |
| Commands (`commands/<name>.md`) | `~/.gemini/commands/<name>.toml` | a command skill in the plugin (every skill is a command) | a command skill, called with `$<name>` | `~/.claude/commands/<name>.md` (`$ARGUMENTS`) |
| Override a command in a repository | `.gemini/commands/<name>.toml` | not reliable: use another name | not reliable: use another name | `.claude/commands/<name>.md` (not verified) |
| Agents | `~/.gemini/agents/ai-kit-<name>.md` | plugin `agents/` | `[agents.ai-kit-<name>]` in the managed block of `config.toml` | `~/.claude/agents/ai-kit-<name>.md` |
| Agent turn and time limits | `max_turns`, `timeout_mins` in the header | the same | the CLI's own | the CLI's own |
| Sub-agents that write at the same time, with the `parallel` setting ([parallel agents](../parallel-agents.md)) | each in a worktree the main agent creates | the same | one at a time: the sandbox refuses `git worktree add` | each in a worktree; also native (`isolation: worktree`) |
| Agent tool list (`AGENT_TOOLS`) | native | native, with agy's tool names | instruction only; the session's sandbox applies | native (`Read`, `Grep`, `Glob`, `Bash`) |
| Guardrails | `ai-kit-*` groups under `hooks.BeforeTool` | plugin `hooks.json` (`PreToolUse`) | `[[hooks.PreToolUse]]` in the block, to approve ("Trust") | groups under `hooks.PreToolUse` of `settings.json` |
| `whats-new` hook | group under `hooks.SessionStart` | plugin `hooks.json` (`SessionStart`, `injectSteps`) | `[[hooks.SessionStart]]`, to approve | group under `hooks.SessionStart` |
| `integrity` check | group under `hooks.AfterTool`; at start through `whats-new` | at session start only, through `whats-new` (its post-tool output is not documented) | `[[hooks.PostToolUse]]`, to approve; at start through `whats-new` | group under `hooks.PostToolUse`; at start through `whats-new` |
| MCP | `mcpServers` of `settings.json` | plugin `mcp_config.json` | `[mcp_servers.ai-kit-<name>]` in the block | `ai-kit-<name>` in `mcpServers` of `~/.claude.json` |
| Permissions | the CLI's approval mode | each person's rules, never written by the kit | sandbox and approvals, never set by the kit | the CLI's own modes and rules, never set by the kit |
| Logs read by `usage` | `~/.gemini/tmp/*/chats/*.json` | `~/.gemini/antigravity-cli/history.jsonl`, `conversations/*.db` (read-only) | `~/.codex/history.jsonl`, `~/.codex/sessions/**/rollout-*.jsonl` | `~/.claude/projects/*/*.jsonl` |
| What `usage` observes (`OBSERVES`) | commands, skills activated, agents, errors | commands, skill files read, agents | commands, skill files read, agents, errors | commands, skills called, agents, errors |
| Real call by `doctor --live` | `gemini -p` | `agy -p` | `codex exec`, read-only, ephemeral | `claude -p` |
| Evals | `--cli gemini` | `--cli agy` | `--cli codex` | `--cli claude` |
| Model and authentication | never set by the kit | never set by the kit | never set by the kit | never set by the kit |

**Copies and paths.** The layers and `USER.md` always live in `~/.ai-kit/context/`. agy and Claude Code read them by path,
so an edit counts at the next session. Gemini CLI reads only files in `~/.gemini` and Codex cannot include a file: they get
a copy at each activation, so after editing `USER.md` by hand run `ai-kit sync --offline`. A copy edited by hand is never
lost: the edit goes into `USER.md` when the file did not change since the copy, otherwise it is in the backup. A `USER.md`
that seems to hold a secret, or is not plain UTF-8, is never copied.

**Chosen CLIs.** `ai-kit init --target` records the CLIs (`auto`, `gemini`, `agy`, `codex`, `claude`, `both` for Gemini
CLI and agy, `all`); later activations keep them. Removing a CLI from the choice removes what the kit put there and keeps
the person's own settings.

## Known limits of the CLIs

- **User-only skills**: Claude Code and Codex hide them from the model, and Claude Code refuses them in its Skill tool, so
  no command chains one; Gemini CLI and agy have no such field and may activate them on their own.
- **Codex**: commands are typed `$intent`; `USER.md` is a copy; guardrails need one approval ("Trust"); an agent role has
  no tool list.
- **Claude Code**: it rewrites `~/.claude.json` while running: close it before an activation that changes MCP.
- **agy**: `usage` sees no error events; its conversation files are an undocumented format, skipped if unreadable.

## Add a CLI

A module in `installer/adapters/`, added to `ADAPTERS`, following the `Adapter` contract of `installer/interface.py`
(including `AGENT_TOOLS`, `OBSERVES`, `VERIFIED`, and `live` for `doctor --live`), its scenarios in `tests/snapshot.py`, its
column above and its page here. It must know where each row above goes, how the CLI loads `~/.ai-kit/context/` (by path,
or a copy at each activation), the form of a command, and how the CLI passes a tool call to a guardrail script.
