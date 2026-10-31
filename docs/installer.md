# The installer: what it does, what it does not do

Reference page for people who deploy or maintain the kit. To install: [getting started](getting-started.md). Where each file goes, CLI by CLI: [CLI matrix](cli/matrice.md). Context layers and their priority: [customization](customization.md).

## How it runs

One launcher, two distributions. `Installer.cmd` (Windows) and `scripts/bootstrap.sh` (Mac, Linux) only find Python 3.9 or newer, then hand over to `scripts/launcher.py`, run with `python -I` (no module of the current folder or of `PYTHONPATH` can replace the kit's). The launcher:

1. checks that this Python has its standard `venv` and `pip` modules; otherwise it says what to ask IT, and downloads no bootstrap script;
2. creates or reuses the kit's private environment, `~/.ai-kit/runtime/venv` (with `--home`, under that folder), at its final place: no environment is shipped prebuilt;
3. installs the kit package and its libraries there with pip:
   - **release ZIP**: from its `wheels/` folder only, `pip install --no-index --find-links wheels`: no package index, no download, no build. All the wheels are pure Python (`py3-none-any`), so one ZIP serves Mac, Windows and Linux, Python 3.9 to 3.14;
   - **git clone**: pip builds the package from the clone (not editable) with the exact versions of `packaging/runtime.txt`; the build tool and the libraries come from the package index pip is already configured for on the workstation (company repository, proxy, certificates: the kit adds no `--index-url` or `--trusted-host`);
4. runs the kit with that environment's Python, from your current folder (a relative `--home` or `--json` keeps its meaning);
5. for `update` in a git clone, first fetches the new version (below).

Nobody activates the environment, runs pip, changes the `PATH` or needs administrator rights. `~/.ai-kit/runtime/install.json` records the state: an installation stopped midway (`installing`) or failed is detected and started again from scratch at the next run, never taken for a success; if the package does not install, the agents are not configured. One run at a time per home folder (`install.lock`): a second one stops and says so. The first messages are plain text; the guided screens come once the libraries are installed. The libraries: Rich (display) and Questionary (questions), pinned in `packaging/runtime.txt` with their dependencies.

**Update in a git clone**, three steps, each reported: 1. fetch, `git pull --ff-only`, refused when the kit folder has local changes (nothing is overwritten, stashed, reset or merged); 2. reinstall the package in the private environment; 3. apply the configuration. If the fetch fails or is refused, the configuration of the current folder is reapplied and the command ends with "Update incomplete" and a non-zero code. The versions of the folder and of the environment are shown when they differ. With a ZIP, a new version is a new ZIP: run its installer.

**Modes.** In a terminal without options: the guided installer (Rich and Questionary), or its menu once the kit is installed. `--plain` or `AI_KIT_PLAIN=1`: plain numbered questions, no colours (also used automatically without the libraries, for example `python -m installer` from a clone). With an action and options, or without a terminal: nothing is asked; a missing choice is an error that names the option, never a question waiting for an answer. `NO_COLOR` is respected; output redirected to a file or a CI log carries no colour codes; a terminal that cannot show Unicode gets ASCII marks. Nothing is applied before the review screen's **Install**; Ctrl+C or a closed terminal during the writes puts every file back.

## What it does

- Does not choose the authentication mode or the model: Google sign-in, licensed Code Assist (`code_assist`), Vertex AI (`vertex`) or API key, and `model` only if you declare them in `overrides.json`. See [customization](customization.md#authentication-and-model).
- Detects a declarative identity (active CLI account, git, OS session), asks you to confirm it and writes it at the top of `30_USER.md` when it creates the file. See [identity](identity.md).
- Stores profile, identity, overrides, fingerprints and backups in `~/.ai-kit`.
- Refuses to overwrite managed layers, skills, agents or MCP servers that were edited by hand.
- Removes old managed files on a profile or version change if they are intact.
- Prevalidates conflicts, backs up, then writes the files; attempts a restore on a write error.
- Touches no project repository, starts no MCP server, calls no model. Downloads nothing from a ZIP; from a git clone, only what pip fetches from the configured package index.
- Changes nothing on the system: no administrator rights, no registry, no system or user PATH, no execution policy, no Gatekeeper or quarantine setting, no shell startup file. Calls no model and needs no network: only `doctor --live`, on request, makes a real call to the model.
- Installs nothing that points back to the extracted kit folder: the package and its content live in `~/.ai-kit/runtime`, the guardrails, the friction script and the `overrides.json` schema are copied to `~/.ai-kit`, and the guardrails run with the private environment's Python. The extracted folder can be deleted after installation; keep it, or the next ZIP, to run the installer again.
- Keeps the CLIs you chose: `update` never adds or removes one because a folder exists or disappears. Removing a CLI from your choice removes what the kit had put there and keeps your own settings.

Existing settings must be strict JSON. An invalid JSON file or one with comments is refused without change. Symbolic links on managed paths are not supported.

The context layers and `30_USER.md` are written to `~/.gemini/` when Gemini CLI is installed (it reads only its own folder), otherwise to `~/.ai-kit/context/`, which the other CLIs include or copy. The guardrail scripts are in `~/.ai-kit/hooks/`.

Before 0.19, the kit folder was called `~/.ai-toolkit`. The first `setup` or `update` renames it to `~/.ai-kit`, with `overrides.json`, the state and the backups, then rewrites the files that referenced the old path. If both folders exist, the kit stops without touching anything: keep `~/.ai-kit`, move what is missing into it, remove `~/.ai-toolkit`, then run `update`.

## Commands

| Action | Mac and Linux (Terminal) | Windows (Command Prompt) |
| --- | --- | --- |
| Install / change profile | `sh scripts/bootstrap.sh` | double-click `Installer.cmd`, or `Installer.cmd setup` |
| New version | extract the new ZIP and run its installer | the same |
| Reapply this version (after editing `overrides.json`; in a git clone, `git pull` first) | `sh scripts/bootstrap.sh update` | `Installer.cmd update` |
| Diagnose (local, free) | `sh scripts/bootstrap.sh doctor` | `Installer.cmd doctor` |
| Uninstall (`--dry-run` to see the list, `--yes` for automation, `--remove-runtime` for the private environment too) | `sh scripts/bootstrap.sh uninstall` | `Installer.cmd uninstall` |
| Check the connection (real call to the model, may be billed) | `sh scripts/bootstrap.sh doctor --live` | `Installer.cmd doctor --live` |
| Usage review | `sh scripts/bootstrap.sh usage` | `Installer.cmd usage` |

Windows: to get a Command Prompt in the kit folder, type `cmd` in the Explorer address bar and press Enter. The launchers (`Installer.cmd`, `scripts/bootstrap.sh`) look for Python 3.9 or newer, then run `python -m installer` from the kit folder; without a usable Python they say what to ask IT. They need neither PowerShell nor administrator rights.

Options for `setup` and `update`: `--profile <id>`, `--user <email>`, `--team <team>`, `--target auto|gemini|agy|codex|both|all` (without it: the CLIs chosen last time; see [getting started](getting-started.md)), `--home <folder>`, `--dry-run`, `--plain` (`--no-live` is still accepted and changes nothing). `scripts\bootstrap.ps1` remains for older instructions: it only runs `Installer.cmd`, where the workstation's script policy already allows it, and changes nothing about that policy. `AI_KIT_NO_PAUSE=1` keeps `Installer.cmd` from waiting for a key when it is started without arguments by a script. Non-interactive example: `sh scripts/bootstrap.sh setup --profile general --user first.last@company.com`. If a company policy blocks a launcher, IT decides: the launcher is equivalent to `python -m installer` run from the kit folder. Never change the policy yourself.

## Try it without touching your account

```sh
sh scripts/bootstrap.sh setup --profile data-analyst --home ./sandbox-user --dry-run
sh scripts/bootstrap.sh setup --profile data-analyst --home ./sandbox-user
sh scripts/bootstrap.sh doctor --home ./sandbox-user
```

On Windows, replace `sh scripts/bootstrap.sh` with `Installer.cmd`. The private environment of a trial goes under `./sandbox-user/.ai-kit/runtime`. From a clone, without the launcher: `python3 -m installer …` uses your Python and its plain-text mode. `--home` applies only to the kit, not to the configuration actually loaded by a CLI launched normally. `setup` and `update` never call the model. `doctor --live` is the only real call; `AI_KIT_NO_LIVE=1` refuses it, for example in CI.

## MCP

No server is defined in the public kit: endpoints, transports and authentication belong to the organization. `organization.json` defines the approved servers, each profile lists those it turns on, and each person adjusts or adds their own in `overrides.json`. See [MCP configuration](mcp.md).

## Uninstall

`uninstall` removes what the kit installed and nothing else: the managed files it recognises as unchanged, its blocks and entries in the CLIs' settings (guardrails, MCP servers, layers in `context.fileName`, kit lines of `.env`, the Codex blocks), and its state. It keeps your personal context (`30_USER.md`), `overrides.json`, the backups and frictions, the CLIs' folders and your own settings; a managed file you edited is kept and named. Everything removed or cleaned is first copied to `~/.ai-kit/backups/`. No network, no model. Interactive: it shows the list and asks; automation: `--yes`; `--dry-run` shows the list without changing anything. The private environment stays unless the launcher is given `--remove-runtime`; it removes it only after the kit has exited, so no file in use is deleted.

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
