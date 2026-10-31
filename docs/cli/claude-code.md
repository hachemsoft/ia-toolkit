# Claude Code

What the kit does for Claude Code, and what is specific to this CLI. Formats read and evals run (`claude -p`) on Claude Code 2.1.316; the interactive checks (below) are still to do on each new version. Shared concepts are in the [CLI matrix](matrice.md).

## Install for Claude Code

`setup` and `update` install for Claude Code when the `claude` command is present or `~/.claude/settings.json` exists (`--target auto`, the first time). `--target all` includes it, `--target claude` installs it alone; the guided installer lists it with the other CLIs. Claude Code signs in with its own account (`claude` then `/login`, an API key, Bedrock or Vertex): the kit does not touch it, nor the model or the permissions.

## What the kit installs

- **Context**: a managed block at the top of `~/.claude/CLAUDE.md`, between two `ai-kit` markers, that imports the kit layers and your `30_USER.md` by path (`@~/.gemini/00_KIT.md`, or `~/.ai-kit/context/` without Gemini CLI). Nothing is copied: an edit of `30_USER.md` is read at the next session, without `update`. The rest of the file is yours and never changes.
- **Skills** in `~/.claude/skills/`, with a prefix: `ai-kit-tdd`, `ai-kit-code-review`… Claude Code ships its own `code-review`, and many people keep personal skills with the same names as the kit's; the prefix keeps both. The texts the kit installs name its skills with the prefix, and the block of `CLAUDE.md` says to read any other mention the same way. "On command only" (`disable-model-invocation`) is honoured natively.
- **Commands** in `~/.claude/commands/<name>.md`: `/intent`, `/build`, `/review`… as in the other CLIs. When one of your own skills or commands already has the name, the kit's is installed as `/ai-kit-<name>` (with your prefix), and the installer and the block of `CLAUDE.md` say so; yours is never touched.
- **Agents** in `~/.claude/agents/ai-kit-<name>.md`. Their tool list is applied by Claude Code itself: a reviewer gets `Read` and `Grep` only, the verifier also `Glob` and `Bash`. They inherit the session's model.
- **Guardrails** that are enabled: groups under `hooks.PreToolUse` in `~/.claude/settings.json` (`Bash` for `dbt-prod-guard`; `Bash|Write|Edit|MultiEdit|NotebookEdit` for `protected-paths`), next to your own hooks, which stay as they are. Claude Code runs them without an approval step.
- **MCP servers** that are enabled: `ai-kit-<name>` entries in `mcpServers` of `~/.claude.json`, translated from the kit's form (`command` → `stdio`, `httpUrl` → `http`, `url` → `sse`, with `args`, `env` and `headers`). A server with `cwd` is refused: give the full path in `command`. Your own servers and the rest of the file stay as they are.

A kit entry edited by hand (the block, a guardrail group, an MCP entry) stops `update` instead of being overwritten. Every file is backed up before a change.

## The prefix

`skill_prefix` in `~/.ai-kit/overrides.json` (or in the organization's or the team's defaults) sets it: `"ai-kit-"` by default, up to 20 lowercase letters, digits or dashes. The other CLIs use the same prefix, but only for a name already taken by one of your skills or commands. `""` installs the skills without a prefix; the installer then refuses if a name collides (a skill shipped with Claude Code, one of yours) and lists them. Changing the prefix renames the kit's files at the next `update`; the agents stay `ai-kit-<name>`.

## The repository's AGENTS.md

Claude Code loads `CLAUDE.md`, not `AGENTS.md`. The block of `~/.claude/CLAUDE.md` asks it to read the repository's `AGENTS.md` (and the one of the area it works in) before working. For a repository used with Claude Code, "Initialize the project context" also proposes a one-line `CLAUDE.md`, `@AGENTS.md`, so the context loads on its own; the kit never writes a second copy of the content.

## Close Claude Code before an update

Claude Code keeps `~/.claude.json` in memory and writes it back: an `update` made while a session is open can lose its MCP entries. Close the sessions, run `update`, then start a new one. `doctor` reports a missing kit MCP server.

## Check in Claude Code

In a session, without sending a message: `/memory` (the imported files), `/skills` (the `ai-kit-` skills), `/agents`, `/hooks` (the kit's groups next to yours), `/mcp`. Then `/guide I need to …` in a repository. `doctor --live` makes one real call (`claude -p`), which your provider may bill.

## Usage report

`usage` reads the session transcripts in `~/.claude/projects/`: the prompts and commands typed, the skills called (the prefix removed), the `ai-kit-*` agents called, the API errors. The format is Claude Code's own and not documented as stable: an unknown line is skipped.

## Specifics

- `protected-paths` also blocks agent writes to `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/agents/ai-kit-*` and `~/.claude.json`: Claude Code itself can no longer change them through its tools; you make such changes, then `update`.
- A Claude Code plugin (marketplace) would isolate the kit's names natively, but depends on Claude Code installing it at the start of a session: not used.
- Evals: `evals/run.py --cli claude` runs `claude -p` without shell or file writes (`--disallowedTools`); a real run is billed and needs `--confirm-paid-run`.
