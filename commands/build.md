---
name: build
description: "Build: implement test-first, one slice at a time, with a plan proportionate to the change"
category: workflow
stage: Build
skills: [implement]
artifact: "diff + tests (plan.md for a full change)"
order: 30
---

Activate the implement skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) (it drives tdd and code-review).

Stage: Build. Goal: an implementation that does what was asked, verified, with no more ceremony than the change needs.

Input: {{args}} (a ticket, a spec.md section, or a short description).

Choose the ceremony level (quick, standard or full, as defined in the kit context 00_KIT.md) and state it in one line. A go-ahead the person already gave stands: do not ask for it again.

Step 1, plan, proportionate to the level. Quick: no plan file; say in one line what you change and how you check it, then go to step 2. Standard: a short alignment in the conversation (files, approach, proof); go on when the person agrees or has already asked you to proceed; no plan.md unless asked. Full: read spec.md, intent.md, AGENTS.md and GLOSSARY.md when they exist; produce plan.md where the repo keeps such notes (AGENTS.md), otherwise in the change folder docs/sdlc/<date>-<slug>/ next to spec.md or intent.md (create the folder when neither exists; plan.md is a local working note ignored by git by default), with: Files that change, Order of work, Risks, Proof (which tests or checks prove each step). Use the template at the init-project-context skill's templates/plan.md when the repo has no convention; keep its section titles in English and write the content in the user's language. Stress-test it: what could this break, which step is riskiest, which alternatives were rejected. Do not edit code until the person accepts the plan; if the CLI has a plan mode, use it for this step.
Step 2, implement: one thin slice at a time, red test first, minimal code, run the repo's checks, and commit per slice only when the repo works that way and the person has agreed to commits in this session (ask once). Domain playbooks: when an installed playbook (listed in 00_KIT.md) matches the files or the task, follow it, including its "In the kit commands" section for this step.
Step 3, verify, proportionate to the level: quick, the check that covers the change; standard and full, every check listed under "Verifying your work" in AGENTS.md for what changed. Paste the real output. Never report a check you did not run. If the ai-kit-verifier agent is available, delegate the final verification to it and relay its report.
End with: what changed, what was verified with its output, what remains. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use the default above. Retry limit: if the same check still fails after three different fixes, stop looping; report what you tried, the literal failing output and what you suspect, and ask how to proceed.
