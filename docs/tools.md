# Tools

Utilities independent of the flow, usable at any time. One tool = one command, one skill underneath, one sheet here. A tool without a sheet does not enter the core.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

Each sheet follows the same template: when, command, output, needs, skill, example.

## `/guide` — where to start
- **When**: you are unsure about the command, the tool or the level of ceremony. **Not** for starting the work.
- **Command**: `/guide <question>`.
- **Output**: a short answer in the person's language, with an example prompt.
- **Needs**: nothing.
- **Skill**: `routing` (internal). `workflow-guide` as an option for the full map of the upstream flow.
- **Example**: `/guide I need to change a KPI definition, where do I start?`

## `/learn` — learn an area or a concept
- **When**: newcomer to an area, building skills on a topic, over several sessions. **Not** for a one-off question (`/explain`).
- **Command**: `/learn <topic>`.
- **Output**: in the repo, `docs/learn/<topic>/` with short HTML lessons, quizzes, printable reference sheets, shared components; outside a repo, `~/.ai-kit/learning/<topic>/` with mission, notes and learning log. Domain terms go into the repo's `GLOSSARY.md`.
- **Needs**: access to the repo and its docs; web access helps for sources.
- **Skill**: `teach`. `perimeter-brief` playbook for a Data area when installed.
- **Example**: `/learn the billing area: sources, models, KPIs, date rules`.

## `/explain` — map or rephrasing
- **When**: unfamiliar code area or data flow; or the last answer was not understood.
- **Command**: `/explain <area>` or `/explain` alone after an unclear answer.
- **Output**: a map one level up (modules, models, callers, dependencies) in glossary terms, or a plain rephrasing; offer to save a sheet in `docs/learn/`.
- **Needs**: `GLOSSARY.md`, preferably.
- **Skills**: `zoom-out`, `wait-what`.
- **Example**: `/explain the path of the orders table up to the sales mart`.

## `/ask` — questionnaire for a business owner
- **When**: the information is neither in the code nor in the team. Option in every profile: `"extra_commands": ["ask"]` in `overrides.json`, then `update`.
- **Command**: `/ask <recipient and decision to unblock>`.
- **Output**: a questionnaire file, one idea per question, an answer to fill in under each; the answers feed `/intent`, `spec.md` or the glossary.
- **Needs**: nothing.
- **Skill**: `to-questionnaire`.
- **Example**: `/ask the product owner: definition of "active customer" for the retention KPI`.

## `/retro` — improve the agent's environment
- **When**: end of a session, especially if it went off track.
- **Command**: `/retro` or `/retro <log path>` after a `/clear`.
- **Output**: proposals to accept one at a time: lines for `AGENTS.md`, checks to automate, standards for `REVIEW.md`, skills to add or remove, missing commands.
- **Needs**: the current session.
- **Skill**: `retrospective`.
- **Example**: `/retro`.

## `/handoff` — handover (option)
- **When**: switching session, folder or person, or delegating a side task.
- **Command**: `/handoff [destination]`.
- **Output**: a handover file, `docs/sdlc/handoff-<date>.md` or the location the repo reserves for these notes (local note, not committed unless requested): goal, state, decisions and reasons, open questions, exact next steps.
- **Skill**: `handover`.

## `/research` — primary sources (Architect; option elsewhere)
- **When**: a documentation or API fact to establish, long reading to delegate.
- **Command**: `/research <question>`.
- **Output**: `docs/research/<topic>.md` with every claim sourced.
- **Needs**: sub-agents preferably, web access.
- **Skill**: `investigation`.

## `/wizard` — human steps (option)
- **When**: credentials, third-party consoles, approvals, one-off migration. **Not** if the agent can do the step itself.
- **Command**: `/wizard <procedure>`.
- **Output**: an interactive bash script. On Windows, the kit asks the model to give the PowerShell equivalent or the manual steps.
- **Skill**: `manual-steps`.

## `/audit` — code health (Architect; option elsewhere)
- **When**: spare time to make the code easier for an agent to work with.
- **Command**: `/audit [folder]`.
- **Output**: HTML report in the temporary folder, top-priority recommendation, idea to pick up with `/intent`.
- **Needs**: sub-agents preferably.
- **Skill**: `improve-codebase-architecture`.

## `/friction` — record what got in the way
- **When**: something slowed you down, surprised you or forced you to work around the kit: a command that does not do what its description says, a skill that triggers for nothing, an annoying guardrail, a wrong page, a missing tool. Right away, in one sentence, without leaving your work.
- **Command**: `/friction <one sentence>` or `/friction` alone, and the agent asks.
- **Output**: a line (short id, date, category, current command, sentence, plus kit version, profile, CLI and OS, added automatically) appended to `~/.ai-kit/frictions.jsonl`, on the workstation only. The sentence goes through standard input, so the shell expands nothing in it. When a version fixes it, `usage` says so, by its id.
- **What is recorded without you**: a `doctor --live` failure (authentication, quota, model) automatically becomes an `auth` line; the usage report also counts, from the logs, unknown commands typed and repeated requests within one session. The agent offers `/friction` when you correct it, when a check is red after "done", when you give up or repeat the same request, when it works around a skill or a guardrail, or when the ceremony was out of proportion; it writes nothing without you, unless you set `"frictions": "auto"` in `overrides.json` (`"off"` turns these offers off). `/retro` also offers to record what it finds about the kit. Nothing is sent. The usage report counts them; `usage --json` exports them when the person chooses to share; `scripts/usage-aggregate.py` groups them for the [usage review](usage-review.md), which turns them into tickets.
- **Needs**: Python (the `~/.ai-kit/bin/friction.py` script is installed by the kit); in some CLIs, an execution permission the first time.
- **Skill**: none; the command is enough.
- **Example**: `/friction /test reran the whole suite when I only wanted one model`.

## Enabling a tool marked "option"

One line in `~/.ai-kit/overrides.json`, then `update`: `{"extra_commands": ["handoff", "research"]}`. The command and its skills are installed; `disabled_commands` does the opposite. See [customization](customization.md).

## Adding a tool
A skill folder, an entry in `skills/catalog.json` with `category: tool`, a `commands/<name>.md` file in the [pivot format](format.md), a sheet here, a case in `evals/cases/`.
