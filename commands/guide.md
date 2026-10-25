---
name: guide
description: "Which command, tool and level of ceremony fits the situation"
category: tool
skills: [guide]
order: 110
---

Activate the guide skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Question: {{args}}

Answer in the user's language, in a few lines: the level of ceremony for the stakes described, the command or tool to use, the artifact it produces, and one example prompt.

Routing rules: a tweak (label, filter, colour) needs no command, /test if the repo has tests; anything that changes what is built or how a number is computed (a feature, a KPI or metric definition, a model, a report, an incident to fix for good) starts with /intent, which chains the kpi-definition playbook for KPIs, then /build; a large or fuzzy change adds /spec and /review; a wrong result, a bug or a regression is /diagnose; a merge request description is /ship; learning a business perimeter or a concept over time is /learn, never the way to change something; an explanation of a code area or of the last answer is /explain.

Propose only the commands listed under "Commandes" in the kit context (00_KIT.md): they are the ones installed for this profile. If a command that is not installed would fit (for example /spec, /review, /explain, /ask), say so in one line with how to enable it: add it to extra_commands in ~/.ai-toolkit/overrides.json, then run update. Do not list skill names unless asked.
