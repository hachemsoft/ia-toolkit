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

Read-only stage: read AGENTS.md, GLOSSARY.md, docs and code with the file-reading and search tools only; never run shell commands, builds or queries during the interview.

Choose the ceremony level (quick, standard or full, as defined in the kit context 00_KIT.md) and state it in one line. Quick needs no intent.md: say so and stop here (the person does it, or runs /build). Standard: a short intent.md of a few lines. Full: the complete intent.md, plus an explicit risk section for production data, irreversible operations or personal data.

Interview in rounds until the frontier of open decisions is empty, then write intent.md with these sections: Problem, Proposed outcome, Affected users and systems, Constraints, Open questions. Use the template at the init-project-context skill's templates/intent.md; keep its section titles in English and write the content in the user's language. Location: the repo's convention in AGENTS.md when there is one; otherwise one folder per change, docs/sdlc/<YYYY-MM-DD>-<slug>/intent.md; intent.md is a local working note ignored by git by default; never overwrite an existing intent, create a new folder. Use the terms of GLOSSARY.md when it exists; propose new terms for it rather than inventing synonyms. Domain playbooks: when an installed playbook (listed in 00_KIT.md) matches the files or the task, follow it, including its "In the kit commands" section for this step. Do not write code or a spec. End by stating the file path and the open questions that block acceptance.
