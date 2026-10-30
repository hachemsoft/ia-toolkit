---
name: review
description: "Deploy: review the diff since a base on bugs, security and compliance with spec.md and plan.md"
category: workflow
stage: Deploy
skills: [code-review]
artifact: "review findings"
order: 50
---

Activate the code-review skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) for its review discipline (one axis at a time, findings ranked, nothing fixed). The passes of this kit replace its Standards/Spec axes: the standards are REVIEW.md and the practices loaded in your context, not CODING_STANDARDS.md or CONTRIBUTING.md; run the passes yourself in sequence, or delegate them to the ai-kit-code-reviewer agent when it is available; do not ask the user to run setup-workflow.

Stage: Deploy. Goal: ranked findings a human can act on before merging.

Input: {{args}} (a base ref such as main, optionally followed by "quick" or "full"; default base is the repo's default branch, default level is inferred from diff size and touched paths and stated).

Read REVIEW.md at the repo root when it exists and follow its passes, severity rule, nit cap and exclusions; otherwise use the template at the init-project-context skill's templates/REVIEW.md. Passes: Bugs (logic, edge cases, regressions), Security (secrets, injection, personal data in logs or outputs), Data (grain preserved, join cardinality, NULL and date rules, partition filters, cost), Compliance (matches spec.md and plan.md). For SQL and dbt files, run the Data pass with the installed domain playbooks (sql-review, bigquery-query-review, dbt-model-change) and the repo's conventions, or delegate it to the ai-kit-sql-reviewer and ai-kit-dbt-reviewer agents when they are available. Tag each finding with its pass and severity; Important is reserved for behaviour, data or policy breaks; cap nits at five. State in one line the level of ceremony you chose (quick or full) and why. When plan.md is not in the checkout (it is a local note by default), check compliance against spec.md only and say so. In "full" mode, before concluding, list the claims the change relies on, doubt each one and look for proof or a counter-example (delegate to the ai-kit-doubter agent when available). Do not fix anything; report only. Use the terms of GLOSSARY.md when it exists; propose new terms for it rather than inventing synonyms. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use findings tagged with pass and severity. Cross-area impact: when the repo has areas with their own AGENTS.md (a monorepo), name every other area reached by the changed files and what depends on them (for dbt, the descendants of the changed models), so the right owners review.
