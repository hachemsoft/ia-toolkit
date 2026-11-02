# Architecture

How the installer works, what it guarantees and where it depends on things it does not control. For a second maintainer: read this, then `installer/interface.py`.

## The flow of an installation

```
launcher (scripts/launcher.py)          the private venv ~/.ai-kit/runtime, the kit package from the ZIP's wheels
  └─ installer (installer/cli.py: main)
       ├─ settings (installer/settings.py): organization.toml defaults → team → ~/.ai-kit/overrides.toml
       ├─ resolution (installer/plan.py): profile + settings → skills (with their dependencies), commands, agents, guardrails, MCP servers
       ├─ plan: a Plan (installer/interface.py) holding every file to write, with nothing specific to a CLI
       ├─ adapters (installer/adapters/*.py): each chosen CLI adds its own writes to the plan, in its format
       ├─ checks: nothing written yet; a file edited by hand, a link, a refused value stops everything here
       └─ commit (installer/commit.py): backup of every file that changes, atomic writes, state.json; any error puts everything back
```

`setup` and `update` run the same `apply` (`installer/cli.py`, with the commands and migrations), which runs the steps of `installer/plan.py` in order; `doctor` (`installer/doctor.py`), `usage` (`installer/usage.py`) and `uninstall` read `~/.ai-kit/state.json`, which records every file the kit wrote with its digest, the managed blocks inside files it shares (`~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`), the guardrails, MCP servers, versions and choices.

## The adapter contract

A CLI is a module in `installer/adapters/`, listed in `ADAPTERS`, that follows the `Adapter` protocol of `installer/interface.py`: `install(plan)` adds its files, `finalize(plan, active)` merges its settings (and, when the CLI is no longer chosen, removes what the kit had put there), `doctor(ctx)`, `history(home, state)` for the usage review, and the declarations `AGENT_TOOLS` (does the CLI enforce an agent's tool list) and `OBSERVES` (what its logs show). Two optional capabilities: `ContextHost` (the CLI reads its context only from its own folder, so it gets a copy) and `LiveCheck` (`doctor --live`). `cli.py` names no CLI.

## Invariants

These hold for every change; a test guards each.

- **No byte installed changes by accident**: `tests/golden/install-snapshot.json` holds the digest of every file of 16 scenarios; `python3 tests/snapshot.py --update` after an intended change.
- **A file the person edited is never overwritten**: managed files are tracked by digest; a hand edit stops `update` (the rule layers 00/10/20 are put back, the edited copy kept in the backup).
- **All or nothing**: writes are atomic; an error or Ctrl+C restores every file from the backup taken just before.
- **No model call, no network** in `setup`, `update`, `doctor`, `uninstall` and the tests (`scripts/offline_tests.py` takes the CLIs off the PATH and fails if one is reached).
- **Every skill and agent has a version**, raised at each change (`versions.lock.json`, `scripts/versions.py`).
- **Modules stay readable**: no module of `installer/` over 800 lines; past that, it is split by responsibility.
- **Size ceilings**: the kit context template stays under 3,800 characters and each command prompt under 4,000, because the context is loaded at every session of every person: every line has a cost.

## What the kit does not control

| Dependency | Where | What breaks it |
| --- | --- | --- |
| Each CLI's file layout and settings format | the adapters | a CLI release that moves a folder or renames a key; `doctor` then reports the missing piece |
| The logs read by `usage` (Gemini chats, agy conversation database, Codex sessions, Claude Code transcripts) | `history` in each adapter | an undocumented format change: `usage` says so when it reads a CLI's logs and recognises nothing |
| `~/.claude.json`, rewritten by Claude Code while it runs | the Claude adapter | an `update` during an open session; the docs say to close it first |
| What is new, said at session start | `runtime/hooks/session-news.py`, `NEWS.md`, `runtime/news.py` | the hook reads the kit's remote once a day, never writes it, never runs `update` (ADR 0012) |
| The CLIs' tool names in the guardrails | `runtime/hooks/` | a new tool name; the guardrails refuse a call that names a protected path in a form they cannot read |

Each adapter declares the CLI version it was checked on (`VERIFIED`, shown in the [CLI matrix](cli/matrice.md)): `doctor` says when a newer one runs. Once a week, `.github/workflows/cli-drift.yml` installs the latest release of each CLI published on npm and runs `scripts/cli_drift.py`: the version, and the options the kit relies on, read from `--help`, without a model call. A red run means an adapter or the evals need a change; a newer version that still has every option is reported, then `VERIFIED` is raised after a check.

## Migrations

An installation is migrated by the next `update` from the three previous minor versions at least; older migration code can be removed. Each migration is said to the person (`[Info]`), keeps the old file in the backup, and has a test.
