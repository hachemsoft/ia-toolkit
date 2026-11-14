---
name: code-change
description: "Develop or review a change to application code, in any language (PHP, Java, Go, Scala, Python, JavaScript or TypeScript, and others), in an existing repo. Triggers: add a feature, an endpoint or a field, fix this function or this service, change a module, review this code. Not for: SQL or dbt models, infrastructure or deployment files."
metadata:
  aikit-default: "false"
  aikit-version: "1.0.0"
  aikit-origin: "internal"
  aikit-summary: "Develop or review a change to application code, in any language, in an existing repo."
  aikit-category: "domain"
  aikit-requires: "tdd"
  aikit-optional-codebase-design: "before adding an interface, keep it small with a deep implementation, and add a seam only where a test needs one"
  aikit-optional-mr: "describe the delivery in the merge request (MR) or pull request (PR) format the repo uses: what changed, why, how it was verified"
---

# code-change

Read the repo's instructions (`AGENTS.md`), its build and dependency files, the language and framework versions, and two neighbouring files that already do something similar. Follow their patterns: layering, dependency injection, error handling, data mapping, logging. Do not introduce a new library, annotation, framework or style the repo does not already use, and avoid an implicit framework migration: either is a team decision. Preserve public contracts: API signatures, serialized formats (JSON fields, events), database migrations already applied, configuration keys, existing structured logs. Secrets stay in external configuration, never in code, tests or logs.

Develop with the tdd skill (standard and full levels, once the acceptance test is approved; quick: the existing checks): a red test at the lowest level that proves the behaviour, when it helps, minimal code, refactor; an integration test only when the behaviour crosses a boundary (database, HTTP, message queue). Before adding an interface, apply the vocabulary of the codebase-design skill: small interface, deep implementation, testable seam. Run the repo's verification commands (those of `AGENTS.md`, else the build tool's own) and report their output. Describe the delivery with the mr skill. Conventions that belong to one repo stay in that repo's `AGENTS.md`, not here.

Language standard, tools and classic traps: read references/<language>.md only when the change is in that language. Available: references/python.md, references/javascript.md (and TypeScript), references/java.md, references/php.md, references/go.md, references/scala.md. Run the formatter, linter and type checker the repo already declares; never add one: that is a team decision. Any other language: the body above is enough.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "Too simple for a test" | At standard or full level, writing it takes a minute; a quick change is proven by the existing checks, named. |
| "I tested it by hand" | A manual run is not repeatable; turn it into a test or paste the exact output. |
| "The build is too long, I won't run it" | Run at least the touched module or package and say what was not run. |
| "I'll add this library, it will be shorter" | A new dependency is a team decision; follow the repo's style. |
| "I'll migrate the framework along the way" | Out of scope; a migration is a change in its own right with its own plan. |
| "I'll mock everything, it's faster" | One mock per external boundary; test business logic with real objects. |
| "I'll rename this field while I'm at it" | That is a contract change; decide and version it separately. |
| "The existing tests already cover this" | Name them; if you cannot, they do not cover it. |

## In the kit commands
- `/build`: a change to application code follows this playbook, whatever the language.
