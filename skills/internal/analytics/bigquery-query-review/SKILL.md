---
name: bigquery-query-review
description: "Optimize a slow or expensive BigQuery query and check scans, partitions, joins and plan. Triggers: slow query, too expensive, bytes read, partition filter, execution plan, slots, this query scans everything."
---

# bigquery-query-review

Get the SQL, the schemas and the authorized scope. Examine partition filters, columns read, cardinalities and aggregations. Use a dry run to estimate bytes if available; that figure gives neither actual time nor slot consumption. Inspect the existing job's metrics for execution problems. Propose a change that preserves semantics and verify it on a representative scope; one change between two measurements, as in the diagnosing-bugs skill. Set a maximum budget before any new expensive run. Report before/after measurements, assumptions and trade-offs. Never claim that a LIMIT necessarily reduces bytes read.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "A LIMIT reduces bytes read" | No; only a partition or cluster filter reduces the scan. |
| "The dry run is enough" | It gives neither time nor slots; read the actual job for a slow query. |
| "It's faster, so it's cheaper" | Measure bytes and slots afterwards, with the same figures as before. |

## Forbidden
No run of an expensive query without a set budget and without a dry run when one is available. No rewrite that changes semantics without verifying it on a known scope. Never two changes between two measurements.

## In the kit commands
- `/build`: a BigQuery query follows this playbook (and bigquery-cost-review, if installed, before and after).
- `/diagnose`: cost or slowness in BigQuery starts with the query plan, as above.
