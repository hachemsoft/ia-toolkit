---
name: spec
description: "Design: turn an accepted intent.md into spec.md, policies applied while writing"
category: workflow
stage: Design
skills: [to-spec, domain-modeling]
artifact: "spec.md"
order: 20
---

Activate the to-spec skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) for its synthesis method and keep the domain-modeling skill in mind. Two rules of this kit override to-spec: the interview already happened in /intent (do not interview again, but ask when intent.md leaves a decision open), and the output is a file, spec.md, never a ticket on the issue tracker (turning a spec into tickets is the to-tickets skill, on request). Do not ask the user to run setup-workflow.

Stage: Design. Goal: spec.md that engineering can plan from, with areas of concern flagged.

Input: {{args}} (defaults to the most recent accepted intent.md under docs/sdlc/).

Read intent.md, AGENTS.md, GLOSSARY.md and the ADRs. Apply the team practices loaded in your context as constraints while writing, not as a review afterwards. Write spec.md next to its intent.md, in the same docs/sdlc/<date>-<slug>/ folder (spec.md is versioned: it is the contract reviewers read in the MR), following the template at the init-project-context skill's templates/spec.md when the repo has no convention; keep the template's section titles in English and write the content in the user's language: objective, scope and non-goals, requirements with acceptance criteria, data contracts (grain, keys, sources, freshness), constraints and policies applied, areas of concern, open questions. Flag every place where two policies conflict or where a requirement cannot be met. Use the terms of GLOSSARY.md when it exists; propose new terms for it rather than inventing synonyms. Do not break the spec into tickets here; say that /build or to-tickets does it. State in one line the level of ceremony inherited from intent.md. End with the file path and the list of concerns a reviewer must decide on.
