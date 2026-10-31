# Review instructions

## Passes
Run four passes and tag each finding with its pass. Keep, in the Domain pass, the lines that apply to this repo:
- Bugs: logic errors, broken edge cases, subtle regressions.
- Security: secrets in code or logs, injection, personal data in outputs or examples, access beyond the declared scope.
- Domain: what this kind of change must preserve.
  - Service or library: API and event contracts stay compatible, database migrations are reversible, errors are handled at the boundary.
  - Data: grain preserved through each join and aggregation, join cardinality, NULL and date rules, late-arriving data, partition filters present, bytes scanned and cost.
  - Infrastructure: the plan was read, the blast radius is stated, nothing is destroyed or opened by accident, no secret in state or logs.
- Compliance: the change matches spec.md and plan.md, GLOSSARY.md terms, and the team practices.

## What Important means here
Reserve Important for findings that would break behaviour, corrupt or leak data, or breach a policy. Style and naming are nits.

## Cap the nits
Report at most five nits per review; summarise the rest as a count.

## Do not report
Generated files and build outputs (compiled artifacts, `target/`, `dist/`), and anything CI already enforces.

## Full mode
List the claims the change relies on (for example "the API stays backward compatible", "grain is unchanged", "the plan destroys nothing"). Doubt each one; look for proof in the diff, the tests or a query; report the ones without proof as Important.
