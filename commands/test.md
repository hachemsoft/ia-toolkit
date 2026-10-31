---
name: test
description: "Test: run the repo's checks and paste the real output; never weaken a test to hide a regression"
category: workflow
stage: Test
skills: [tdd]
artifact: "verification output"
order: 40
---

Activate the tdd skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Stage: Test. Goal: evidence from the toolchain that the current change works.

Input: {{args}} (optional: a scope, a test name, or a behaviour to cover).

First, read AGENTS.md with the file-reading tool (never assume or recall its content). Scope rule, whatever the repo or the team: test what changed and what depends on it. List the changed files against the base branch (git diff --name-only <base>...HEAD, plus uncommitted changes); for each stack touched, run its "Changed" command from the table under "Verifying your work"; run the "Full" command when a shared file changed (a shared module, macro or configuration, a lockfile, the shared test configuration) or when the input asks for the full suite. If AGENTS.md is missing or has no such table, say so once, apply the same rule with the repo's own tools (the test runner's changed-files mode, the tests of the changed modules, or what the matching domain playbook says), and suggest adding the block with "Initialise le contexte du projet". To find the repo's own tools, read the CI configuration first (.gitlab-ci.yml, .github/workflows/), then the stack files (dbt_project.yml, pyproject.toml, package.json scripts, go.mod, pom.xml, Cargo.toml), then Makefile or the README. If no test command can be deduced, do not invent one: say so, ask the person for the repo's test commands, and suggest writing them under "Verifying your work" in AGENTS.md so the next run is automatic. Paste the literal output. If a test fails, fix the code; never weaken, skip or delete a test to hide a regression. If the change alters the expected behaviour on purpose (a contract change the person asked for), update the test to the new contract, say which test changed and why, and keep a test that proves the new behaviour. If a behaviour has no test yet, write the failing test first, then the code. State in one line the level of ceremony you chose (quick check or full suite) and why. Report: commands run, pass/fail per command, what is still unverified. Never claim a run you did not perform. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise use commands run, pass/fail per command, what is still unverified. Cross-area impact: when the repo has areas with their own AGENTS.md (a monorepo), name every other area reached by the changed files and what depends on them (as the matching domain playbook defines it), so the right owners review.
