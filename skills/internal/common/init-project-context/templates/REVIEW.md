# Review instructions

The kit's review passes always run: Bugs, Security, Domain, Standards, Compliance, Tests. This file adds what is specific to
this repo; it never removes a pass. Delete the lines that do not apply.

## Domain
What a change in this repo must preserve. Keep the lines that apply:
- Service or library: API and event contracts stay compatible, database migrations are reversible, errors are handled at the boundary.
- Data: grain preserved through each join and aggregation, join cardinality, NULL and date rules, late-arriving data, partition filters present, bytes scanned and cost.
- Infrastructure: the plan was read, the blast radius is stated, nothing is destroyed or opened by accident, no secret in state or logs.
- <Rule of this repo's business, e.g. an amount is always stored in cents>

## Standards
<This repo's conventions the Standards pass checks, when they are not in CONTRIBUTING.md or enforced by CI; delete otherwise.>

## What Important means here
Reserve Important for findings that would break behaviour, data, security or a written policy. Style and naming are nits. This rule and the exclusions below never lower a Security or Tests finding.

## Cap the nits
Report at most five nits per review; summarise the rest as a count.

## Do not report
Generated files and build outputs (compiled artifacts, `target/`, `dist/`), and anything CI already enforces.
