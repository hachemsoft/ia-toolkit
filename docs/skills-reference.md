# Skills reference

Full list of the catalog (`skills/catalog.json`). Users do not need to know these names: they go through the commands. This page is for people who want to see what is underneath or extend the kit.

Categories: `workflow` (an SDLC step), `tool` (utility outside the flow), `domain` (domain playbook: Java, infrastructure, architecture, Data…), `reference` (vocabulary consulted by other skills), `setup` (repository setup). Tiers: `core` installed in all profiles (checked by a test), `profile` depending on the profile, `optional` through `extra_skills` or `extra_commands`.

| Skill | Category | Tier | Commands | Description |
| --- | --- | --- | --- | --- |
| `grilling` | workflow | core | — | Challenge a plan, decision or idea through rounds of questions before implementing it. |
| `codebase-design` | reference | optional | `/design` | Vocabulary of deep modules: interface, seam, depth; interface design in several variants. |
| `prototype` | workflow | optional | `/design` | Throwaway prototype to settle a design, logic or interface question. |
| `domain-modeling` | reference | core | `/spec` | Project glossary (GLOSSARY.md) and architecture decisions (ADR). |
| `tdd` | workflow | core | `/test` | Test-first development: red, green, refactor; integration tests preferred. |
| `diagnosing-bugs` | workflow | core | `/diagnose` | Diagnosis loop for hard bugs and performance regressions: reproduce, minimize, hypothesize, instrument, fix. |
| `writing-for-agents` | reference | core | — | Write documents meant for agents: skills, AGENTS.md, repository docs. |
| `research` | tool | optional | `/research` | Research on primary sources, recorded in a Markdown file in the repository, delegated to a background agent. |
| `mr` | workflow | core | `/ship` | Write a merge request (MR) description: visual summary, evidence, merge risk. |
| `guide` | tool | core | `/guide` | Which command, which tool and which level of ceremony for the situation: the kit router. |
| `grill-me` | workflow | optional | — | Tight interview to sharpen a plan, with no repository or written record. |
| `grill-with-docs` | workflow | core | `/intent` | Tight interview that feeds GLOSSARY.md and the ADRs as answers come in; entry point of the main flow. |
| `to-questionnaire` | tool | optional | `/ask` | Turn a decision you cannot make alone into a questionnaire for someone else. |
| `to-spec` | workflow | profile | `/spec` | Turn the conversation into a specification published on the ticket tracker. |
| `to-tickets` | workflow | profile | — | Split a plan or spec into tracer tickets with their blocking dependencies. |
| `wayfinder` | workflow | optional | `/map` | Map a body of work too large for one session into decision tickets, resolved one by one. |
| `implement` | workflow | core | `/build` | Implement a ticket or a spec, with TDD, then review. |
| `implement-spec` | workflow | optional | — | Implement a whole spec: tickets read as a graph, subagents in parallel, integration branch. |
| `code-review` | workflow | core | `/review` | Review a diff from a fixed point on two axes: repository standards and compliance with the spec. |
| `triage` | workflow | optional | `/triage` | Move incoming tickets through a triage state machine until they are ready for an agent. |
| `retro` | tool | profile | `/retro` | Retrospective of a work session: improve the agent's environment, not the code. |
| `handoff` | tool | optional | `/handoff` | Compact the conversation into a handoff document for another agent or session. |
| `wait-what` | tool | profile | `/explain` | Rephrase the last message that was not understood, using the glossary vocabulary. |
| `zoom-out` | tool | profile | `/explain` | Step back: wider context and overview. |
| `teach` | tool | core | `/learn` | Learn a scope or concept over several sessions: lessons, quizzes and cards; shared material in the repository's `docs/learn/<topic>/`, personal progress in `~/.ai-kit/learning/`. |
| `improve-codebase-architecture` | tool | optional | `/audit` | Spot modules to deepen, HTML report, then an interview on the selected ones. |
| `wizard` | tool | optional | `/wizard` | Generate an interactive bash wizard for steps only a human can perform. |
| `write-a-skill` | tool | optional | — | Create a skill: structure, progressive disclosure, resources. |
| `writing-great-skills` | reference | optional | — | Reference for writing and reviewing predictable skills. |
| `setup-workflow` | setup | core | — | Configure a repository for the flow: ticket tracker (GitHub, GitLab, local), triage labels, location of the glossary and ADRs. Run once per repository. |
| `workflow-guide` | tool | optional | — | Which skill or flow for the current situation: router across all skills. |
| `init-project-context` | setup | core | — | Set up a repository's agent context, with confirmation for each file: short AGENTS.md, prefilled GLOSSARY.md, REVIEW.md, git rule for artifacts; does not copy the templates, does not create an empty ADR. |
| `python-js-change` | domain | profile | — | Develop or review a Python or JavaScript feature in an existing repository. |
| `java-change` | domain | profile | — | Develop or review a Java feature in an existing repository (Maven or Gradle, Spring or other). |
| `infra-change` | domain | profile | — | Prepare or review an infrastructure or delivery change: Terraform, Kubernetes, Helm, CI/CD pipeline, Dockerfile, cloud configuration. |
| `architecture-decision` | domain | profile | — | Investigate and document an architecture decision (ADR): options, criteria, consequences, reversibility. |
| `sql-review` | domain | profile | — | Review BigQuery or dbt SQL and investigate suspicious aggregations, duplicates or business results. |
| `dbt-model-change` | domain | profile | — | Create, change, test or document a dbt model on BigQuery. |
| `bigquery-query-review` | domain | profile | — | Optimize a slow or costly BigQuery query and check scans, partitions, joins and plan. |
| `kpi-definition` | domain | profile | — | Define or redefine a KPI before computing it: grain, population, period, exclusions, source of truth, owner. |
| `incremental-replay` | domain | profile | — | Replay or fix an incremental model: unique key, late data, reprocessing window, idempotence. |
| `bigquery-cost-review` | domain | profile | — | Measure and reduce the cost of a BigQuery query or model: bytes, slots, frequency, budget before running. |
| `perimeter-brief` | domain | profile | — | HTML brief of a Data scope, quiz and candidate glossary terms, first lesson of `/learn`. |
| `clarify-request` | replaced | | | → `grilling` |
| `debug-systematically` | replaced | | | → `diagnosing-bugs` |
| `verify-change` | replaced | | | → `tdd`, `mr` |

## Origin

Skills with `origin: upstream` come from [mattpocock/skills](https://github.com/mattpocock/skills) (Matt Pocock, MIT licence) (`skills/LICENSE-UPSTREAM-MIT`), in English. Three adaptations: `pr` becomes `mr`, and the two upstream skills whose name carried their author's name become `setup-workflow` and `workflow-guide`. Skills with `origin: contrib` (under `skills/contrib/`) are proposed by people in the organization who remain their owners; they are always optional. Skills with `origin: internal` are written for the kit, in French. See [workflow](workflow.md) and [tools](tools.md) for usage.
