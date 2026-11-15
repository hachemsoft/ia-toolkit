---
name: init-project-context
description: "Set up a repo's agent context: a short AGENTS.md (one per area in a monorepo), a REVIEW.md that adds the repo's review rules, a GLOSSARY.md prefilled with the repo's vocabulary, the git rule for local notes. Triggers: initialize the project context, create the AGENTS.md, set up the glossary or the review rules, prepare the repo or one of its apps for the agent."
metadata:
  aikit-default: "true"
  aikit-version: "1.4.0"
  aikit-origin: "internal"
  aikit-summary: "Set up a repo's agent context in one grouped proposal: short AGENTS.md (per area in a monorepo), REVIEW.md that adds to the kit's review, prefilled GLOSSARY.md, git rule for local notes; copies neither the templates nor the kit's rules."
  aikit-category: "setup"
  aikit-requires: "writing-for-agents,domain-modeling"
  aikit-optional-setup-workflow: "skip the ticket tracker: the workflow works without one"
  aikit-optional-to-spec: "not installed: nothing to configure for it"
  aikit-optional-to-tickets: "not installed: nothing to configure for it"
  aikit-optional-code-review: "not installed: propose REVIEW.md only if the team reviews with another tool that reads it"
  aikit-optional-review-guide: "not installed: its two .gitignore lines stay, harmless, for a person who installs it later"
---

# init-project-context

The kit never writes to a repo. This skill does, on request, after one grouped confirmation. Offer it when it becomes useful (the same question comes back, the checks are unknown, no `REVIEW.md` for a review), never as a prerequisite to a first task.

## Before writing
1. Read the repo: README, its project or build files (`pom.xml`, `build.gradle`, `build.gradle.kts`, `build.sbt`, `composer.json`, `pyproject.toml`, `package.json`, `go.mod`, `dbt_project.yml`, Terraform files…), test commands, CI, main folders. Note the actual commands, not assumed ones.
2. Check what already exists: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `REVIEW.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `GLOSSARY.md`, `GLOSSARY-MAP.md`, `docs/adr/`, and the repo's skills (`.agents/skills/`, `.claude/skills/`, `.codex/skills/`, `.gemini/skills/` in the repo). Never replace an existing file: propose an addition, and never repeat what one of them already says.
3. Several applications in the repo (workspace files, several build files in separate folders): read `references/monorepo.md` and follow it.
4. Read the `writing-for-agents` skill for the shape of `AGENTS.md`, and `domain-modeling` with `GLOSSARY-FORMAT.md` for the glossary.

## Proposed files
- "Verifying your work" block: generic, the same for a Data repo and an application repo, inferred automatically. Identify the stacks in use by reading, in this order, the CI first (`.gitlab-ci.yml`, `.github/workflows/`, `Jenkinsfile`), which already runs the real commands; then the stack files (`dbt_project.yml`, `pyproject.toml`, `setup.cfg`, `pytest.ini`, `package.json` and its scripts, `composer.json` and its scripts, `go.mod`, `pom.xml`, `build.gradle`, `build.sbt`, `Cargo.toml`); then `Makefile`, `justfile` or `Taskfile` and the README. For each stack found, fill in the command on the changed scope and the full command, the base branch, the shared files that require the full suite, the development target; delete the rows of absent stacks. Offer to run each command once, with agreement, and write only those that pass; report those that fail. If no stack or test command can be inferred from the repo, invent nothing: leave the block with its `<…>`, say so clearly, and ask the person to write the repo's test commands in it themselves (or to give them, so the agent writes them).
- `AGENTS.md` from `templates/AGENTS.md`: one page, only what belongs to this repo: Commands (with the language, framework and build tool versions), Verifying your work, Conventions, Architecture, Things the agent gets wrong, Where the rest lives. The kit's own rules (artifacts, tests, commits) stay in the kit context: never copy them. Replace each `<…>` with facts read from the repo; delete lines without a fact. Each "Things the agent gets wrong" line keeps the form `rule (since YYYY-MM: what happened)`; when the repo already has such rules, add the month you found them. "Where the rest lives" lists the repo's skills and what each is for; never name a personal skill or a kit skill in a repo file: they depend on each person's machine. A rule from a personal skill that must hold for the whole repo is written in `AGENTS.md` as a rule of the repo.
- `CLAUDE.md`: never created; Claude Code reads `AGENTS.md` when the repo has none. When the repo already has a `CLAUDE.md` that does not import `AGENTS.md`, propose `@AGENTS.md` as its first line. An existing `GEMINI.md` stays as it is: the kit already has Gemini CLI and agy read `AGENTS.md`. Never a second copy of the content.
- `GLOSSARY.md` in the `domain-modeling` format (example: `templates/GLOSSARY.md`). Collect the business terms found in the code, the APIs and the docs. For a data repo (dbt, SQL, pipelines), also propose the starter terms of `templates/GLOSSARY-DATA.md` that the repo really uses. Each term with its synonyms to avoid. When `GLOSSARY-MAP.md` exists (several contexts), propose each term in the glossary of the context it lists; do not create a map.
- `REVIEW.md` from `templates/REVIEW.md`, its first paragraph kept word for word (it names the six passes and says this file adds to them): what this repo adds to the kit's review passes (Bugs, Security, Domain, Standards, Compliance, Tests), which always run: its domain rules, its conventions not already in `CONTRIBUTING.md` or CI, what Important means here, the nit cap, what not to report. It never removes a pass, and its severity rule and exclusions never lower a Security or Tests finding. Adapt the data line to the scope, or remove it if the repo does not handle data.
- Git rule for local notes, with confirmation: add to `.gitignore` the lines `**/docs/sdlc/**/intent.md`, `**/docs/sdlc/**/plan.md`, `**/docs/sdlc/**/review-guide.md`, `**/docs/sdlc/**/review.html` and `**/docs/sdlc/handoff-*.md` (they also match the notes of an area in a monorepo); `spec.md` and `REVIEW.md` stay committed. If the team prefers to commit everything, write it in `AGENTS.md` and do not touch `.gitignore`.
- Artifact templates `templates/intent.md`, `templates/spec.md`, `templates/plan.md`: do not copy them into the repo; `/intent`, `/spec` and `/build` read them from this skill and write the filled artifact at the right time. The kit's convention (one folder per change, `docs/sdlc/<YYYY-MM-DD>-<slug>/`) needs no line in `AGENTS.md`; only a convention of the repo's own does.
- `docs/adr/`: do not create an empty file. If a structuring decision is already visible in the repo (a layer or module convention, a mandated tool, a storage or materialization choice), propose a first ADR following `ADR-FORMAT.md`; otherwise say the folder will be created with the first decision.

## Steps
1. Present one grouped proposal: in a monorepo, the map first; then each file to create or to add to (an existing file gets an addition, never a replacement), a summary of each, and its full content below. The person accepts it as a whole, drops some files, or asks for changes: one confirmation, not one per file.
2. Write what was accepted.
3. Only if the team wants the agent to read and create tickets, mention `setup-workflow` (GitLab via `glab`, GitHub or local markdown, and triage labels for `to-spec` and `to-tickets`); the rest of the kit works without a tracker.
4. After writing, test: ask the agent to perform a common task in the repo reading only these files. Add what was missing, remove what was not used.

## Forbidden
No writing without confirmation. No file that repeats the code structure or the kit's rules. No invented term: each glossary entry comes from the repo or from the person.
