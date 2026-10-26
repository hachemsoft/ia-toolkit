---
name: init-project-context
description: "Set up a repo's agent context: a short AGENTS.md, a GLOSSARY.md prefilled with the repo's vocabulary, a docs/ folder ready for ADRs. Triggers: initialize the project context, create the AGENTS.md, set up the glossary, prepare the repo for the agent."
---

# init-project-context

The kit never writes to a repo. This skill does, on request, with confirmation before each file.

## Before writing
1. Read the repo: README, `dbt_project.yml`, `pyproject.toml` or `package.json`, test commands, CI, main folders. Note the actual commands, not assumed ones.
2. Check what already exists: `AGENTS.md`, `GEMINI.md`, `GLOSSARY.md`, `GLOSSARY-MAP.md`, `docs/adr/`. Never replace an existing file: propose an addition.
3. Read the `writing-for-agents` skill for the shape of `AGENTS.md`, and `domain-modeling` with `GLOSSARY-FORMAT.md` for the glossary.

## Proposed files
- "Verifying your work" block: generic, the same for a Data repo and an application repo, inferred automatically. Identify the stacks in use by reading, in this order, the CI first (`.gitlab-ci.yml`, `.github/workflows/`, `Jenkinsfile`), which already runs the real commands; then the stack files (`dbt_project.yml`, `pyproject.toml`, `setup.cfg`, `pytest.ini`, `package.json` and its scripts, `go.mod`, `pom.xml`, `build.gradle`, `Cargo.toml`); then `Makefile`, `justfile` or `Taskfile` and the README. For each stack found, fill in the command on the changed scope and the full command, the base branch, the shared files that require the full suite, the development target; delete the rows of absent stacks. Offer to run each command once, with agreement, and write only those that pass; report those that fail. If no stack or test command can be inferred from the repo, invent nothing: leave the block with its `<…>`, say so clearly, and ask the person to write the repo's test commands in it themselves (or to give them, so the agent writes them).
- `AGENTS.md` from `templates/AGENTS.md`: one page, structured like the SDLC playbook's context file: Commands, Verifying your work, Conventions, Architecture, Things the agent gets wrong, Where the rest lives. Replace each `<…>` with facts read from the repo; delete lines without a fact. Each "Things the agent gets wrong" line keeps the form `rule (since YYYY-MM: what happened)`; when the repo already has such rules, add the month you found them. If the repo already uses `GEMINI.md`, keep it and add `@AGENTS.md` to it rather than duplicating.
- `GLOSSARY.md` in the `domain-modeling` format (example: `templates/GLOSSARY.md`). For a data repo (dbt, SQL, pipelines), start from the template's generic Data terms and remove those that do not apply. For any other repo, keep only the template's structure and collect the business terms found in the code, the APIs and the docs. Each term with its synonyms to avoid.
- `REVIEW.md` from `templates/REVIEW.md`: the review passes `/review` follows (bugs, security, data, compliance), what Important means, the nit cap. Adapt the data pass to the scope, or remove it if the repo does not handle data.
- Git rule for artifacts, with confirmation: add to `.gitignore` the lines `docs/sdlc/**/intent.md`, `docs/sdlc/**/plan.md` and `docs/sdlc/handoff-*.md` (local working notes); `spec.md` and `REVIEW.md` stay committed. If the team prefers to commit everything, write it in `AGENTS.md` and do not touch `.gitignore`.
- Artifact templates `templates/intent.md`, `templates/spec.md`, `templates/plan.md`: do not copy them into the repo; `/intent`, `/spec` and `/build` read them from this skill and write the filled artifact at the right time. Convention: one folder per change, `docs/sdlc/<YYYY-MM-DD>-<slug>/` containing `intent.md`, `spec.md`, `plan.md`; the folder's git history is the audit trail. Write this in `AGENTS.md`.
- `docs/adr/`: do not create an empty file. If a structuring decision is already visible in the repo (incremental materialization, layer convention, mandated tool), propose a first ADR following `ADR-FORMAT.md`; otherwise say the folder will be created with the first decision.

## Steps
1. Present the plan: files to create, a summary of each.
2. For each file, show the full content and wait for confirmation.
3. Then propose `setup-workflow` to declare the ticket tracker (GitLab via `glab`, GitHub or local markdown) and the triage labels that `to-spec`, `to-tickets` and `code-review` expect.
4. After writing, test: ask the agent to perform a common task in the repo reading only these files. Add what was missing, remove what was not used.

## Forbidden
No writing without confirmation. No file that repeats the code structure. No invented term: each glossary entry comes from the repo or from the person.
