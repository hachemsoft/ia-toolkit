# Troubleshooting

First step, always: `sh scripts/bootstrap.sh doctor --live` (Mac) or `.\scripts\bootstrap.ps1 doctor --live` (Windows). It makes a real call to the model and, for each known failure, gives the diagnosis and the command that fixes it. The symptoms below are those seen on real workstations; each new ticket adds one.

| Symptom | Cause | What to do |
| --- | --- | --- |
| "Your prepayment credits are depleted", HTTP 402 | the AI Studio key has no balance left | top up, or switch to Vertex: `"vertex": {"project": "<project>"}` in `overrides.json`, then `update` |
| "API Keys are Disallowed" | Google Cloud policy forbids keys | `gcloud auth application-default login`, Vertex in `overrides.json`, remove `GEMINI_API_KEY` from the environment |
| "aiplatform.googleapis.com has not been used", HTTP 403 | Vertex API not enabled on the project | `gcloud services enable aiplatform.googleapis.com --project <project>` |
| Gemini never answers, "Model fallback activated" in a loop | default model unavailable on your access | `"model": "gemini-2.5-flash"` (or another model available to you) in `overrides.json`, then `update` |
| "This account requires setting the GOOGLE_CLOUD_PROJECT…" | Code Assist Standard or Enterprise licence with no project declared | `"code_assist": {"project": "<project>"}` in `overrides.json`, then `update` |
| "When using Vertex AI, you must specify…" | project and region missing | `"vertex": {"project": "<project>", "location": "<region>"}` in `overrides.json`, then `update` |
| Vertex variables are ignored | `selectedType` is still `gemini-api-key` | `update` with `vertex` in `overrides.json` fixes it; otherwise `/auth` in Gemini |
| "Skill conflict detected" at startup, the command does not do what the docs say | a personal copy in `~/.agents/skills` or in the repo's `.agents/skills` hides the kit's skill | `doctor` lists hidden skills; remove or rename the copy |
| agy asks for permission on every shell command | normal behaviour: agy permissions belong to each person | answer; "always allow" saves the rule in your agy settings, and the kit does not touch them |
| "It does not see my glossary" | CLI started outside the repo | `cd` into the repo, then start the CLI; the kit is global, the repo is not |
| a command from the docs cannot be found | command not in your profile ([profile table](getting-started.md#3-work-one-command-per-step)) | `"extra_commands": ["spec"]` in `overrides.json`, then `update`; `00_KIT.md` lists the installed commands |
| `/intent` or `/build` cannot be found | command not installed, or skill disabled | `doctor`; check `disabled_skills` and `disabled_commands` in `overrides.json` |
| "Skill existing file not managed by the kit" at `update` | a skill with the same name installed outside the kit | remove it, or add it to `disabled_skills` |
| dbt refuses to run: "Blocked by the kit: production target" | guardrail active | use the development target; an authorized person exports `AI_KIT_ALLOW_PROD=1` |
| `update` stops on "modified locally" | a generated file was edited | move the change to `30_USER.md` or a repo skill, restore, run again |

## Other cases

CLI-specific issues are on each CLI's page: [Gemini CLI](cli/gemini.md#gemini-troubleshooting), [Antigravity CLI](cli/agy.md#troubleshooting), [Codex CLI](cli/codex.md).

- **Python missing or too old**: check `python3 --version` on Mac, `py -3 --version` or `python --version` on Windows. Version 3.11 or later recommended, 3.9 minimum. Do not change company policies; ask IT support if needed.
- **PowerShell scripts blocked**: use `py -3 -m installer setup` in the kit folder. Do not bypass the policy.
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
