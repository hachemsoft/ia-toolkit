---
name: build
description: "Build: plan.md in plan mode, then implement one slice at a time, test-first"
category: workflow
stage: Build
skills: [implement]
artifact: "plan.md + diff + tests"
order: 30
---

Activate the implement skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) (it drives tdd and code-review).

Stage: Build. Goal: an accepted plan.md, then an implementation that matches it, verified.

Input: {{args}} (a ticket, a spec.md section, or a short description).

Match ceremony to stakes before starting: a small tweak needs no artifact, say so and do it; a small feature needs a short alignment then test-first; a large or fuzzy change needs the full artifact; anything touching production data, irreversible operations or personal data needs the full artifact plus an explicit risk section. State the level you chose in one line.

Step 1, plan: read spec.md, intent.md, AGENTS.md and GLOSSARY.md. Produce plan.md in the change folder docs/sdlc/<date>-<slug>/ next to spec.md or intent.md (create the folder when neither exists; plan.md is a local working note ignored by git by default), with: Files that change, Order of work, Risks, Proof (which tests or checks prove each step). Use the template at the init-project-context skill's templates/plan.md when the repo has no convention; keep its section titles in English and write the content in the user's language. State the level of ceremony you chose in one line. Stress-test it: what could this break, which step is riskiest, which alternatives were rejected. Do not edit code until the user accepts the plan; if Gemini plan mode is available, use it for this step.
Step 2, implement: one thin slice at a time, red test first, minimal code, run the repo's checks, and commit per slice only when the repo works that way and the person has agreed to commits in this session (ask once). Business playbooks, each only if installed: when the target is a dbt model, follow the dbt-model-change skill if installed, with dbt test as the red-green loop on the development target; when it is an incremental model or a replay, follow the incremental-replay skill if installed; when it is a BigQuery query, follow the bigquery-query-review skill if installed and the bigquery-cost-review skill if installed, before and after; when it is Python or JavaScript, follow the python-js-change skill if installed.
Step 3, verify: run every check listed under "Verifying your work" in AGENTS.md and paste the real output. Never report a check you did not run. If the ai-kit-verifier agent is available, delegate the final verification to it and relay its report.
End with: what changed, what was verified with its output, what remains. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use the default above. Retry limit: if the same check still fails after three different fixes, stop looping; report what you tried, the literal failing output and what you suspect, and ask how to proceed.
