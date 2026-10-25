---
name: guide
description: "Kit router: which command, which tool and what level of ceremony for the situation described. Triggers: which skill for, where do I start, how do we do this here, guide, help with the workflow."
---

# guide

Reply in the person's language, in a few lines: the level of ceremony, the command or tool, the artifact produced, an example prompt. Mention skill names only if asked.

Propose only the commands listed under "Commands" in the kit context (00_KIT.md): those are the ones installed for this profile. The tables below give the full map; when the command that would fit is not installed (for example `/spec`, `/review`, `/explain` for an analyst), say so in one line with how to enable it: `extra_commands` in `~/.ai-kit/overrides.json`, then `update`.

## Level of ceremony first
| Stakes | What to do | Commands |
| --- | --- | --- |
| Tweak (label, filter, colour) | do it, check it yourself | none; `/test` if the repo has tests |
| Visual or exploratory | iterate with the agent, look, start again | `/design` for a throwaway prototype |
| Small feature | short framing, then test-first | short `/intent`, `/build`, `/test`, `/ship` |
| Large or fuzzy | spec, phased plan, verification between each phase | `/intent`, `/spec`, `/build` per ticket, `/review`, `/ship` |
| Production, irreversible, sensitive data | everything above, full review | `/review full`, hooks active |

## The steps and their artifacts
- `/intent <idea>` → `intent.md` (Plan). `/map` when the work spans more than one session.
- `/spec` → `spec.md` (Design). `/design` for the shape of a module or a prototype.
- `/build <ticket>` → `plan.md`, then code and tests, one slice at a time (Build).
- `/test` → actual output of the checks (Test).
- `/review [base] [quick|full]` → ranked findings (Deploy). `/ship` → merge request (MR) description.
- `/diagnose <symptom>` → proven cause and regression test (Maintain). `/triage` for incoming tickets.

## The tools, at any time
`/learn` learn a perimeter or a concept · `/explain` map of an area or rephrasing · `/ask` questionnaire for a business owner · `/retro` improve the agent's environment · `/handoff` handover · `/research` primary sources · `/wizard` human steps · `/audit` code health.

## Setting up a repo
First time: "Initialize the project context" (AGENTS.md, GLOSSARY.md, REVIEW.md, git rule for artifacts). Later, when the team wants the agent to read and create tickets (`/map`, `/triage`, to-tickets): `setup-workflow`, which requires `glab` or `gh` installed.

## Outside the commands
The Data domain skills (SQL, dbt, BigQuery, Python/JS) activate on their own when the task fits; `/build` and `/diagnose` chain them. For the full map of the upstream flow, the `workflow-guide` skill is available as an option.
