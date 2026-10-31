---
name: kpi-definition
description: "Define or redefine a KPI before computing it: grain, population, period, exclusions, source of truth, owner. Triggers: define an indicator, the KPI doesn't match, two different numbers for the same measure, new metric. Not for: debugging the SQL of a metric already defined."
---

# kpi-definition

A KPI without a written definition produces two different numbers as soon as a second person computes it. The definition comes before the query.

## Steps
1. Read `GLOSSARY.md` and the existing definitions (dbt docs, dashboards, tickets). If the term exists, start from it; do not create a synonym. If the repo has a `GLOSSARY-MAP.md` (several teams), say which glossary the definition comes from; an indicator shared by several teams has a single definition, in the common glossary, with a named owner, and the team glossaries refer to it instead of redefining it. If two definitions exist, flag it and ask who decides before writing.
2. Settle, in this order, asking one question at a time when it is ambiguous: the grain (one row per what), the population (who is in, who is out, and the rule that says so), the period (window, time zone, reference date: event, record or processing), the exclusions (tests, cancellations, duplicates, internal accounts), the formula (numerator, denominator, aggregation), the source of truth (table or model, and why that one), the expected freshness, the business owner.
3. Write the definition in the glossary format: one term, a two-sentence definition, the synonyms to avoid; the details (formula, exclusions, source) go in the documentation of the model that carries it.
4. Write the assertion query that validates the definition on a known case (a month, a scope whose number is accepted) before the production query. It becomes a test.
5. If the definition changes a published number, say so explicitly and propose an ADR.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "Everyone knows what an active customer is" | Two teams already have two definitions; write the activity rule and its window. |
| "We'll take the table's date, it's the same" | Event, record and processing dates diverge on late-arriving data; choose and name it. |
| "The denominator is obvious" | The ratio changes with the denominator's population; write it and test it on a known month. |
| "We'll exclude the odd cases later" | Exclusions are part of the definition; list them now, otherwise the number moves on every run. |
| "The dashboard is already the reference" | A dashboard is not a definition; find its query, read it, document it or fix it. |

## Forbidden
No production query before the written definition. No new term when the glossary already has one. No published number without an assertion on a known case.

## In the kit commands
- `/intent`: when the intent concerns a KPI or a metric, settle grain, population, period and exclusions before closing the interview.
- `/guide`: a KPI or metric definition starts with `/intent`, then `/build`.
