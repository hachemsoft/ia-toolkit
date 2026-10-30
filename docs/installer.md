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
- Changes nothing on the system: no administrator rights, no registry, no system or user PATH, no execution policy, no Gatekeeper or quarantine setting, no shell startup file. Needs no network: only the final check calls the model.
- Installs nothing that points back to the extracted kit folder: the guardrails, the friction script and the `overrides.json` schema are copied to `~/.ai-kit`. Keep the folder to run `update` and `doctor`; when the next version comes as a new ZIP, the new folder replaces it.

Existing settings must be strict JSON. An invalid JSON file or one with comments is refused without change. Symbolic links on managed paths are not supported.

The context layers and `30_USER.md` are written to `~/.gemini/` when Gemini CLI is installed (it reads only its own folder), otherwise to `~/.ai-kit/context/`, which the other CLIs include or copy. The guardrail scripts are in `~/.ai-kit/hooks/`.

Before 0.19, the kit folder was called `~/.ai-toolkit`. The first `setup` or `update` renames it to `~/.ai-kit`, with `overrides.json`, the state and the backups, then rewrites the files that referenced the old path. If both folders exist, the kit stops without touching anything: keep `~/.ai-kit`, move what is missing into it, remove `~/.ai-toolkit`, then run `update`.

## Commands

| Action | Mac and Linux (Terminal) | Windows (Command Prompt) |
| --- | --- | --- |
| Install / change profile | `sh scripts/bootstrap.sh` | double-click `Installer.cmd`, or `Installer.cmd setup` |
| New version | extract the new ZIP and run its installer | the same |
| Reapply this version (after editing `overrides.json`; in a git clone, `git pull` first) | `sh scripts/bootstrap.sh update` | `Installer.cmd update` |
| Diagnose | `sh scripts/bootstrap.sh doctor --live` | `Installer.cmd doctor --live` |
| Usage review | `sh scripts/bootstrap.sh usage` | `Installer.cmd usage` |

Windows: to get a Command Prompt in the kit folder, type `cmd` in the Explorer address bar and press Enter. The launchers (`Installer.cmd`, `scripts/bootstrap.sh`) look for Python 3.9 or newer, then run `python -m installer` from the kit folder; without a usable Python they say what to ask IT. They need neither PowerShell nor administrator rights.

Options for `setup` and `update`: `--profile <id>`, `--user <email>`, `--team <team>`, `--target auto|gemini|agy|codex|both|all` (see [getting started](getting-started.md)), `--home <folder>`, `--dry-run`, `--no-live`. Non-interactive example: `sh scripts/bootstrap.sh setup --profile general --user first.last@company.com`. If a company policy blocks a launcher, IT decides: the launcher is equivalent to `python -m installer` run from the kit folder. Never change the policy yourself.

## Try it without touching your account

```sh
python3 -m installer setup --profile data-analyst --home ./sandbox-user --dry-run
python3 -m installer setup --profile data-analyst --home ./sandbox-user
python3 -m installer doctor --home ./sandbox-user
```

On Windows, replace `python3` with `py -3`. `--home` applies only to the kit, not to the configuration actually loaded by a CLI launched normally. `setup` and `update` end with a real call to the model; `--no-live` (or `AI_KIT_NO_LIVE=1`) skips it, for example in CI.

## MCP

No server is defined in the public kit: endpoints, transports and authentication belong to the organization. `organization.json` defines the approved servers, each profile lists those it turns on, and each person adjusts or adds their own in `overrides.json`. See [MCP configuration](mcp.md).

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
