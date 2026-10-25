# Review instructions

## Passes
Run four passes and tag each finding with its pass:
- Bugs: logic errors, broken edge cases, subtle regressions.
- Security: secrets in code or logs, injection, personal data in outputs or examples, access beyond the declared scope.
- Data: grain preserved through each join and aggregation, join cardinality, NULL and date rules, late-arriving data, partition filters present, bytes scanned and cost.
- Compliance: the change matches spec.md and plan.md, GLOSSARY.md terms, and the team practices.

## What Important means here
Reserve Important for findings that would break behaviour, corrupt or leak data, or breach a policy. Style and naming are nits.

## Cap the nits
Report at most five nits per review; summarise the rest as a count.

## Do not report
Generated files, compiled dbt artifacts under target/, and anything CI already enforces.

## Full mode
List the claims the change relies on (for example "grain is unchanged", "bytes scanned decrease", "replay is idempotent"). Doubt each one; look for proof in the diff, the tests or a query; report the ones without proof as Important.
