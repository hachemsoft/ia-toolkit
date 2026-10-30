# CLI matrix

The kit content (practices, skills, commands, agents, guardrails) is written once, with nothing specific to any CLI. Each CLI receives it through its adapter, in the place and form it reads. This page says where, CLI by CLI. To plug in a new one, fill in its column: that is the specification for its adapter.

## Status of each CLI

| CLI | Adapter | Verified on | Page |
| --- | --- | --- | --- |
| Gemini CLI | ✅ integrated | 0.65 | [Gemini CLI](gemini.md) |
| Antigravity CLI (agy) | ✅ integrated | 1.4.7 | [Antigravity CLI](agy.md) |
| Codex CLI | ✅ integrated | 0.160 | [Codex CLI](codex.md) |
| Claude Code | ❌ no adapter | — | — |
| GitHub Copilot CLI | ❌ no adapter | — | — |

A CLI without an adapter can already read the kit's repository files (`AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`) if it reads `AGENTS.md`, but it has none of the kit's global layers, commands, skills or guardrails.

## Concept by concept

| Kit concept | Gemini CLI | Antigravity CLI (agy) | Codex CLI |
| --- | --- | --- | --- |
| CLI folder | `~/.gemini/` | `~/.gemini/` (also read by agy) and `~/.gemini/config/plugins/ai-kit/` | `~/.codex/` |
| Context layers (`00_KIT`, `10_COMPANY`, `20_TEAM`) | files in `~/.gemini/`, declared in `context.fileName` of `settings.json` | included by path from the plugin's `rules/AGENTS.md` | managed block at the top of `~/.codex/AGENTS.md` |
| Personal context `30_USER.md` | `~/.gemini/30_USER.md`, declared in `context.fileName` | included by path from the plugin | copied into that block on every `update` |
| Repository context | `AGENTS.md` or `GEMINI.md`, at the root and in the folders traversed | `AGENTS.md`, `GEMINI.md`, `.agents/rules/` | `AGENTS.md` (and `AGENTS.override.md`), at the root and in the folders |
| Kit skills | `~/.gemini/skills/<name>/SKILL.md` | the same (`~/.gemini/skills/`) | `~/.codex/skills/<name>/SKILL.md`, "on command only" honored (`agents/openai.yaml`) |
| Your own skills (personal, any name the kit does not install) | `~/.gemini/skills/<name>/SKILL.md` | the same (`~/.gemini/skills/`) | `~/.codex/skills/<name>/SKILL.md` |
| Repository skills | `<repo>/.agents/skills/` or `<repo>/.gemini/skills/`; loaded last, so a repo skill named like a kit or personal skill replaces it, only in a trusted folder (verified on 0.65) | `<repo>/.agents/skills/`; a repo skill named like a kit or personal skill is ignored, the kit's is kept (verified) | `<repo>/.agents/skills/`; a repo skill named like a kit skill does not replace it: both are listed to the model, which chooses (verified on 0.164) |
| Commands (`commands/<name>.md`) | `~/.gemini/commands/<name>.toml` | a command skill in the plugin, `~/.gemini/config/plugins/ai-kit/skills/<name>/` (in agy, every skill is a command) | a command skill, called with `$<name>` |
| Override a command in a repository | `<repo>/.gemini/commands/<name>.toml` | not reliable: a repo skill named like the command skill does not replace it (see the line above); give the repo skill another name | not reliable: both are listed (see the line above); give the repo skill another name |
| Agents | `~/.gemini/agents/ai-kit-<name>.md` | plugin `agents/` | `[agents.ai-kit-<name>]` in the managed block of `config.toml` |
| Guardrails | `ai-kit-*` groups under `hooks.BeforeTool` of `settings.json` | plugin `hooks.json` (`PreToolUse`) | `[[hooks.PreToolUse]]` in that block, to approve in Codex ("Trust") |
| Repository protected paths | `<repo>/.ai-kit/protected-paths`, read by the kit script | the same file, read by the same script | the same file, read by the same script |
| MCP | `mcpServers` of `settings.json` | plugin `mcp_config.json` | `[mcp_servers.ai-kit-<name>]` in that block |
| Permissions | Gemini approval mode | each person's rules in `~/.gemini/antigravity-cli/settings.json`, never written by the kit | Codex sandbox and approvals, never set by the kit |
| Logs read by `usage` | `~/.gemini/tmp/*/chats/*.json` | `~/.gemini/antigravity-cli/history.jsonl` | `~/.codex/history.jsonl` |
| Real call by `doctor --live` | `gemini -p` | no (agy is checked by `agy plugin validate`) | no (`codex doctor` checks its configuration) |
| Evals | `evals/run.py --cli gemini` | `evals/run.py --cli agy` | `evals/run.py --cli codex` |
| Model (`model`, `models` in `overrides.json`) | `model` sets `model.name` in `settings.json`; `models` sets `model:` on the agents with a capability | not applied: agy's own model choice | not applied: the session model |
| Authentication set by the kit | when declared: `vertex`, `code_assist`, `model` in `overrides.json` | never; see [the agy page](agy.md#authentication-google-account-or-google-cloud-project) | never (`codex login`) |
| Detailed page | [Gemini CLI](gemini.md) | [Antigravity CLI](agy.md) | [Codex CLI](codex.md) |

**Where the layers and `30_USER.md` live.** Gemini imports only files located in `~/.gemini` (verified on 0.65). When Gemini is installed, the layers and `30_USER.md` are therefore in `~/.gemini/`, and agy and Codex read them from there. Without Gemini (`--target codex`, `--target agy`, or a workstation where only another CLI is detected), they are in `~/.ai-kit/context/`, and no `~/.gemini` folder is created for Codex. If the location changes, `30_USER.md` is copied to the new place if it is missing there; the old one is never deleted. `doctor` shows the file in effect.

## Add a CLI

A new CLI is a module in `installer/adapters/`, added to the `ADAPTERS` list, that follows the `Adapter` contract of `installer/interface.py`, plus its column in the table above and its scenarios in `tests/snapshot.py`. What this adapter must know how to do: where to write each row above, how the CLI loads a global context without copying `30_USER.md`, in what form it receives a command, and how it passes a tool call to a guardrail script (the JSON it sends and the response it expects).
