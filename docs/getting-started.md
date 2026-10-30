# Getting started

This page is for someone who has never seen the kit. Fifteen minutes, in order.

## 1. Install (once)

Before you start: Python 3.9 or later (3.11 recommended) and your CLI must be available on the workstation, as provided or approved by your company. The kit installs nothing else and needs no administrator rights. If Python is missing or blocked, the installer says exactly what to ask IT.

1. Download `ai-kit-<version>.zip` from the Releases page of the kit repository, and extract it into a folder you keep, for example `Documents`: this is your **kit folder**, from which you will run `update` and `doctor`. Windows: right-click the ZIP, **Extract All**. Mac: double-click the ZIP.
2. Run the installer:
   - **Windows**: double-click `Installer.cmd` in the extracted folder. If Windows asks to confirm running a downloaded file, follow your company's rule; if it is blocked, ask IT and change no security setting.
   - **Mac**: open **Terminal** (Applications > Utilities), type `sh ` (with a space), drag the `scripts/bootstrap.sh` file of the extracted folder into the window, press Enter. (A double-click launcher is not provided: macOS blocks unsigned downloaded scripts, see [validation](validation.md).)
3. The installer checks Python, then asks the questions below. Nothing is changed outside your home folder.
4. Confirm the detected identity (your work email), then choose the profile:
   - **1. General**: the workflow and tools, without domain playbooks; the right choice if in doubt.
   - **2. Java Developer**: Maven or Gradle, Spring, JUnit; code and security review.
   - **3. DevOps**: Terraform, Kubernetes, Helm, CI/CD pipelines; infrastructure and security review.
   - **4. Architect**: architecture decisions (ADR), design, design review.
   - **5. Data Analyst**: you mostly write SQL, dbt, BigQuery queries, KPIs.
   - **6. Data Developer**: the same, plus Python or JavaScript code.

   You can change the profile at any time by running `setup` again. A skill or agent from another profile is added in `~/.ai-kit/overrides.json` (see [customization](customization.md)).
5. **Which CLI?** Nothing to choose in the usual case: the kit configures the CLIs it finds on the workstation (Gemini CLI, Antigravity CLI, Codex CLI), and Gemini CLI if none is installed yet. To force a choice: add `--target` to the command, for example `sh scripts/bootstrap.sh setup --target codex` (Windows: `Installer.cmd setup --target codex`).

   | `--target` | CLIs configured |
   | --- | --- |
   | `auto` (default) | those present on the workstation; Gemini CLI if none |
   | `gemini`, `agy`, `codex` | that CLI only |
   | `both` | Gemini CLI and Antigravity CLI |
   | `all` | all three |

   A CLI installed later is picked up at the next `update`.
