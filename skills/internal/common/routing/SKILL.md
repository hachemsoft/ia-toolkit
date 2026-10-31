---
name: routing
description: "Kit router: which command, which tool and what level of ceremony for the situation described. Triggers: which skill for, where do I start, how do we do this here, guide, help with the workflow."
---

# routing
Reply in the person's language, in a few lines: the level of ceremony, the command or tool, the artifact produced, an example prompt. Mention skill names only if asked.

## Start here: four everyday uses
A plain sentence is the normal way in; a command is a shortcut to the same step. Offer these first, with an example in the person's words:
| Use | Say it | Shortcut |
| --- | --- | --- |
| Understand a repo or an area | "explain how orders are validated in this repo" | `/explain` |
| Change a behaviour | "make the export skip archived customers" | `/build` (with `/intent` first when the need is fuzzy) |
| Diagnose a problem | "the nightly job fails since Monday with this error: …" | `/diagnose` |
| Review changes | "review my changes before I open the merge request" (committed or not) | `/review` |

Nothing to set up first: no ticket tracker, no document to write before a first simple task. When a repo has no AGENTS.md yet and it would help (the same question keeps coming back, the checks are unknown), offer once to initialise the project context, as one grouped proposal that keeps what already exists.

Propose only the commands listed under "Commands" in the kit context (00_KIT.md): those are the ones installed for this profile. The tables below give the full map; when the command that would fit is not installed (for example `/spec`, `/review`, `/explain` for an analyst), say so in one line with how to enable it: `extra_commands` in `~/.ai-kit/overrides.json`, then `update`.

## Ceremony level (quick, standard, full: defined in 00_KIT.md)
| Stakes | Level | What to do | Commands |
| --- | --- | --- | --- |
| Small local change (label, typo, condition) | quick | do it, run the check that covers it | none; `/test` if the repo has tests |
| Visual or exploratory | quick | iterate with the agent, look, start again | `/design` for a throwaway prototype |
| Small feature | standard | short alignment in the conversation, then test-first | `/build`, `/test`, `/ship` |
| Large or fuzzy | full | intent, spec, plan, verification between phases | `/intent`, `/spec`, `/build` per ticket, `/review`, `/ship` |
| Production, irreversible, sensitive data | full | everything above, full review | `/review full`, guardrails active |

## The steps and their artifacts
- `/intent <idea>` → `intent.md` (Plan). `/map` when the work spans more than one session.
- `/spec` → `spec.md` (Design). `/design` for the shape of a module or a prototype.
- `/build <task>` → code and tests, one slice at a time; `plan.md` for a full change (Build).
- `/test` → actual output of the checks (Test).
- `/review [base|staged|local] [quick|full]` → ranked findings on everything that changed, committed or not (Deploy). `/ship` → the merge or pull request description, in the repo's format.
- `/diagnose <symptom>` → proven cause and regression test (Maintain). `/triage` for incoming tickets.

## The tools, at any time
`/learn` learn a perimeter or a concept · `/explain` map of an area or rephrasing · `/ask` questionnaire for a business owner · `/retro` improve the agent's environment · `/handoff` handover · `/research` primary sources · `/wizard` human steps · `/audit` code health.

## Setting up a repo
When it becomes useful, not before a first task: "Initialize the project context" (AGENTS.md, GLOSSARY.md, REVIEW.md, git rule for artifacts), proposed as one grouped change that keeps existing files. Only when the team wants the agent to read and create tickets (`/map`, `/triage`, to-tickets): `setup-workflow`, which requires `glab` or `gh` installed.

## Outside the commands
The installed domain playbooks (listed in 00_KIT.md) activate on their own when the task fits; `/build`, `/review` and `/diagnose` chain them. For the full map of the upstream flow, the `workflow-guide` skill is available as an option.
