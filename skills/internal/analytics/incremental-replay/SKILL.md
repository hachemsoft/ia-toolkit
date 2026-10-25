---
name: incremental-replay
description: "Design or fix an incremental model and its replay: unique key, late-arriving data, reprocessing window, idempotence, full refresh. Triggers: incremental, replay, backfill, late-arriving data, the model duplicates rows, full-refresh."
---

# incremental-replay

An incremental model is defined by its replay: if you cannot say what happens when a period is reprocessed, the model is not ready.

## Steps
1. Establish the model's grain and the key that identifies it. Check the key's uniqueness on the source with an assertion query before anything else.
2. Choose the strategy and justify it: insert only, merge on key, delete then insert by partition. For BigQuery, say whether the table is partitioned and on which column; the partition strategy is the only one that makes replaying a period trivial.
3. Define the tolerated lateness window (late-arriving data) and the reprocessing window on each run; write them in the model's documentation, not only in the code.
4. Write the replay scenario: exact command to reprocess a period, effect on existing rows, estimated cost, duration. Test the scenario on the development target: run the same period twice and check that the result is identical (idempotence) with a comparison query.
5. Document when a `--full-refresh` is needed (change of logic, grain or key) and what it costs; never run it on production without an instruction and without an estimate.
6. Add the tests: key uniqueness, not-null, volume per partition compared to the source, freshness.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "The duplicates come from the source, not the model" | The model has a key; if it is not unique in the output, the model is wrong, whatever the source. |
| "We'll do a full refresh if it drifts" | A full refresh on a large table is costly and blocking; design per-period replay now. |
| "Late-arriving data is rare" | Rare is not zero; set the window and measure how much arrives beyond it. |
| "Two runs give the same result, obviously" | Prove idempotence with a before/after comparison on one period; do not assume it. |
| "dbt handles incremental on its own" | dbt applies the chosen strategy; the key, the window and the replay remain decisions to write down. |

## Forbidden
No incremental model without a key verified unique. No replay untested on the development target. No `--full-refresh` in production without a written instruction.