6. Installation ends with a real call to the model. **Green**: you are done. Otherwise, the installation is still complete, and the message says exactly what to do: sign in, a line to add, or what to ask IT (network, proxy, certificate). Do it, then run `doctor --live` again.
7. **Your personal context** (optional, two minutes): the installer shows the path of `30_USER.md` and offers to open it in Notepad (Windows) or your text editor (Mac). The file is already filled with headings and examples: *Language and style*, *My level and my domains*, *My default workflow*, *Report*, *Personal context*. Replace the "to fill in" lines with your role, your projects and your preferences, in plain text; save under the same name, then press Enter in the installer: it applies the file. Start a new session of your CLI to take it into account. Later: edit the same file, run `update` ([below](#run-the-kit)), then start a new session.

### Run the kit

Every page of this documentation that says "run `update`" or "then `update`" means the command below. All four are run **from the kit folder**.

| Action | Windows | Mac |
| --- | --- | --- |
| `setup`: install, change profile or team | double-click `Installer.cmd`, or `Installer.cmd setup` | `sh scripts/bootstrap.sh` |
| `update`: apply a change to `overrides.json`, pick up a newly installed CLI | `Installer.cmd update` | `sh scripts/bootstrap.sh update` |
| `doctor`: check, and say what to do | `Installer.cmd doctor --live` | `sh scripts/bootstrap.sh doctor --live` |
| `usage`: what you used, locally | `Installer.cmd usage` | `sh scripts/bootstrap.sh usage` |

- **Windows, a Command Prompt in the kit folder**: open the folder in Explorer, click the address bar, type `cmd`, press Enter.
- **Mac, a Terminal in the kit folder**: in Terminal, type `cd ` (with a space), drag the kit folder into the window, press Enter.

Options (`--profile`, `--team`, `--target`…) go after the action: `Installer.cmd setup --team data-platform`.

### Where your files are

| File | Mac | Windows |
| --- | --- | --- |
| Your settings, `overrides.json` (created by `setup`, with one explanation line) | `~/.ai-kit/overrides.json` | `%USERPROFILE%\.ai-kit\overrides.json` |
| Your personal context, `30_USER.md` | `~/.gemini/30_USER.md` with Gemini CLI, otherwise `~/.ai-kit/context/30_USER.md` | `%USERPROFILE%\.gemini\30_USER.md`, otherwise `%USERPROFILE%\.ai-kit\context\30_USER.md` |

`~` and `%USERPROFILE%` are your home folder. Folders starting with a dot are hidden: on Windows, paste the path into the Explorer address bar (or open it with `notepad %USERPROFILE%\.ai-kit\overrides.json`); on Mac, in Finder press Cmd+Shift+G and paste the path, or Cmd+Shift+. to show hidden files. `doctor` prints the exact path of `30_USER.md`.

### New version

Download and extract the new ZIP, then run its installer, as for the first time. Profile, team, `overrides.json` and `30_USER.md` are kept. The new folder is now your kit folder; the old one can be deleted, since nothing installed depends on it. `update` alone re-applies the version of the folder you have: it fetches a new version only in a git clone (it runs `git pull` first).

If your organization requires a Google Cloud project or a model, that is one line in `~/.ai-kit/overrides.json`, provided by your platform team; see [customization](customization.md#authentication-and-model). Otherwise there is nothing to declare.

## 2. First session (five minutes)

1. Go to your repo: `cd <repo folder>`. Without this, the agent does not see the project context.
2. Start your CLI: `gemini`, `agy` or `codex`. In Gemini and agy, commands are written `/guide`; in Codex, `$guide`. This page writes them with `/`. The first time, Codex asks you to review the kit's hooks: answer "Trust all and continue" (they keep the agent from changing its own configuration).
3. Type: **"Initialize the project context"**. The agent proposes, file by file and with your approval, `AGENTS.md` (one page about the repo), `GLOSSARY.md` (the domain terms), `REVIEW.md` (what a review checks) and two `.gitignore` lines for working notes. If someone has already done this in the repo, skip it.
4. Type: `/guide I need to …` with today's need. It answers: which level of ceremony, which command, what it produces, an example prompt.

**Your repo and your layers.** The kit's layers (company, team, you) apply in every repo; each repo adds its own context on top: `AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`, its decisions (`docs/adr/`), its working notes (`docs/sdlc/`) and, if the team wants, its own skills in `.agents/skills/`. What wins when they disagree, and what a repo can and cannot change: [project layer](project-context.md).

## 3. Work: one command per step

| You want to | Type | You get |
| --- | --- | --- |
| frame an idea, a ticket, an incident | `/intent <what you want>` | an interview, then `intent.md` (local note) |
| turn the intent into a contract | `/spec` | `spec.md`, reviewed in the MR |
| implement | `/build <ticket or spec>` | `plan.md` to accept, then code and tests, one slice at a time |
| verify | `/test` | the real output of the repo's checks |
| get a review before merging | `/review main` (`full` for production) | findings sorted by pass and severity |
| describe the merge request (MR) | `/ship` | the description, evidence included; nothing is pushed |
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
| **Data Analyst** (`data-analyst`) | `/intent` `/build` `/test` `/ship` `/diagnose` | `/guide` `/friction` `/learn` | repo-investigator, sql-reviewer, dbt-reviewer, verifier |
| **Data Developer** (`data-developer`) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` | `/design` `/map` `/triage` `/guide` `/friction` `/learn` `/explain` `/retro` | repo-investigator, code-reviewer, verifier, doubter, sql-reviewer, dbt-reviewer |
<!-- profile-table:end -->

`/design` shapes an interface or answers a design question with a throwaway prototype; `/map` splits a large piece of work into decision tickets; `/triage` moves incoming tickets forward; `/research` investigates a question using primary sources; `/audit` finds modules worth deepening. `/ask`, `/handoff`, `/research`, `/wizard` and `/audit` can be added to any profile that lacks them: `{"extra_commands": ["handoff"]}` in `~/.ai-kit/overrides.json`, then `update`. Agent details: [agents](agents.md).

The rule that avoids running everything: **ceremony matches the stakes**. A small fix needs no command. A small feature: a short `/intent`, then `/build`. Only a large change or a production change goes through `/spec` and `/review full`. Each command states in one line the level it chose.

## 4. What you will see, and what is normal

- `/help` lists the commands with English descriptions; the agent answers in your language. Artifacts keep English headings; their content is in the team's language.
- `intent.md` and `plan.md` are local notes, ignored by git; `spec.md` and `REVIEW.md` are versioned. The agent never commits without your approval.
- Your profile's domain playbooks (Java, infrastructure, architecture, SQL and dbt…) activate on their own when the task calls for them; you do not need to name them.
- In agy, a permission request before a shell command is normal: answer it; "always allow" saves your choice in your agy settings, and the kit does not touch them.
- Without a connected MCP server, the agent does not read your real data: provide the SQL and the authorized schemas, or have the platform team configure the connection.

## 5. Troubleshooting

1. Mac: `sh scripts/bootstrap.sh doctor --live` from the kit folder; Windows: in the kit folder, type `cmd` in the Explorer address bar and press Enter, then `Installer.cmd doctor --live`. It tells you what to do.
2. The [Troubleshooting](troubleshooting.md) page: one symptom, one cause, one command.
3. Otherwise a ticket, using the template on the [pilot](pilot.md) page. And on the spot, `/friction <one sentence>`: the usage review will pick it up. It will become a check, a line on that page or an eval case, never a repeated verbal explanation.

## 6. Later

- Your preferences (language, style, domains): `30_USER.md`, created for you and never rewritten by the kit ([where](#where-your-files-are)).
- Add or remove commands, skills, agents, MCP servers, guardrails: `~/.ai-kit/overrides.json`, then [`update`](#run-the-kit). What you decide, and what the organization and your team decide: [customization](customization.md).
- Write your own skill, or replace a kit skill for yourself, a repo or the team: [add or replace a skill](extending.md).
- When the team wants the agent to read and create tickets: in the repo, ask the agent "set up the workflow for this repo" (the `setup-workflow` skill; requires `glab` or `gh`).
- The day-to-day of each command: [workflow](workflow.md). A new version of the kit: [new version](#new-version). `doctor` says when what is installed is behind the kit folder.
