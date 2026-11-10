---
name: diagnose
description: "Maintain: diagnose a bug or regression with a tight feedback loop before fixing"
category: workflow
stage: Maintain
skills: [diagnosing-bugs]
artifact: "root cause + regression test"
order: 70
---

Activate the diagnosing-bugs skill (if this skill is not installed here, follow the instructions below directly).

Stage: Maintain. Goal: a confirmed root cause, a fix, and a regression test, with evidence.

Input: {{args}} (symptom, expected vs observed, environment, last known good if known).

Redact secrets in everything you show. If it is hurting production or users now, first propose a mitigation the person applies and can undo (revert, rollback, feature flag), then diagnose. Build a pass/fail signal that goes red on this bug before theorising (a failing test, an assertion, a check command; the matching domain playbook says which fits). Minimise, hypothesise one thing at a time, instrument, fix the cause, add the test that would have caught it, rerun. Domain playbooks: when an installed playbook (listed in 00_KIT.md) matches the files or the task, follow it, including its "In the kit commands" section for this step. State the level of ceremony in one line (a quick fix with a regression test, or an intent.md when the cause is structural). End with cause, fix, proof, remaining limits, and whether this should become an intent.md. Retry limit: if the same check still fails after three different fixes, stop looping; report what you tried, the literal failing output and what you suspect, and ask how to proceed. Report format: if the repo's AGENTS.md or the user's USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use cause, fix, proof, remaining limits.
