---
name: python-js-change
description: "Develop or review a Python or JavaScript feature in an existing repo."
---

# python-js-change

Read the repo's instructions, dependencies and neighbouring examples. Identify API boundaries, expected errors and side effects. Reuse existing patterns and avoid an implicit framework migration. Preserve public contracts, existing structured logs and the secret-handling rules. Develop with the tdd skill: red test, minimal code, refactor. Before adding an interface, apply the vocabulary of the codebase-design skill: small interface, deep implementation, testable seam. Check the diff and run the relevant validations; describe the delivery with the mr skill. Keep repo-specific conventions in that repo.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "Too simple for a test" | Then writing it takes a minute; otherwise say in one line why the change is trivial. |
| "I tested it by hand" | A manual run is not repeatable; turn it into a test or paste the exact output. |
| "I'll migrate the framework along the way" | Out of scope; a migration is a change in its own right with its own plan. |
| "The existing tests already cover this" | Name them; if you cannot, they do not cover it. |
