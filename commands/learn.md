---
name: learn
description: "Learn a business perimeter or concept over several sessions: lessons, quizzes, reference sheets"
category: tool
skills: [teach]
order: 120
---

Activate the teach skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Topic: {{args}}

Workspace rules for this kit: shared material (reference/*.html, lessons/*.html, assets/) lives in the repo under docs/learn/<topic-slug>/ so the team can reuse it; personal state (MISSION.md, NOTES.md, learning-records/) lives outside the repo under ~/.ai-kit/learning/<topic-slug>/. Create both folders lazily and tell the user where things went. The repo's GLOSSARY.md is the glossary of this workspace: add business terms you teach to it in its format rather than keeping a separate one. When the topic is a data perimeter (sources, models, KPIs, rules, owners), start with a one-page perimeter brief and a ten-question quiz grounded in the repo's models and docs, and follow the perimeter-brief skill if installed. Never trust parametric knowledge for business facts: cite the repo, its docs or the resources list.
