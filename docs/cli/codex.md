# Codex CLI

What the kit does for Codex CLI. Verified on Codex CLI 0.164. Shared concepts: [CLI matrix](matrice.md).

## Install

`ai-kit init` installs for Codex when `codex` is present or `~/.codex` exists (`--target auto`); later activations keep
the CLIs chosen. `--target codex` installs it alone, `--target all` with the others. Codex signs in with its own account
(`codex login`): the kit does not touch it.

## What the kit installs

- **Context**: a managed block at the top of `~/.codex/AGENTS.md`, between two `ai-kit` markers, with the kit layers and a
  copy of `~/.ai-kit/context/USER.md`. The rest of the file is yours. Codex cannot include a file by path, so after editing
  `USER.md` run `ai-kit sync --offline` (`doctor` reports a stale copy).
- **Skills** in `~/.codex/skills/`; user-only skills get an `agents/openai.yaml` with `allow_implicit_invocation: false`,
  which Codex honours.
- **Commands**: one command skill each, also on command only, typed **`$intent`**, `$build`, `$test`…; `/skills` lists them.
- **Agents**: one `ai-kit-<name>` role each under `[agents.ai-kit-<name>]` in the managed block of `~/.codex/config.toml`,
  instructions in `~/.codex/ai-kit/agents/`. A role has no tool list: the session's sandbox and approvals apply.
- **Guardrails** that are on: `[[hooks.PreToolUse]]` in the same block; the scripts read Codex's call format, including the
  paths of an `apply_patch`. The `whats-new` hook: `[[hooks.SessionStart]]`, no matcher.
- **MCP servers** that are on: `[mcp_servers.ai-kit-<name>]` in the same block.

The `config.toml` block is appended at the end and checked to stay valid TOML before writing. Both files are backed up on
every change.

## Approve the guardrails

Codex runs a hook only after approval. On the first launch after installation it shows "Hooks need review": answer "Trust
all and continue". The kit never writes this approval. In `codex exec`, an unapproved hook does not run. `doctor` reports
`[Check]` when no approval is recorded at all; when records exist it says "approval not verifiable automatically", since
Codex stores a hash the kit cannot recompute. `/hooks` in Codex shows what is approved; Codex asks again when a hook
command changes.

## Protected configuration

`protected-paths` always blocks agent writes to `~/.codex/config.toml` and `~/.codex/AGENTS.md`.

## Check in Codex

`codex doctor` (`config.toml parse ok`), `/skills` and `/agents` in Codex, then `$guide I need to …` in a repository.

## Specifics

- **Parallel agents**: Codex's sandbox does not let the agent write to `.git`, so it cannot create a worktree for a sub-agent: with the `parallel` setting, sub-agents that read run together and one writes at a time. To isolate a whole session, start it with `codex --worktree`; its sub-agents share that worktree ([parallel agents](../parallel-agents.md)).
- **`~/.codex/AGENTS.override.md`**: when it exists, Codex reads it instead of `AGENTS.md` and the kit context is ignored;
  `doctor` reports it.
- **Logs read by `usage`**: `~/.codex/history.jsonl` and `~/.codex/sessions/**/rollout-*.jsonl` (skill files read,
  `ai-kit-*` roles spawned, errors).
- **Name taken**: when one of your skills has the name of a kit skill or command, yours is kept and the kit's is installed
  as `ai-kit-<name>`; the block says which name to type.
- **`doctor --live`**: one real call with `codex exec` in a read-only sandbox, without saving the session; may be billed.
- **Evals**: `python3 evals/run.py --cli codex` runs `codex exec` read-only; `/intent` in a case becomes `$intent`.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| "Kit block edited by hand" | move the change outside the block (or into `USER.md` or `aikit.toml`), remove the block, run `ai-kit sync --offline` |
| "hooks.PreToolUse already defined in another form" | your `config.toml` declares hooks in another form; the kit does not rewrite your settings and refuses |
| the guardrails block nothing | they were not approved: restart Codex interactively and answer "Trust" |
