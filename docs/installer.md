# The installer: what it does, what it does not do

Reference page for people who deploy or maintain the kit. To install: [getting started](getting-started.md). Where each file goes, CLI by CLI: [CLI matrix](cli/matrice.md). Context layers and their priority: [customization](customization.md).

## What it does

- Does not choose the authentication mode or the model: Google sign-in, licensed Code Assist (`code_assist`), Vertex AI (`vertex`) or API key, and `model` only if you declare them in `overrides.json`. See [customization](customization.md#authentication-and-model).
- Detects a declarative identity (active CLI account, git, OS session), asks you to confirm it and writes it at the top of `30_USER.md` when it creates the file. See [identity](identity.md).
- Stores profile, identity, overrides, fingerprints and backups in `~/.ai-kit`.
- Refuses to overwrite managed layers, skills, agents or MCP servers that were edited by hand.
- Removes old managed files on a profile or version change if they are intact.
- Prevalidates conflicts, backs up, then writes the files; attempts a restore on a write error.
- Touches no project repository, starts no MCP server, downloads nothing.

Existing settings must be strict JSON. An invalid JSON file or one with comments is refused without change. Symbolic links on managed paths are not supported.

The context layers and `30_USER.md` are written to `~/.gemini/` when Gemini CLI is installed (it reads only its own folder), otherwise to `~/.ai-kit/context/`, which the other CLIs include or copy. The guardrail scripts are in `~/.ai-kit/hooks/`.

Before 0.19, the kit folder was called `~/.ai-toolkit`. The first `setup` or `update` renames it to `~/.ai-kit`, with `overrides.json`, the state and the backups, then rewrites the files that referenced the old path. If both folders exist, the kit stops without touching anything: keep `~/.ai-kit`, move what is missing into it, remove `~/.ai-toolkit`, then run `update`.

## Commands

| Action | Mac | Windows PowerShell |
| --- | --- | --- |
| Install / change profile | `sh scripts/bootstrap.sh setup` | `.\scripts\bootstrap.ps1 setup` |
| Fetch and apply a new version (does `git pull` first in a git clone without local changes) | `sh scripts/bootstrap.sh update` | `.\scripts\bootstrap.ps1 update` |
| Diagnose | `sh scripts/bootstrap.sh doctor --live` | `.\scripts\bootstrap.ps1 doctor --live` |
| Usage review | `sh scripts/bootstrap.sh usage` | `.\scripts\bootstrap.ps1 usage` |

Options for `setup` and `update`: `--profile <id>`, `--user <email>`, `--team <team>`, `--target auto|gemini|agy|codex|both|all` (see [getting started](getting-started.md)), `--home <folder>`, `--dry-run`, `--no-live`. Non-interactive example: `python3 -m installer setup --profile general --user first.last@company.com`. If company policy blocks PowerShell scripts: `py -3 -m installer setup`, without changing the policy.

## Try it without touching your account

```sh
python3 -m installer setup --profile data-analyst --home ./sandbox-user --dry-run
python3 -m installer setup --profile data-analyst --home ./sandbox-user
python3 -m installer doctor --home ./sandbox-user
```

On Windows, replace `python3` with `py -3`. `--home` applies only to the kit, not to the configuration actually loaded by a CLI launched normally. `setup` and `update` end with a real call to the model; `--no-live` (or `AI_KIT_NO_LIVE=1`) skips it, for example in CI.

## MCP

The catalog offers a documentation server, BigQuery and dbt. No server is enabled by default: your endpoints, transports and authentication are not known. See [MCP configuration](mcp.md).

## Limits

- Each CLI has its own limits, described on its page: [Gemini CLI](cli/gemini.md), [Antigravity CLI](cli/agy.md), [Codex CLI](cli/codex.md).
- Company and team practices are offered as a baseline, to be validated by each organization before rollout.
- The core skills come from an upstream repository under the MIT licence (`skills/LICENSE-UPSTREAM-MIT`), in English; they are updated by hand.
- `research` and `implement-spec` (optional) delegate to CLI subagents; without them, they run in degraded mode. `/map`, `/triage` and `to-tickets` expect a ticket tracker declared per repository with `setup-workflow`.
- The core skills were written for another tool: `00_KIT.md` gives the model the mapping table (subagents, `CLAUDE.md`, PR). None of the current CLIs understands their "on command only" flag; the kit restates it in context but cannot guarantee it.
- No embedded secrets, fleet management or admin policy. The detected identity grants no rights.
- No project-specific role, dataset, dbt target or KPI configuration.
- `doctor` checks files, settings, identity and executables, not authentication, IAM rights or MCP calls.
- Automated tests run on Mac/Windows/Linux; this version was tested on macOS. Layer and skill discovery was verified on each CLI in a sandbox (versions in the [CLI matrix](cli/matrice.md)); acceptance testing on your workstations is still to do.
- The global user context is loaded in all your projects: use a work account.
