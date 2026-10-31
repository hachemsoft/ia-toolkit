# Codex CLI

What the kit does for Codex CLI, and what is specific to this CLI. Verified on Codex CLI 0.160. Shared concepts are in the [CLI matrix](matrice.md).

## Install for Codex

The first `setup` installs for Codex when the `codex` command is present or `~/.codex` exists (`--target auto`); afterwards `update` keeps the CLIs you chose. `--target all` forces it alongside the other CLIs, `--target codex` installs it alone, and `--target gemini`, `agy`, `claude` or `both` exclude it. Codex signs in with its own account (`codex login`, ChatGPT account or OpenAI key): the kit does not touch it.

## What the kit installs

- **Context**: a managed block at the top of `~/.codex/AGENTS.md`, between two `ai-kit` markers, with the kit layers and a copy of `30_USER.md` (in `~/.gemini/` if Gemini is installed, otherwise in `~/.ai-kit/context/`). The rest of the file belongs to you and is never changed. Because Codex does not include other files by path, the copy of `30_USER.md` is refreshed on every `update`: after you edit it, run `update` again (`doctor` reports it).
- **Skills** in `~/.codex/skills/`. Skills marked "on command only" get an `agents/openai.yaml` with `allow_implicit_invocation: false`: Codex honors this flag natively and activates them only when called.
- **Commands**: one skill per command, also on command only. In Codex, you call them with **`$intent`**, `$build`, `$test`…; `/skills` lists them.
- **Agents**: one `ai-kit-<name>` role per agent, declared under `[agents.ai-kit-<name>]` in the managed block of `~/.codex/config.toml`, with its instructions in `~/.codex/ai-kit/agents/`.
- **Guardrails** that are enabled: declared under `[[hooks.PreToolUse]]` in the same block. The scripts understand the Codex call format, including the paths of an `apply_patch`.
- **MCP servers** that are enabled: `[mcp_servers.ai-kit-<name>]` in the same block.

The `config.toml` block is appended to the end of the file and checked before writing with Python 3.11 or later (the file must stay valid TOML). Your own settings do not move. Both files are backed up on every change.

## Approve the guardrails

Codex runs a hook only after it has been approved. The kit installs one by default (`protected-paths`, which protects the configuration), so on the first launch after installation Codex shows "Hooks need review". Answer "Trust all and continue"; "Continue without trusting" leaves them inactive. The kit never writes this approval for you. In non-interactive mode (`codex exec`), an unapproved hook does not run.


`doctor` reports `[Check]` when no approval is recorded at all (no `[hooks.state."…config.toml:pre_tool_use:…"]` entry). When records exist, it says "approval not verifiable automatically": Codex records each approval with a `trusted_hash` the kit cannot recompute, under group indexes that other hooks share, so a record is never taken as proof that the kit's guardrails are approved. `/hooks` in Codex shows what is approved; Codex asks again when a guardrail command changes after an update. The `protected-paths` guardrail always blocks agent writes to `~/.codex/config.toml` and `~/.codex/AGENTS.md`.
## Check in Codex

`codex doctor` (configuration loaded, `config.toml parse ok`), `/skills` and `/agents` (the `ai-kit-*` roles) in Codex, then `$guide I need to …` in a repository.

## Specifics

- **`~/.codex/AGENTS.override.md`**: if it exists, Codex reads it instead of `AGENTS.md`, and the kit context is ignored; `doctor` reports it.
- **Repository context**: Codex natively reads the `AGENTS.md` of the repository and its folders, as the kit organizes it.
- **Logs read by `usage`**: `~/.codex/history.jsonl` (typed prompts, `$intent` or `/intent` commands) and the session files `~/.codex/sessions/**/rollout-*.jsonl`: the kit skills whose `SKILL.md` is read, the `ai-kit-*` roles spawned, the errors.
- **Name already taken**: when one of your skills in `~/.codex/skills/` has the name of a kit skill or command, yours is kept and the kit's is installed as `ai-kit-<name>` (`skill_prefix`); the kit block says which name to type.
- **`doctor --live`**: one real call with `codex exec` in a read-only sandbox, without saving the session; may be billed. The failure is explained (sign-in, quota, model, network, proxy, certificate).
- **Evals**: `python3 evals/run.py --cli codex` runs `codex exec` in a read-only sandbox; `/intent` in a case becomes `$intent`.

## Codex troubleshooting

- **"Kit block edited by hand"**: a line was changed between the `ai-kit` markers. Move the change outside the block (or into `30_USER.md` or `overrides.json`), remove the block, then run `update`.
- **"hooks.PreToolUse already defined in another form"**: your `config.toml` declares its hooks in a form other than `[[hooks.PreToolUse]]`. The kit does not rewrite your settings; it refuses.
- **The guardrails block nothing**: they were not approved. Restart Codex in interactive mode and answer "Trust".
