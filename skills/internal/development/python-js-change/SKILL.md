---
name: python-js-change
description: "Develop or review a Python or JavaScript feature in an existing repo. Triggers: add a feature in Python or JavaScript or TypeScript, fix this function, an API endpoint, review this Python or JS code. Not for: SQL in a dbt project, or infrastructure files."
metadata:
  aikit-default: "false"
  aikit-version: "1.1.0"
  aikit-origin: "internal"
  aikit-summary: "Develop or review a Python or JavaScript feature in an existing repo."
  aikit-category: "domain"
  aikit-requires: "tdd"
  aikit-optional-codebase-design: "before adding an interface, keep it small with a deep implementation, and add a seam only where a test needs one"
  aikit-optional-mr: "describe the delivery in the merge request (MR) or pull request (PR) format the repo uses: what changed, why, how it was verified"
---

# python-js-change

Read the repo's instructions, dependencies and neighbouring examples. Identify API boundaries, expected errors and side effects. Reuse existing patterns and avoid an implicit framework migration. Preserve public contracts, existing structured logs and the secret-handling rules. Develop with the tdd skill (standard and full levels, once the acceptance test is approved; quick: the existing checks): a red test when it helps, minimal code, refactor. Before adding an interface, apply the vocabulary of the codebase-design skill: small interface, deep implementation, testable seam. Check the diff and run the relevant validations; describe the delivery with the mr skill. Keep repo-specific conventions in that repo.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "Too simple for a test" | At standard or full level, writing it takes a minute; a quick change is proven by the existing checks, named. |
| "I tested it by hand" | A manual run is not repeatable; turn it into a test or paste the exact output. |
| "I'll migrate the framework along the way" | Out of scope; a migration is a change in its own right with its own plan. |
| "The existing tests already cover this" | Name them; if you cannot, they do not cover it. |

## In the kit commands
- `/build`: a Python or JavaScript change follows this playbook.
