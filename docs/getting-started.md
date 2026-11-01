# Getting started

Fifteen minutes, in order. What you need on day one is on this page; everything else is in the reference pages it links.

## 1. Install (once)

You need Python 3.9 or later (3.11 recommended) and your coding-agent CLI, as provided by your company. The kit installs into your home folder only: no administrator rights, no download, your Python left as it is. If something is missing, the installer says exactly what to ask IT.

1. Download `ai-kit-<version>.zip` from the Releases page (your organization's copy if it has one) and extract it into a folder you keep, for example `Documents`: this is your **kit folder**.
2. Run the installer:
   - **Windows**: double-click `Installer.cmd` in the extracted folder.
   - **Mac**: open **Terminal**, type `sh ` (with a space), drag `scripts/bootstrap.sh` from the extracted folder into the window, press Enter.
3. Answer the guided screen (arrows move, Space ticks, Enter confirms, Ctrl+C leaves without changing anything): which CLIs you use, your **profile** (**General** if in doubt; also Java Developer, DevOps, Architect, Data Analyst, Data Developer), your work email. Keep what the profile proposes; you can adjust later. Review, then **Install**.
4. Three quick questions fill your personal context: the language and length of the answers, how much the agent does on its own, your role in one line.

The installer never calls the model, so the summary says "connection not verified". Signing in and choosing the model are done in your CLI, as your IT procedure says.

### Run the kit

Every page that says "run `update`" means this, **from the kit folder**:

| Action | Windows | Mac |
| --- | --- | --- |
| the installer, or its menu once installed (update, change my choices, check, uninstall) | double-click `Installer.cmd` | `sh scripts/bootstrap.sh` |
| `update`: apply a change to your settings | `Installer.cmd update` | `sh scripts/bootstrap.sh update` |
| `doctor`: check and say what to do (local, free) | `Installer.cmd doctor` | `sh scripts/bootstrap.sh doctor` |

Windows, a Command Prompt in the kit folder: click the Explorer address bar, type `cmd`, press Enter. Mac, a Terminal in the kit folder: type `cd ` then drag the folder into the window. Every other action and option: [installer](installer.md).

### Where your files are

| File | Mac | Windows |
| --- | --- | --- |
| Your personal context, `30_USER.md` | `~/.ai-kit/context/30_USER.md` | `%USERPROFILE%\.ai-kit\context\30_USER.md` |
| Your settings, `overrides.toml` | `~/.ai-kit/overrides.toml` | `%USERPROFILE%\.ai-kit\overrides.toml` |

Folders starting with a dot are hidden: paste the path into the Explorer address bar, or in Finder press Cmd+Shift+G. `doctor` prints the exact paths.

### New version

Extract the new ZIP and run its installer, as the first time. Your CLIs, profile, choices and files are kept; the old kit folder can be deleted.

## 2. First session (five minutes)

You install the kit once per workstation; you work in your own repos.

1. Open a terminal in your repo and start your CLI there (`gemini`, `agy`, `codex` or `claude`). Commands are written `/guide`; in Codex, `$guide`. The first time, Codex asks you to review the kit's hooks: answer "Trust".
2. Type **`/me`**: a short interview (your domains, the tone you want, what annoys you in an assistant) that fills your personal context, shown before and after, written only with your agreement.
3. Type `/guide I need to …` with today's need: which command fits and what it produces.

When the agent offers to prepare the repo's context (`AGENTS.md`, `GLOSSARY.md`), accept if the repo has none. What a repo adds to your layers: [project layer](project-context.md).

## 3. Work: one command per step

Plain sentences are the normal way in: "explain how this area works", "the job fails since Monday with this error", "review my changes". The commands are shortcuts to the same steps.

| You want to | Type | You get |
| --- | --- | --- |
| frame an idea, a ticket, an incident | `/intent <what you want>` | an interview, then `intent.md` |
| turn it into a contract | `/spec` | `spec.md`, reviewed with the change |
| implement | `/build <task>` | code and tests, one slice at a time |
| verify | `/test` | the real output of the repo's checks |
| get a review before merging | `/review` | findings sorted by severity |
| describe the merge or pull request | `/ship` | the description, evidence included; nothing is pushed |
| understand a bug or a wrong number | `/diagnose <symptom>` | proven cause, fix, regression test |
| record what got in the way | `/friction <one sentence>` | a local line for the team's usage review |

The agent matches the ceremony to the stakes and says so on its first line: `Level: quick` (a small change, done and checked), `standard` (a short alignment, then test-first) or `full` (intent, spec, plan, your acceptance before code).

What each profile installs:

<!-- profile-table:start -->
| Profile | Workflow steps | Other commands | Agents |
| --- | --- | --- | --- |
| **General** (`general`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/me` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter |
| **Java Developer** (`java-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/me` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, code-reviewer, security-reviewer |
| **DevOps** (`devops`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/map` `/triage` `/me` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, infra-reviewer, security-reviewer |
| **Architect** (`architect`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/me` `/guide` `/friction` `/learn` `/explain` `/retro` `/research` `/audit` | repo-investigator, verifier, doubter, architecture-reviewer, code-reviewer |
| **Data Analyst** (`data-analyst`) | `/intent` `/build` `/test` `/review` `/ship` `/diagnose` | `/me` `/guide` `/friction` `/learn` | repo-investigator, sql-reviewer, dbt-reviewer, verifier |
| **Data Developer** (`data-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/me` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter, sql-reviewer, dbt-reviewer |
<!-- profile-table:end -->

Your profile's domain playbooks (SQL and dbt, Java, infrastructure…) activate on their own when the task calls for them. Every command and tool: [workflow](workflow.md) and [tools](tools.md).

## 4. What is normal

- The agent answers in your language; commands and artifact headings stay in English.
- `intent.md` and `plan.md` are local notes; `spec.md` is versioned. The agent never commits or pushes without your approval.
- A test changed by the agent is said and explained, never weakened to hide a regression.
- If one of your own skills or commands already has a kit name, the kit's takes a prefix (`/ai-kit-review`); the installer says which.
- A permission request before a shell command is normal: answer it.

## 5. When something goes wrong

1. Run the installer and choose **Check the installation** (or `doctor`): it says what to do.
2. [Troubleshooting](troubleshooting.md): one symptom, one cause, one fix.
3. Otherwise a ticket ([template](pilot.md)), and on the spot `/friction <one sentence>`.

## Later, when you need it

- Change your choices: run the installer, **Change my choices**. Your preferences: `/me` again.
- Settings you write yourself (MCP servers, guardrails), and what your organization and team decide: [customization](customization.md).
- Your own skills, or a repo's: [extending](extending.md).
