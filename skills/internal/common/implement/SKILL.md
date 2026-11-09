---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
metadata:
  aikit-default: "true"
  aikit-version: "1.0.0"
  aikit-origin: "upstream"
  aikit-license: "skills/LICENSE-UPSTREAM-MIT"
  aikit-summary: "Implement a ticket or a spec, with TDD, then review."
  aikit-category: "workflow"
  aikit-tier: "core"
  aikit-requires: "tdd,code-review"
---

Implement the work described by the user in the spec or tickets.

If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask.

Call the Skill tool with "tdd" where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, call the Skill tool with "code-review" to review the work.

Commit only when the person agreed to commits in this session, or the repo's instructions say so; otherwise leave the changes uncommitted and say so in your report.
