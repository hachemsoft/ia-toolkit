# Claude Code

What the kit does for Claude Code. Formats read and evals run (`claude -p`) on Claude Code 2.1.316; the interactive checks
below are to redo on each new version. Shared concepts: [CLI matrix](matrice.md).

## Install

`ai-kit init` installs for Claude Code when `claude` is present or `~/.claude/settings.json` exists (`--target auto`);
later activations keep the CLIs chosen. `--target claude` installs it alone, `--target all` with the others. Claude Code
signs in with its own account (`/login`, an API key, Bedrock or Vertex): the kit touches neither that, nor the model, nor
the permissions.

## What the kit installs

- **Context**: a managed block at the top of `~/.claude/CLAUDE.md`, between two `ai-kit` markers, that imports the layers
  and `USER.md` by path (`@~/.ai-kit/context/00_KIT.md`, …). No copy: an edit of `USER.md` is read at the next session. The
  rest of the file is yours.
- **Skills** in `~/.claude/skills/`, always prefixed: `ai-kit-tdd`, `ai-kit-code-review`… Claude Code ships its own
  `code-review`, and many people keep personal skills with the kit's names; the prefix keeps both. The installed texts name
  the kit's skills with the prefix. User-only skills (`disable-model-invocation`) are honoured.
- **Commands** in `~/.claude/commands/<name>.md` (`$ARGUMENTS`): `/intent`, `/build`, `/review`… When one of your own
  skills or commands has the name, the kit's is `/ai-kit-<name>`, and the installer and the block say so.
- **Agents** in `~/.claude/agents/ai-kit-<name>.md`; Claude Code applies their tool list (reviewers `Read` and `Grep`, the
  verifier also `Glob` and `Bash`). They inherit the session's model.
- **Guardrails** that are on: groups under `hooks.PreToolUse` of `~/.claude/settings.json` (`Bash` for the shell guardrails, one group for all of them;
  `Bash|Write|Edit|MultiEdit|NotebookEdit` for `protected-paths`), next to your own hooks; no approval step. The
  `whats-new` hook: a group under `hooks.SessionStart`, no matcher.
- **MCP servers** that are on: `ai-kit-<name>` entries in `mcpServers` of `~/.claude.json`, translated from the kit's form
  (`command` → `stdio`, `httpUrl` → `http`, `url` → `sse`). A server with `cwd` is refused: give the full path in `command`.

A kit entry edited by hand (the block, a guardrail group, an MCP entry) stops the activation instead of being overwritten.
Every file is backed up before a change.

## The prefix

`skill_prefix` in `[user]` of `~/.ai-kit/aikit.toml`: `"ai-kit-"` by default, up to 20 lowercase letters, digits or dashes.
The other CLIs use it only for a name already taken. `""` installs without a prefix; the installer then refuses a name that
collides with a skill shipped with Claude Code or one of yours, and lists them. Agents stay `ai-kit-<name>`.

## The repository's AGENTS.md

Claude Code reads a repository's `AGENTS.md` when the repository has no `CLAUDE.md`. When it has one, Claude Code reads
that instead, and the block of `~/.claude/CLAUDE.md` asks it to read `AGENTS.md` (and the one of the area it works in).
"Initialize the project context" proposes a one-line `CLAUDE.md`, `@AGENTS.md`, so the context loads on its own.

## Close Claude Code before an activation

Claude Code keeps `~/.claude.json` in memory and writes it back: an activation made while a session is open can lose its
MCP entries. Close the sessions, run `ai-kit sync` (or `sync --offline`), then start a new one. `doctor` reports a missing
kit MCP server.

## Check in Claude Code

Without sending a message: `/memory` (the imported files), `/skills` (the `ai-kit-` skills), `/agents`, `/hooks`, `/mcp`.
Then `/guide I need to …` in a repository. `doctor --live` makes one real call (`claude -p`), which may be billed.

## Specifics

- `protected-paths` also blocks agent writes to `~/.claude/settings.json`, `~/.claude/CLAUDE.md`,
  `~/.claude/agents/ai-kit-*` and `~/.claude.json`: you make such changes, then run `ai-kit sync --offline`.
- `usage` reads `~/.claude/projects/` (prompts, skills called with the prefix removed, `ai-kit-*` agents, API errors); the
  format is not documented as stable, and an unknown line is skipped.
- A Claude Code plugin would isolate the kit's names natively, but depends on Claude Code installing it at session start:
  not used.
- Evals: `evals/run.py --cli claude` runs `claude -p` without shell or file writes; a real run is billed and needs
  `--confirm-paid-run`.
