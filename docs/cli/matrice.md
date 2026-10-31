# CLI matrix

The kit content (practices, skills, commands, agents, guardrails) is written once, with nothing specific to any CLI. Each CLI receives it through its adapter, in the place and form it reads. This page says where, CLI by CLI. To plug in a new one, fill in its column: that is the specification for its adapter.

## Status of each CLI

| CLI | Adapter | Verified on | Page |
| --- | --- | --- | --- |
| Gemini CLI | ✅ integrated | 0.65 | [Gemini CLI](gemini.md) |
| Antigravity CLI (agy) | ✅ integrated | 1.4.12 | [Antigravity CLI](agy.md) |
| Codex CLI | ✅ integrated | 0.160 | [Codex CLI](codex.md) |
| Claude Code | ✅ integrated | 2.1.316 (files; session checks to do) | [Claude Code](claude-code.md) |
| GitHub Copilot CLI | ❌ no adapter | — | — |

A CLI without an adapter can already read the kit's repository files (`AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`) if it reads `AGENTS.md`, but it has none of the kit's global layers, commands, skills or guardrails.

## Concept by concept

| Kit concept | Gemini CLI | Antigravity CLI (agy) | Codex CLI | Claude Code |
| --- | --- | --- | --- | --- |
| CLI folder | `~/.gemini/` | `~/.gemini/` (also read by agy) and `~/.gemini/config/plugins/ai-kit/` | `~/.codex/` | `~/.claude/` and `~/.claude.json` |
| Context layers (`00_KIT`, `10_COMPANY`, `20_TEAM`) | files in `~/.gemini/`, declared in `context.fileName` of `settings.json` | included by path from the plugin's `rules/AGENTS.md` | managed block at the top of `~/.codex/AGENTS.md` | imported by path from the managed block at the top of `~/.claude/CLAUDE.md` |
| Personal context `30_USER.md` | `~/.gemini/30_USER.md`, declared in `context.fileName` | included by path from the plugin | copied into that block on every `update` | imported by path from that block (no copy) |
| Repository context | `AGENTS.md` or `GEMINI.md`, at the root and in the folders traversed | `AGENTS.md`, `GEMINI.md`, `.agents/rules/` | `AGENTS.md` (and `AGENTS.override.md`), at the root and in the folders | `CLAUDE.md` only: the block asks to read `AGENTS.md`; a one-line `CLAUDE.md` `@AGENTS.md` can load it |
| Kit skills | `~/.gemini/skills/<name>/SKILL.md` | the same (`~/.gemini/skills/`) | `~/.codex/skills/<name>/SKILL.md`, "on command only" honored (`agents/openai.yaml`) | `~/.claude/skills/<prefix><name>/SKILL.md` (`ai-kit-` by default, `skill_prefix`), "on command only" honored |
| Name already taken by one of your skills or commands | the kit's is installed as `<prefix><name>`, yours kept; the kit's texts name it so | the same | the same; the kit block says which name to type (`$<prefix><name>`) | always prefixed for skills; the same for commands |
| Your own skills (personal, any name the kit does not install) | `~/.gemini/skills/<name>/SKILL.md` | the same (`~/.gemini/skills/`) | `~/.codex/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/SKILL.md`, kept next to the kit's prefixed ones |
| Repository skills | `<repo>/.agents/skills/` or `<repo>/.gemini/skills/`; loaded last, so a repo skill named like a kit or personal skill replaces it, only in a trusted folder (verified on 0.65) | `<repo>/.agents/skills/`; a repo skill named like a kit or personal skill is ignored, the kit's is kept (verified) | `<repo>/.agents/skills/`; a repo skill named like a kit skill does not replace it: both are listed to the model, which chooses (verified on 0.164) | `<repo>/.claude/skills/` (not verified) |
| Commands (`commands/<name>.md`) | `~/.gemini/commands/<name>.toml` | a command skill in the plugin, `~/.gemini/config/plugins/ai-kit/skills/<name>/` (in agy, every skill is a command) | a command skill, called with `$<name>` | `~/.claude/commands/<name>.md` (`$ARGUMENTS`); `<prefix><name>` when one of your skills or commands has the name |
| Override a command in a repository | `<repo>/.gemini/commands/<name>.toml` | not reliable: a repo skill named like the command skill does not replace it (see the line above); give the repo skill another name | not reliable: both are listed (see the line above); give the repo skill another name | `<repo>/.claude/commands/<name>.md` (not verified) |
| Agents | `~/.gemini/agents/ai-kit-<name>.md` | plugin `agents/` | `[agents.ai-kit-<name>]` in the managed block of `config.toml` | `~/.claude/agents/ai-kit-<name>.md` |
| Agent tool list (`AGENT_TOOLS`) | native: the header's `tools` are the only tools | native: `tools` in the header, with agy's tool names (`view_file`, `grep_search`, `list_dir`, `run_command`) | instruction only: a role has no tool list in Codex; the session's sandbox and approvals apply | native: `tools` in the header (`Read`, `Grep`, `Glob`, `Bash`) |
| Guardrails | `ai-kit-*` groups under `hooks.BeforeTool` of `settings.json` | plugin `hooks.json` (`PreToolUse`) | `[[hooks.PreToolUse]]` in that block, to approve in Codex ("Trust") | groups under `hooks.PreToolUse` of `~/.claude/settings.json`, next to your own hooks; no approval step |
| Repository protected paths | `<repo>/.ai-kit/protected-paths`, read by the kit script | the same file, read by the same script | the same file, read by the same script | the same file, read by the same script |
| MCP | `mcpServers` of `settings.json` | plugin `mcp_config.json` | `[mcp_servers.ai-kit-<name>]` in that block | `ai-kit-<name>` entries in `mcpServers` of `~/.claude.json` |
| Permissions | Gemini approval mode | each person's rules in `~/.gemini/antigravity-cli/settings.json`, never written by the kit | Codex sandbox and approvals, never set by the kit | Claude Code's own permission modes and rules, never set by the kit |
| Logs read by `usage` | `~/.gemini/tmp/*/chats/*.json` | `~/.gemini/antigravity-cli/history.jsonl` and `conversations/*.db` (read-only) | `~/.codex/history.jsonl` and `~/.codex/sessions/**/rollout-*.jsonl` | `~/.claude/projects/*/*.jsonl` |
| What `usage` can observe (`OBSERVES`) | prompts, so commands; skills activated; agents called; errors | prompts, so commands; skill files read; agents called (no error events) | prompts, so commands; skill files read; agents called; errors | prompts, so commands; skills called; agents called; errors |
| Real call by `doctor --live` | `gemini -p` | `agy -p` | `codex exec`, read-only and ephemeral | `claude -p` |
| Evals | `evals/run.py --cli gemini` | `evals/run.py --cli agy` | `evals/run.py --cli codex` | `evals/run.py --cli claude` |
| Model | never set by the kit (`/model`); agents inherit the session model | never set by the kit | never set by the kit | never set by the kit (`/model`) |
| Authentication | never set by the kit (`/auth`); what a version before 0.36 wrote stays | never (see [the agy page](agy.md#authentication-google-account-or-google-cloud-project)) | never (`codex login`) | never (`/login`) |
| Detailed page | [Gemini CLI](gemini.md) | [Antigravity CLI](agy.md) | [Codex CLI](codex.md) | [Claude Code](claude-code.md) |

**Where the layers and `30_USER.md` live.** Gemini imports only files located in `~/.gemini` (verified on 0.65). When Gemini is installed, the layers and `30_USER.md` are therefore in `~/.gemini/`, and agy, Codex and Claude Code read them from there. Without Gemini (`--target codex`, `--target agy`, or a workstation where only another CLI is detected), they are in `~/.ai-kit/context/`, and no `~/.gemini` folder is created for Codex. If the location changes (another CLI chosen), the version in effect is the one at the location recorded by the previous installation, whatever other copies exist or their dates: it is copied to the new place; a different copy already there is kept beside it as `30_USER.md.before-<date>`, and the installer names the file in effect. The old one is never deleted. A `30_USER.md` that seems to hold a secret, or is not plain UTF-8 text, is never copied (neither to a new place nor into the Codex block): the source stays as it is, the last valid copy stays in place, and the installer says why. `doctor` shows the file in effect.

**Chosen CLIs.** The CLIs chosen at setup are recorded and kept by every `update`, whatever folders exist on the machine. Removing a CLI from the choice removes what the kit had put there (files, settings entries, managed blocks, kit references in `context.fileName`) and keeps the person's own settings.

## Known limits of the CLIs

What remains different comes from the CLIs themselves, not from a part of the kit left undone:

- **Codex**: commands are skills, typed `$intent` (Codex has no custom `/` commands); `30_USER.md` is copied into the block (Codex does not import files), so a change needs an `update`; the guardrails must be approved once in Codex ("Trust"); an agent role has no tool list.
- **Gemini and agy**: "on command only" is an instruction in the skill's description; these CLIs have no field for it.
- **Claude Code**: it rewrites `~/.claude.json` while running, so close it before an `update` that changes MCP; it reads `CLAUDE.md`, not `AGENTS.md` (the block asks it to, and a one-line `CLAUDE.md` makes it automatic).
- **agy**: `usage` sees no error events; its conversation files are an undocumented format, read read-only and skipped if they change.

## Add a CLI

A new CLI is a module in `installer/adapters/`, added to the `ADAPTERS` list, that follows the `Adapter` contract of `installer/interface.py`, plus its column in the table above and its scenarios in `tests/snapshot.py`. What this adapter must know how to do: where to write each row above, how the CLI loads a global context without copying `30_USER.md`, in what form it receives a command, and how it passes a tool call to a guardrail script (the JSON it sends and the response it expects).
