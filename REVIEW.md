# Review instructions

The kit's review passes always run: Bugs, Security, Domain, Standards, Compliance, Tests. This file adds what is specific to
this repo; it never removes a pass.

## Domain
What a change in this repo must preserve:
- No model call and no network in the engine or the tests (ADR 0004); `evals/run.py` calls a model only with `--confirm-paid-run`.
- Nothing the agent may run lifts a guardrail, changes the kit's or a CLI's configuration, or bills a model (ADR 0006, 0030); a person's settings (`aikit.toml`, CLI settings, agy permissions) are never written by the kit.
- The four CLIs stay on the same footing: a behaviour added for one is checked on the others, or its limit is written in `docs/cli/`.
- Installs keep working without administrator rights, offline from the ZIP, on Windows paths (spaces, backslashes, `cp1252` console).
- A test is never weakened, skipped or deleted to pass; a contract changed on purpose names the test and why (kit context).
- The texts loaded at every session stay within their budgets (`docs/extending.md`); a raised budget says why in the CHANGELOG.

## Standards
- Repo public and generic: no company, person, internal project or tool name, not even split.
- A general page names no CLI outside a table.
- Every installed-file change regenerates `tests/golden/install-snapshot.json`; every skill or agent change raises its `aikit-version`.
- A user-facing behaviour change comes with an eval case or a model-free test that locks the wording the evals measure.

## What Important means here
Reserve Important for findings that would break an install, a guardrail, a CLI's behaviour, offline or Windows use, or a written policy. Style and naming are nits. This rule and the exclusions below never lower a Security or Tests finding.

## Cap the nits
Report at most five nits per review; summarise the rest as a count.

## Do not report
Generated files (`tests/golden/install-snapshot.json`, `versions.lock.json`, `workflows/*.md`, `build/`, `dist/`), `evals/results/`, and anything CI already enforces (ruff, the schemas, `check_skills.py`, `check_news.py`).
