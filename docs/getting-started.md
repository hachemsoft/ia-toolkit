# Getting started

This page is for someone who has never seen the kit. Fifteen minutes, in order.

## 1. Install (once)

1. Get the kit into a durable folder, for example `Documents`: `git clone <repository url> ai-kit`. Without git: "Download ZIP" button on the repository page, then extract into `Documents/ai-kit`.
2. Open a terminal **in that folder**. Mac: right-click the folder, "New Terminal at Folder". Windows: in Explorer, open the folder, then type `powershell` in the address bar and press Enter.
3. Run:
   - Mac: `sh scripts/bootstrap.sh`
   - Windows: `.\scripts\bootstrap.ps1` (if scripts are blocked: `py -3 -m installer setup`)
4. Confirm the detected identity (your work email), then choose the profile:
   - **1. General**: the workflow and tools, without domain playbooks; the right choice if in doubt.
   - **2. Java Developer**: Maven or Gradle, Spring, JUnit; code and security review.
   - **3. DevOps**: Terraform, Kubernetes, Helm, CI/CD pipelines; infrastructure and security review.
   - **4. Architect**: architecture decisions (ADR), design, design review.
   - **5. Data Analyst**: you mostly write SQL, dbt, BigQuery queries, KPIs.
   - **6. Data Developer**: the same, plus Python or JavaScript code.

   You can change the profile at any time by running `setup` again. A skill or agent from another profile is added in `~/.ai-kit/overrides.json` (see [customization](customization.md)).
5. **Which CLI?** Nothing to choose in the usual case: the kit configures the CLIs it finds on the workstation (Gemini CLI, Antigravity CLI, Codex CLI), and Gemini CLI if none is installed yet. To force a choice: add `--target` to the command, for example `sh scripts/bootstrap.sh setup --target codex`.

   | `--target` | CLIs configured |
   | --- | --- |
   | `auto` (default) | those present on the workstation; Gemini CLI if none |
   | `gemini`, `agy`, `codex` | that CLI only |
   | `both` | Gemini CLI and Antigravity CLI |
   | `all` | all three |

   A CLI installed later is picked up at the next `update`.
6. Installation ends with a real call to the model. **Green**: you are done. Otherwise, the message says exactly what to do (a line to add, a command to run); do it, then run `doctor --live` again.

If your organization requires a Google Cloud project or a model, that is one line in `~/.ai-kit/overrides.json`, provided by your platform team; see [customization](customization.md#authentication-and-model). Otherwise there is nothing to declare.

## 2. First session (five minutes)

1. Go to your repo: `cd <repo folder>`. Without this, the agent does not see the project context.
2. Start your CLI: `gemini`, `agy` or `codex`. In Gemini and agy, commands are written `/guide`; in Codex, `$guide`. This page writes them with `/`.
3. Type: **"Initialize the project context"**. The agent proposes, file by file and with your approval, `AGENTS.md` (one page about the repo), `GLOSSARY.md` (the domain terms), `REVIEW.md` (what a review checks) and two `.gitignore` lines for working notes. If someone has already done this in the repo, skip it.
4. Type: `/guide I need to …` with today's need. It answers: which level of ceremony, which command, what it produces, an example prompt.

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

1. From the kit folder: `sh scripts/bootstrap.sh doctor --live` (Mac) or `.\scripts\bootstrap.ps1 doctor --live` (Windows). It tells you what to do.
2. The [Troubleshooting](troubleshooting.md) page: one symptom, one cause, one command.
3. Otherwise a ticket, using the template on the [pilot](pilot.md) page. And on the spot, `/friction <one sentence>`: the usage review will pick it up. It will become a check, a line on that page or an eval case, never a repeated verbal explanation.

## 6. Later

- Your preferences (language, style, domains): `30_USER.md`, created for you and never rewritten by the kit. It is in `~/.gemini/` if Gemini CLI is installed, otherwise in `~/.ai-kit/context/`; `doctor` shows its path.
- Add or remove commands, skills, agents, MCP servers, guardrails: `~/.ai-kit/overrides.json`, then `update`. See [customization](customization.md).
- Write your own skill, or replace a kit skill for yourself, a repo or the team: [add or replace a skill](extending.md).
- When the team wants the agent to read and create tickets: `setup-workflow` in the repo (requires `glab` or `gh`).
- Kit update: `git pull`, then `update` from its folder (without git: download the ZIP again, replace the folder, then `update`).
