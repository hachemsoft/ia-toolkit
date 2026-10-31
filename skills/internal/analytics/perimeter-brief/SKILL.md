---
name: perimeter-brief
description: "Produce the brief of a Data perimeter from a dbt repo and its documentation: sources, layers, key models and their grain, KPIs, rules, owners, open questions; plus a quiz and candidate glossary terms. Triggers: perimeter brief, onboarding on a domain, walk me through this perimeter, first lesson."
---

# perimeter-brief

The document you give to someone joining a perimeter, and the first lesson of `/learn` when the subject is a Data domain. Everything comes from the repo and its documentation: nothing invented.

## Steps
1. Inventory: `dbt_project.yml`, declared sources, models by layer (source, staging, intermediate, mart), exposures, tests, descriptions; `GLOSSARY.md`, ADRs, README, referenced dashboards. Note what is missing.
2. For each key model (the marts and what they depend on directly): grain as documented or inferred from the key, sources, freshness, existing tests. Flag any undocumented grain as an open question, not as a certainty.
3. List the exposed KPIs with their definition when it exists; otherwise mark it "undefined" and refer to `kpi-definition`.
4. Record cross-cutting rules: reference dates, time zones, exclusions, access scopes, dbt targets and environments.
5. Produce the brief as standalone HTML, readable and printable, with no required external dependency: title, five-line summary, layer diagram (text or simple SVG), table of key models, table of KPIs, rules, owners, open questions, sources consulted with paths. Save it as `docs/learn/<perimeter>/reference/perimeter-brief.html` with the person's agreement.
6. Produce a ten-question multiple-choice quiz based on the brief; answers of equal length, varied position of the correct answer, a one-line explanation per question. Same folder, `quiz-01.html`.
7. List the candidate terms for `GLOSSARY.md` in the `domain-modeling` format; propose them, do not write without agreement.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "The grain is obvious from the model name" | A name is not a contract; read the key and the tests, otherwise mark it "to confirm". |
| "The KPI is defined in the dashboard" | Find the query; if it is not in the repo, the KPI is undefined here. |
| "I'll fill in with what I know about the domain" | General knowledge is not this team's perimeter; cite a file or ask the question. |
| "A short brief is enough, we'll see the details later" | Short yes, but the open questions go in it: they are what costs later. |

## Forbidden
No statement without a supporting file path. No writing to the repo without agreement. No quiz on anything that is not in the brief.

## In the kit commands
- `/learn`: when the topic is a data perimeter (sources, models, KPIs, rules, owners), start with a one-page perimeter brief and a ten-question quiz grounded in the repo's models and docs.
