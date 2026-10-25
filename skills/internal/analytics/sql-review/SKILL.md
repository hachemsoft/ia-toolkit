---
name: sql-review
description: "Review BigQuery or dbt SQL and investigate suspicious aggregations, duplicates or business results. Triggers: the number is wrong, duplicates, total that doesn't add up, review this query, join that multiplies rows, unexpected NULLs."
---

# sql-review

Identify the grain of each CTE and of the output. Check keys and cardinality before and after each join; measure row multiplication and do not hide a defect with DISTINCT. Check NULLs, zero denominators, time zones, time boundaries, deduplication and late-arriving data. Check exclusions against the project's business definition. Propose checks on volumes, uniqueness, totals and edge cases. Distinguish a certain defect from a hypothesis to confirm; for a wrong result whose cause is not obvious, follow the loop of the diagnosing-bugs skill with an assertion query as the signal. Present SQL fixes and validations without running any destructive operation.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "A DISTINCT fixes the duplicates" | It hides them; find the join that multiplies rows and fix its grain. |
| "The total is roughly right" | Roughly is not a validation; compare to the reference figure over a known period. |
| "NULLs are rare, we ignore them" | Rare in the numerator, catastrophic in a denominator; handle them explicitly. |
| "We've always used this date" | Event, record and processing dates diverge on late-arriving data; check which one the definition requires. |

## Forbidden
No DISTINCT to hide row multiplication. No fix proposed without the assertion query that proves it. No write or delete operation on tables: the review reads and proposes, and the person applies.
