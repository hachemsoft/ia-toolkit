---
status: accepted
since: 4.10.0
---
# A project's context adds to the kit: REVIEW.md never removes a pass, AGENTS.md per layer, no CLAUDE.md by default

The `init-project-context` skill had drifted from what the kit reads in a project: its `REVIEW.md` template listed four
review passes when `code-review` runs six, and `code-review` let a repo's `REVIEW.md` "win", so a repo following the
template could switch off the Tests pass (weakened tests) and the smell baseline without meaning to. The skill also created
a one-line `CLAUDE.md` that `setup-workflow` then wrote into, and said nothing about a repo holding several applications.

Decisions:
- A repo's `REVIEW.md` **adds** to the kit's review passes (domain lines, severity rule, nit cap, exclusions); it never
  removes a pass, and its exclusions and severity rule never lower a Security or Tests finding. A repo that wants another review replaces the skill with its own
  `code-review` skill, an explicit choice.
- No `CLAUDE.md` by default: Claude Code reads a repo's `AGENTS.md` when the repo has no `CLAUDE.md` (its documentation,
  v2.1.277 and later, a setting on by default). When a repo already has a `CLAUDE.md`, `@AGENTS.md` is proposed at its top.
  `setup-workflow` writes into `AGENTS.md`.
- A monorepo gets layers, only where useful: a root `AGENTS.md` that is a map, one per family of applications for what
  they share, one per application only when it differs. A nested file starts by naming what it overrides, because the CLIs
  do not settle a conflict between a nested file and its parent the same way (Gemini CLI concatenates every file found).
- A project's `AGENTS.md` holds only what belongs to the project; the kit's own rules stay in the kit context.
- Contract tests keep the template and the consumers aligned.

**Why**: the review is the kit's safety net; a project file should be able to sharpen it, not quietly remove it. Project
files are shared with people and CI agents that may not have the kit, and copies of kit rules drift.

**Consequences**: an existing `REVIEW.md` that removed a pass no longer does; the review says so in its limits. A colleague
without the kit no longer reads the kit's rules in the project's `AGENTS.md`; a project that wants them for everyone writes
them as project rules. Nested-file loading on agy is not verified.

**Considered**: letting `REVIEW.md` keep winning (a template can disable the weakened-tests check); keeping the one-line
`CLAUDE.md` (redundant with native reading, and in conflict with `setup-workflow`); one `AGENTS.md` per application
everywhere (near-duplicate files); a script detecting the monorepo layout (the layouts vary too much; the person corrects
a proposed map instead).
