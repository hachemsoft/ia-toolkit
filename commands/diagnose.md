---
name: diagnose
description: "Maintain: diagnose a bug or regression with a tight feedback loop before fixing"
category: workflow
stage: Maintain
skills: [diagnosing-bugs]
artifact: "root cause + regression test"
order: 70
---

Activate the diagnosing-bugs skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Stage: Maintain. Goal: a confirmed root cause, a fix, and a regression test, with evidence.

Input: {{args}} (symptom, expected vs observed, environment, last known good if known).

Redact secrets in everything you show. Build a pass/fail signal that goes red on this bug before theorising; for data, that signal is usually an assertion query (duplicates on the key, NULLs, a total) or a dbt test. Minimise, hypothesise one thing at a time, instrument, fix the cause, add the test that would have caught it, rerun. Business playbooks, each only if installed: when the symptom is a wrong result in SQL or dbt, follow the sql-review skill if installed, for grain and cardinality checks; when it is cost or slowness in BigQuery, follow the bigquery-query-review skill if installed for the plan and the bigquery-cost-review skill if installed for the measure before and after; when an incremental model duplicates or loses rows, follow the incremental-replay skill if installed; when a deployment, a pipeline or an infrastructure change fails, follow the infra-change skill if installed, with read-only evidence only. State the level of ceremony in one line (a quick fix with a regression test, or an intent.md when the cause is structural). End with cause, fix, proof, remaining limits, and whether this should become an intent.md. Retry limit: if the same check still fails after three different fixes, stop looping; report what you tried, the literal failing output and what you suspect, and ask how to proceed. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use cause, fix, proof, remaining limits.
