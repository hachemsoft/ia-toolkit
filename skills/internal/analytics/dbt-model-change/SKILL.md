---
name: dbt-model-change
description: "Create, modify, test or document a dbt model on BigQuery. Triggers: new model, modify this model, add a column or a dbt test, materialization, incremental, ref and source, dbt run or dbt test."
---

# dbt-model-change

Read dbt_project.yml, the versions and neighbouring models. Define the grain, sources and dependencies; use source() and ref() according to the repo's conventions. Choose the materialization from known needs and volumes. For an incremental model, check unique_key, late-arriving data and replay behaviour. Work test-first with the tdd skill: first write the dbt test (unique, not_null, accepted_values, singular test) that describes the expected behaviour, watch it fail on the development target, then modify the model. Keep tests compatible with the installed version; do not assume native unit tests are available. Compile, then run the validations on the explicitly identified development target. Do not run a full-refresh or a production build without a matching instruction. Compare volumes and expected results.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "dbt compile passes, the model is fine" | Compiling tests neither the grain nor the volumes; run the tests on the development target. |
| "I'll add the tests afterwards" | The test comes before the change; it is what tells you when you are done. |
| "A full refresh costs nothing here" | Estimate first; on production, never without an instruction. |
| "The dbt version surely supports unit tests" | Check the installed version; do not assume a feature. |

## Forbidden
No `dbt run`, `dbt build` or `--full-refresh` on a production target. No change to the model before the dbt test that describes it. No test deleted or weakened to make a run pass.

## In the kit commands
- `/build`: `dbt test` is the red-green loop, on the development target.
- `/test`: when AGENTS.md has no "Verifying your work" table, run `dbt build --select <changed models>+` on the development target; build everything when a shared file changed (macros, `dbt_project.yml`, packages, seeds).
- `/review` and `/test`: the cross-area impact is the descendants of the changed models; delegate the dbt review to the ai-kit-dbt-reviewer agent when it is available.
