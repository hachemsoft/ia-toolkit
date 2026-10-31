# Getting started

This page is for someone who has never seen the kit. Fifteen minutes, in order.

## 1. Install (once)

Before you start: Python 3.9 or later (3.11 recommended), with its standard `venv` and `pip` modules, and your CLI must be available on the workstation, as provided or approved by your company. The kit installs its own libraries in a private environment of your home folder (`~/.ai-kit/runtime`), from the files of the ZIP: no download, no administrator rights, nothing to activate, your Python left as it is. If Python, `venv` or `pip` is missing or blocked, the installer says exactly what to ask IT.

1. Download `ai-kit-<version>.zip` from the Releases page of the kit repository (your organization's copy if it distributes its own, with its `organization.json`; otherwise the public one), and extract it into a folder you keep, for example `Documents`: this is your **kit folder**, from which you will run `update` and `doctor`. Windows: right-click the ZIP, **Extract All**. Mac: double-click the ZIP.
2. Run the installer:
   - **Windows**: double-click `Installer.cmd` in the extracted folder. If Windows asks to confirm running a downloaded file, follow your company's rule; if it is blocked, ask IT and change no security setting.
   - **Mac**: open **Terminal** (Applications > Utilities), type `sh ` (with a space), drag the `scripts/bootstrap.sh` file of the extracted folder into the window, press Enter. (A double-click launcher is not provided: macOS blocks unsigned downloaded scripts, see [validation](validation.md).)
3. The installer checks Python and prepares its private environment (plain text, a few seconds the first time), then shows a short guided screen. Arrow keys move, Space ticks, Enter confirms; Ctrl+C leaves at any time without changing your configuration. Nothing is changed outside your home folder.
   1. **This workstation**: Python, each supported CLI (found or not), the kit (installed or not), and the connection to the model, "not checked": the installer never calls the model.
   2. **Which CLIs do you use?** The CLIs found are ticked the first time; your choice is kept by every update afterwards. A CLI that is not installed yet can be ticked: its configuration is prepared for when IT installs it.
   3. **Your profile**, a starting point: **General** (the workflow and tools, the right choice if in doubt), **Java Developer**, **DevOps**, **Architect**, **Data Analyst**, **Data Developer**.
   4. **Your work email**, detected and shown for confirmation; it goes at the top of your personal context.
   5. **Skills, commands and agents**: keep what the profile proposes, or adjust: tick a domain playbook from another profile, an optional tool, a command, a review agent. What a choice needs is installed with it and said; what you turned off stays off.
   6. **Before installing**: what will be added, updated or removed, where, what stays untouched (your personal context, your `overrides.json`), and that nothing is billed. Then **Install**, **Back** (your answers are kept) or **Cancel**.
   7. A progress bar follows the real writes, then the **summary**: the kit configuration, each chosen CLI (found, or not found with its configuration prepared), the data connections (MCP) and your **next step**. The connection to the model stays "not verified", because a CLI found is not a CLI signed in. To check it, `doctor --live` makes one real call to the model (your provider may bill it) and, if it fails, says exactly what to do: sign in, a line to add, or what to ask IT (network, proxy, certificate).
4. **Your personal context** (optional, two minutes): the installer offers to open `30_USER.md` in Notepad (Windows) or your text editor (Mac). The file is already filled with headings and examples: *Language and style*, *My level and my domains*, *My default workflow*, *Report*, *Personal context*. Replace the "to fill in" lines with your role, your projects and your preferences, in plain text; save under the same name, then press Enter in the installer: it applies the file. Start a new session of your CLI to take it into account. Later: run the installer again and choose **Open my personal context**, or edit the file and run `update`.

Running the installer again once the kit is installed opens a menu: **Update**, **Change my choices**, **Check the installation** (local), **Open my personal context**, **Uninstall**, and, under Advanced, the billed check of the connection. Without a terminal (a script, CI), give the choices as options and nothing is asked: `setup --profile general --user first.last@company.com --target all`; `update` and `doctor` never ask. `--plain` (or `AI_KIT_PLAIN=1`) gives plain numbered questions and no colours.

   | `--target` (options, without the guided screen) | CLIs configured |
   | --- | --- |
   | none | those chosen at the last installation; the first time, those present on the workstation (Gemini CLI if none) |
   | `auto` | those present on the workstation; Gemini CLI if none |
   | `gemini`, `agy`, `codex`, `claude` | that CLI only |
   | `both` | Gemini CLI and Antigravity CLI |
   | `all` | all three |

### Run the kit

Every page of this documentation that says "run `update`" or "then `update`" means the command below. All four are run **from the kit folder**.

| Action | Windows | Mac |
| --- | --- | --- |
| the guided installer, or its menu once installed | double-click `Installer.cmd` | `sh scripts/bootstrap.sh` |
| `setup`: install or change your choices (guided at a terminal; `--profile`… to skip the questions) | `Installer.cmd setup` | `sh scripts/bootstrap.sh setup` |
| `update`: apply a change to `overrides.json`, pick up a newly installed CLI | `Installer.cmd update` | `sh scripts/bootstrap.sh update` |
| `doctor`: check, and say what to do (local) | `Installer.cmd doctor` | `sh scripts/bootstrap.sh doctor` |
| `doctor --live`: also check the connection with a real call to the model, which may be billed | `Installer.cmd doctor --live` | `sh scripts/bootstrap.sh doctor --live` |
| `usage`: what you used, locally | `Installer.cmd usage` | `sh scripts/bootstrap.sh usage` |
| `uninstall`: remove what the kit installed (`--dry-run` to see the list, `--yes` without a question, `--remove-runtime` to also remove the private environment) | `Installer.cmd uninstall` | `sh scripts/bootstrap.sh uninstall` |

- **Windows, a Command Prompt in the kit folder**: open the folder in Explorer, click the address bar, type `cmd`, press Enter.
- **Mac, a Terminal in the kit folder**: in Terminal, type `cd ` (with a space), drag the kit folder into the window, press Enter.

Options (`--profile`, `--team`, `--target`…) go after the action: `Installer.cmd setup --team data-platform`; `--team none` leaves your team.

To run `doctor` for a repo (it then also lists the repo skills named like kit skills), start it from the repo folder with the launcher's full path: Windows, in a Command Prompt opened in the repo, `"<kit folder>\Installer.cmd" doctor`; Mac, in a Terminal in the repo, `sh ` then drag `scripts/bootstrap.sh` from the kit folder, then ` doctor`, Enter.

### Where your files are

| File | Mac | Windows |
| --- | --- | --- |
| Your settings, `overrides.json` (created by `setup`, with one explanation line) | `~/.ai-kit/overrides.json` | `%USERPROFILE%\.ai-kit\overrides.json` |
| Your personal context, `30_USER.md` | `~/.gemini/30_USER.md` with Gemini CLI, otherwise `~/.ai-kit/context/30_USER.md` | `%USERPROFILE%\.gemini\30_USER.md`, otherwise `%USERPROFILE%\.ai-kit\context\30_USER.md` |

`~` and `%USERPROFILE%` are your home folder. Folders starting with a dot are hidden: on Windows, paste the path into the Explorer address bar (or open it with `notepad "%USERPROFILE%\.ai-kit\overrides.json"`); on Mac, in Finder press Cmd+Shift+G and paste the path, or Cmd+Shift+. to show hidden files. `doctor` prints the exact path of `30_USER.md`.

### New version

Download and extract the new ZIP, then run its installer, as for the first time, and choose **Update**. CLIs, profile, team, choices, `overrides.json` and `30_USER.md` are kept. The new folder is now your kit folder; the old one can be deleted, since nothing installed depends on it. `update` alone re-applies the version of the folder you have. In a git clone, it works in three steps and reports each one: fetch the new version (`git pull --ff-only`; never over local changes, never a reset or a merge), reinstall the kit package in the private environment, apply the configuration; if the fetch fails, it says the update is incomplete.

If your organization requires a Google Cloud project or a model, that is one line in `~/.ai-kit/overrides.json`, provided by your platform team; see [customization](customization.md#authentication-and-model). Otherwise there is nothing to declare.

## 2. First session (five minutes)

**One kit, all your repos.** You install the kit once per workstation, not once per repo. The kit folder only serves to run `setup`, `update` and `doctor` ([Run the kit](#run-the-kit)); you never work in it. To work, open a terminal in your own repo and start your CLI there (`gemini`, `agy` or `codex`) directly. In `projet-a`, the CLI reads the kit's global context (company, team, you) and the context of `projet-a`; in `projet-b`, the same kit and the context of `projet-b`. What belongs to a project stays in its repo; your preferences stay in your home folder. If the repo already has its context (`AGENTS.md`…), use it as is: do not initialize it again.

| You want to change | File or location | To apply it |
| --- | --- | --- |
| your personal preferences | `30_USER.md`, at the path shown by the installer ([where](#where-your-files-are)) | `update` if a CLI keeps a copy ([matrix](cli/matrice.md)), then a new CLI session |
| your selection of commands, skills, agents, MCP servers | `~/.ai-kit/overrides.json`: personal, for the whole workstation; there is no per-repo equivalent | `update` from the kit folder ([Run the kit](#run-the-kit)) |
| your project's conventions | `<repo>/AGENTS.md`, versioned with the repo | a new CLI session in the repo |
| a skill for this project, or a project variant of a kit skill | `<repo>/.agents/skills/<name>/SKILL.md`: give it a name of its own (for example `<repo>-sql-review`) and say in `AGENTS.md` when to use it; a kit skill's name gives different results per CLI ([matrix](cli/matrice.md)) | a new CLI session in the repo; the CLI may ask you to trust the folder first |

1. Go to your repo: `cd <repo folder>`. Without this, the agent does not see the project context.
2. Start your CLI: `gemini`, `agy`, `codex` or `claude`. In Gemini, agy and Claude Code, commands are written `/guide`; in Codex, `$guide`. This page writes them with `/`. The first time, Codex asks you to review the kit's hooks: answer "Trust all and continue" (they keep the agent from changing its own configuration).
3. Type: **"Initialize the project context"**. The agent proposes, file by file and with your approval, `AGENTS.md` (one page about the repo), `GLOSSARY.md` (the domain terms), `REVIEW.md` (what a review checks) and two `.gitignore` lines for working notes. If someone has already done this in the repo, skip it.
4. Type: `/guide I need to …` with today's need. It answers: which level of ceremony, which command, what it produces, an example prompt.

**Your repo and your layers.** The kit's layers (company, team, you) apply in every repo; each repo adds its own context on top: `AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`, its decisions (`docs/adr/`), its working notes (`docs/sdlc/`) and, if the team wants, its own skills in `.agents/skills/`. What wins when they disagree, and what a repo can and cannot change: [project layer](project-context.md).

## 3. Work: one command per step

Plain sentences are the normal way in: "explain how this area works", "make the export skip archived customers", "the job fails since Monday with this error", "review my changes". The commands below are shortcuts to the same steps.

| You want to | Type | You get |
| --- | --- | --- |
| frame an idea, a ticket, an incident | `/intent <what you want>` | an interview, then `intent.md` (local note) |
| turn the intent into a contract | `/spec` | `spec.md`, reviewed with the change |
| implement | `/build <task, ticket or spec>` | code and tests, one slice at a time; a `plan.md` to accept only for a large or sensitive change |
| verify | `/test` | the real output of the repo's checks |
| get a review before merging | `/review` (`full` for production) | the scope reviewed (commits, staged and unstaged changes, new files), then findings sorted by severity |
| describe the merge or pull request | `/ship` | the description in the repo's format, evidence included; nothing is pushed |
| understand a bug or a wrong number | `/diagnose <symptom>` | proven cause, fix, regression test |
| learn an area | `/learn <topic>` | lessons, quizzes, reference sheets in `docs/learn/<topic>/` |
| understand an area or the last answer | `/explain <area>` or `/explain` | a map in glossary terms, or a rephrasing |
| improve the agent's environment | `/retro` | proposals for `AGENTS.md`, checks, skills |
| record what got in the way, without stopping | `/friction <one sentence>` | a local line, picked up in the usage review; nothing is sent |

What each profile installs:

<!-- profile-table:start -->
| Profile | Workflow steps | Other commands | Agents |
| --- | --- | --- | --- |
| **General** (`general`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter |
| **Java Developer** (`java-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, code-reviewer, security-reviewer |
| **DevOps** (`devops`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, verifier, doubter, infra-reviewer, security-reviewer |
| **Architect** (`architect`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/guide` `/friction` `/learn` `/explain` `/retro` `/research` `/audit` | repo-investigator, verifier, doubter, architecture-reviewer, code-reviewer |
| **Data Analyst** (`data-analyst`) | `/intent` `/build` `/test` `/review` `/ship` `/diagnose` | `/guide` `/friction` `/learn` | repo-investigator, sql-reviewer, dbt-reviewer, verifier |
| **Data Developer** (`data-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter, sql-reviewer, dbt-reviewer |
<!-- profile-table:end -->

`/design` shapes an interface or answers a design question with a throwaway prototype; `/map` splits a large piece of work into decision tickets; `/triage` moves incoming tickets forward; `/research` investigates a question using primary sources; `/audit` finds modules worth deepening. `/ask`, `/handoff`, `/research`, `/wizard` and `/audit` can be added to any profile that lacks them: `{"extra_commands": ["handoff"]}` in `~/.ai-kit/overrides.json`, then `update`. Agent details: [agents](agents.md).

The rule that avoids running everything: **ceremony matches the stakes**, in three levels the agent states in one line. **quick**: a small local change, done and checked, no document. **standard**: a small feature, a short alignment in the conversation, then test-first. **full**: a large or fuzzy change, or production data: intent, spec, plan, and your acceptance before code. A go-ahead you already gave is not asked again.

## 4. What you will see, and what is normal

- `/help` lists the commands with English descriptions; the agent answers in your language. Artifacts keep English headings; their content is in the team's language.
- `intent.md` and `plan.md` are local notes, ignored by git; `spec.md` and `REVIEW.md` are versioned, unless the repo's `AGENTS.md` sets another convention. The agent never commits without your approval.
- A test changed by the agent is said and explained: it adapts a test only when you changed the expected behaviour on purpose, never to hide a regression.
- Your profile's domain playbooks (Java, infrastructure, architecture, SQL and dbt…) activate on their own when the task calls for them; you do not need to name them.
- In agy, a permission request before a shell command is normal: answer it; "always allow" saves your choice in your agy settings, and the kit does not touch them.
- Without a connected MCP server, the agent does not read your real data: provide the extracts, schemas or examples it needs, or have the platform team configure the connection.

## 5. Troubleshooting

1. Run the installer again and choose **Check the installation**; or Mac: `sh scripts/bootstrap.sh doctor` from the kit folder; Windows: in the kit folder, type `cmd` in the Explorer address bar and press Enter, then `Installer.cmd doctor`. It tells you what to do. For a sign-in or network problem, add `--live`: one real call to the model, which your provider may bill.
2. The [Troubleshooting](troubleshooting.md) page: one symptom, one cause, one command.
3. Otherwise a ticket, using the template on the [pilot](pilot.md) page. And on the spot, `/friction <one sentence>`: the usage review will pick it up. It will become a check, a line on that page or an eval case, never a repeated verbal explanation.

## 6. Later

- Your preferences (language, style, domains): `30_USER.md`, created for you and never rewritten by the kit ([where](#where-your-files-are)).
- Add or remove commands, playbooks, agents: run the installer again, **Change my choices**. MCP servers and guardrails: `~/.ai-kit/overrides.json`, then [`update`](#run-the-kit). What you decide, and what the organization and your team decide: [customization](customization.md).
- Write your own skill, or replace a kit skill for yourself, a repo or the team: [add or replace a skill](extending.md).
- Only when the team wants the agent to read and create tickets: in the repo, ask the agent "set up the workflow for this repo" (the `setup-workflow` skill; requires `glab` or `gh`). Nothing else needs a tracker.
- The day-to-day of each command: [workflow](workflow.md). A new version of the kit: [new version](#new-version). `doctor` says when what is installed is behind the kit folder.
