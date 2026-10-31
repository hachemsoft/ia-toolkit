# Troubleshooting

First step, always: `sh scripts/bootstrap.sh doctor` (Mac) or `Installer.cmd doctor` (Windows, in a Command Prompt opened in the kit folder: type `cmd` in the Explorer address bar): local checks, no model call. For sign-in, quota or network symptoms, add `--live`: it makes one real call to the model (your provider may bill it) and, for each known failure, gives the diagnosis and the command that fixes it. The symptoms below are those seen on real workstations; each new ticket adds one.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

| Symptom | Cause | What to do |
| --- | --- | --- |
| "Your prepayment credits are depleted", HTTP 402 | the AI Studio key has no balance left | top up, or switch to Vertex: `"vertex": {"project": "<project>"}` in `overrides.json`, then `update` |
| "API Keys are Disallowed" | Google Cloud policy forbids keys | `gcloud auth application-default login`, Vertex in `overrides.json`, remove `GEMINI_API_KEY` from the environment |
| "aiplatform.googleapis.com has not been used", HTTP 403 | Vertex API not enabled on the project | `gcloud services enable aiplatform.googleapis.com --project <project>` |
| Gemini never answers, "Model fallback activated" in a loop | default model unavailable on your access | `"model": "gemini-2.5-flash"` (or another model available to you) in `overrides.json`, then `update` |
| "This account requires setting the GOOGLE_CLOUD_PROJECT…" | Code Assist Standard or Enterprise licence with no project declared | `"code_assist": {"project": "<project>"}` in `overrides.json`, then `update` |
| "When using Vertex AI, you must specify…" | project and region missing | `"vertex": {"project": "<project>", "location": "<region>"}` in `overrides.json`, then `update` |
| Vertex variables are ignored | `selectedType` is still `gemini-api-key` | `update` with `vertex` in `overrides.json` fixes it; otherwise `/auth` in Gemini |
| "Skill conflict detected" at startup, the command does not do what the docs say | a personal copy with the same name in `~/.agents/skills` hides the kit's skill | `doctor` lists hidden skills; remove or rename the personal copy |
| in one repo, a command behaves differently from the docs, or differently from one CLI to another | the repo has a skill named like a kit skill (`.agents/skills/<name>`): depending on the CLI, the repo's, the kit's or both are used | `doctor`, run from the repo ([how](getting-started.md#run-the-kit)), lists the clashes; rename the repo skill and point to it from `AGENTS.md` ([project layer](project-context.md#how-the-repo-combines-with-your-layers)) |
| agy asks for permission on every shell command | normal behaviour: agy permissions belong to each person | answer; "always allow" saves the rule in your agy settings, and the kit does not touch them |
| "It does not see my glossary" | CLI started outside the repo | `cd` into the repo, then start the CLI; the kit is global, the repo is not |
| a command from the docs cannot be found | command not in your profile ([profile table](getting-started.md#3-work-one-command-per-step)) | `"extra_commands": ["spec"]` in `overrides.json`, then `update`; `00_KIT.md` lists the installed commands |
| `/intent` or `/build` cannot be found | command not installed, or skill disabled | `doctor`; check `disabled_skills` and `disabled_commands` in `overrides.json` |
| "Skill existing file not managed by the kit" at `update` | a skill with the same name installed outside the kit | remove it, or add it to `disabled_skills` |
| dbt refuses to run: "Blocked by the kit: production target" | guardrail active | use the development target; an authorized person exports `AI_KIT_ALLOW_PROD=1` |
| `update` stops on "modified locally" | a file installed by the kit (skill, agent, command, settings block) was edited | move the change to `30_USER.md` or a repo skill, restore, run again |
| `update` says "was modified by hand: restored" | a rule layer (`00_KIT.md`, `10_COMPANY.md`, `20_…md`) was edited | normal: the kit version is back, your copy is in `~/.ai-kit/backups/`; personal preferences go in `30_USER.md`, a rule change through the kit repository |

## Other cases

CLI-specific issues are on each CLI's page: [Gemini CLI](cli/gemini.md#gemini-troubleshooting), [Antigravity CLI](cli/agy.md#troubleshooting), [Codex CLI](cli/codex.md).

- **Python missing, too old or blocked**: the launcher says which, and what to ask IT: Python 3.9 or newer (3.11 recommended), usable by a standard account, provided or approved by the company. On Windows, the Microsoft Store alias without Python counts as missing; on a Mac, `/usr/bin/python3` without the developer tools too (the launcher does not trigger their installation). Do not change company policies.
- **`Installer.cmd` blocked, or Windows asks to confirm a downloaded file**: follow your company's rule; if it is blocked, ask IT. The launcher only finds Python and runs `scripts\launcher.py`, which installs the kit in its private environment from the ZIP's own files; that helps IT decide. Do not unblock the file or change the policy yourself.
- **"This Python has no venv or pip support"**: the Python found lacks its standard `venv` or `pip` module (on Linux, often the `python3-venv` package). Ask IT for a complete Python; the kit downloads nothing to work around it.
- **"A previous installation of the kit runtime did not finish" or "failed"**: the last run stopped midway (closed window, Ctrl+C, network for a clone); this run starts the private environment again from scratch. If it fails again, the message shows pip's last lines: from a ZIP, extract the whole ZIP again; from a clone, check pip's access to your package index.
- **"Another run of the kit installer is in progress"**: wait for the other window to finish. If none is open, the lock is from a run that crashed: it is taken over automatically when its process no longer exists.
- **"Update incomplete: the new version was not fetched"** (git clone): local changes in the kit folder, no network, or a diverging history. Nothing was overwritten; the configuration of the current folder was reapplied. Commit or set aside your changes yourself, then update again.
- **`ai-kit` shows an old version, or none of the new options, after `pip install .`**: another `ai-kit` command comes first on your PATH, often an earlier `pipx install` (the docs proposed it to developers until 0.33). `ai-kit --version` says which copy runs; `doctor` lists every copy. Remove the old one (`pipx uninstall ai-kit`, or `pip uninstall ai-kit` with the Python that installed it), or start the kit with the launcher of the kit folder, which always runs the private environment's copy.
- **The questions show odd characters or no arrows**: run with `--plain` (or set `AI_KIT_PLAIN=1`) for numbered questions in plain text.
- **No network, proxy, certificate**: the installation is complete anyway; only `doctor --live` needs the model. `doctor --live` names the cause: no network or blocked hosts, a proxy asking for authentication (HTTP 407), or HTTPS inspection without the company root certificate. What to ask IT is in the message; never disable certificate checks.
- **`30_USER.md` not applied**: saved as rich text, under another name (`30_USER.md.txt`) or in another encoding. `doctor` says which. TextEdit: Format > Make Plain Text, then save under the same name; Notepad: encoding UTF-8. Then `update`, and a new session of the CLI.
- **Unreadable settings**: fix the existing JSON after making a backup. The kit does not accept JSON with comments (JSONC).
- **Kit skill hidden**: a personal copy with the same name, in a folder the CLI reads first, hides the kit's skill. `doctor` lists hidden skills. Remove or rename the personal copy.
- **Evals failing with an infrastructure error**: `evals/run.py` distinguishes an unavailable API response (401, 402 credits exhausted, 403, 429) from a behaviour failure; fix the CLI's authentication or billing before drawing conclusions about a skill.
- **Skill existing file not managed by the kit**: a skill with the same name was installed outside the kit (by a CLI command, for example). Either remove it to let the kit provide its own, or add it to `disabled_skills` in overrides.json. The kit never overwrites a file it does not manage.
- **Skill modified**: save your adaptations in a new skill or in the kit sources, restore the old untouched generated output, run update again.
- **Context layer modified** (`00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md`): these files are generated. Move the change to `30_USER.md`, restore the file from a backup, run update again.
- **Context not loaded**: check with the CLI's command that the global layers appear before the project's `AGENTS.md`; the steps are on each CLI's page.
- **Wrong identity detected**: run `setup --user your.email@company` again; the `30_USER.md` header can be fixed by hand. Identity grants no rights.
- **Doctor reports an out-of-domain account**: the CLI is logged in with an account that is not in `allowed_domains`. Log in again with your work account before working on company data.
- **Skills not visible**: list them with the CLI's command, check that they are enabled and check managed policies. Having the files present does not guarantee they are enabled.
- **MCP not configured**: this is normal, no server is enabled by default; see [MCP](mcp.md). A missing optional MCP server does not make doctor fail.
- **Doctor returns 1**: at least one local check needs action; 2 means a configuration error. The setup/update actions return 0 on success, 2 on error.

## Manual rollback

Close the CLI. Each installation that modifies files creates a dated folder in `~/.ai-kit/backups`. It contains the previous files, with their path relative to the home folder, and a manifest of newly created files.

Copy the backed-up files to the same paths under your home folder. For files listed in `created`, remove them only if they have not received personal changes since. Never delete the CLI's folder or its skills wholesale. The manifest is not an automatic restore program.

## Team rule

A support ticket is never solved verbally twice. It becomes a `doctor` check, a line here, or a case in `evals/`.
