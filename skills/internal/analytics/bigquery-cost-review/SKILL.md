---
name: bigquery-cost-review
description: "Review the cost of a BigQuery query, model or job before and after a change: bytes read, partitions, clustering, slots, frequency. Triggers: BigQuery cost, bill, bytes scanned, expensive query, optimize cost, why does this cost so much."
---

# bigquery-cost-review

Cost is measured, not eyeballed. One change between two measurements.

## Steps
1. Get the SQL, the schema of the tables read (partitioning, clustering), the run frequency and the billing model (on-demand or slots).
2. Measure before: bytes estimate from a dry run, and for a job already run, bytes billed, slot-ms and duration from the job history. Note the three figures; a dry run gives neither time nor slots.
3. Look, in this order, for: a missing or non-pushed-down partition filter (function on the partition column, join before filter), columns read needlessly, unpartitioned tables read in full, joins that multiply rows before aggregating, repeated subqueries, intermediate results that deserve a table.
4. Propose one change at a time that preserves semantics. Verify the results are equal on a representative scope with a comparison query. Measure after, with the same three figures.
5. Convert to monthly cost: bytes or slots per run times the frequency. That number decides whether the change is worth its complexity.
6. Set a maximum budget before any new expensive run; refuse to run a query whose estimate exceeds that budget without agreement.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "A LIMIT reduces bytes read" | No: BigQuery reads whole columns; only a partition or cluster filter reduces the scan. |
| "The dry run says it's small" | The dry run ignores slots and time; look at the actual job for a slow query. |
| "It's a small query" | A small query run every five minutes costs more than a large monthly one; count the frequency. |
| "SELECT * is easier to maintain" | Every column read is billed; name the columns. |
| "We optimized, so it's necessarily cheaper" | Measure after, with the same figures as before; otherwise it is not an optimization, it is a hypothesis. |

## Forbidden
No recommendation without a before and after measurement. No run beyond the set budget. No semantic change presented as an optimization.

## In the kit commands
- `/build` and `/diagnose`: measure before and after the change, as above.
