---
name: intent
description: "Plan: capture an idea, ticket or incident as intent.md"
category: workflow
stage: Plan
skills: [grill-with-docs]
artifact: "intent.md"
order: 10
---

Activate the grill-with-docs skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) (it builds on grilling and domain-modeling).

Stage: Plan. Goal: an intent.md the Design stage can act on, written in the originator's own words.

Input: {{args}}

Read-only stage: read AGENTS.md, GLOSSARY.md, docs and code with the file-reading and search tools only; never run shell commands, dbt or queries during the interview.

Match ceremony to stakes before starting: a small tweak needs no artifact, say so and stop here (the person does it, or runs /build); a small feature needs a short alignment then test-first; a large or fuzzy change needs the full artifact; anything touching production data, irreversible operations or personal data needs the full artifact plus an explicit risk section. State the level you chose in one line.

Interview in rounds until the frontier of open decisions is empty, then write intent.md with these sections: Problem, Proposed outcome, Affected users and systems, Constraints, Open questions. Use the template at the init-project-context skill's templates/intent.md; keep its section titles in English and write the content in the user's language. Location: one folder per change, docs/sdlc/<YYYY-MM-DD>-<slug>/intent.md, unless the repo documents another convention in AGENTS.md; intent.md is a local working note ignored by git by default; never overwrite an existing intent, create a new folder. Use the terms of GLOSSARY.md when it exists; propose new terms for it rather than inventing synonyms. When the intent concerns a KPI or a metric, follow the kpi-definition skill if installed, for grain, population, period and exclusions before closing the interview. Do not write code or a spec. End by stating the file path and the open questions that block acceptance.
