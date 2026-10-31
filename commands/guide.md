---
name: guide
description: "Which command, tool and level of ceremony fits the situation"
category: tool
skills: [routing]
order: 110
---

Activate the routing skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Question: {{args}}

Answer in the user's language, in a few lines: the ceremony level (quick, standard or full, as defined in 00_KIT.md), the command or tool to use, the artifact it produces, and one example prompt. A plain sentence works as well as a command: say so.

Routing rules: a quick change (a label, a typo, a condition) needs no command, /test if the repo has tests; a standard change (a small feature, an API or a contract, a computed result) is /build directly, with /intent first when the need is not clear yet; a full change (large or fuzzy, or production data) goes /intent, /spec, /build, /review; reviewing changes, committed or not, is /review; a wrong result, a bug or a regression is /diagnose; a merge request description is /ship; learning a business perimeter or a concept over time is /learn, never the way to change something; an explanation of a code area or of the last answer is /explain.

Propose only the commands listed under "Commands" in the kit context (00_KIT.md): they are the ones installed for this profile. If a command that is not installed would fit (for example /spec, /review, /explain, /ask), say so in one line with how to enable it: add it to extra_commands in ~/.ai-kit/overrides.json, then run update. Do not list skill names unless asked.
