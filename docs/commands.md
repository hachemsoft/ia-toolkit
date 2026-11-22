# Commands, workflows, skills and agents

Plain sentences work; commands are shortcuts to a step or a tool. Each command is written once in `commands/<name>.md` and
activates one or more skills; agents take bounded missions in a separate context. Skills and agents describe themselves in
their own front matter ([extending](extending.md)). `/guide <question>` says which command fits.
New to the workflow? Start with [the SDLC workflow, explained](sdlc-workflow.md), with diagrams.

## Ceremony matches the stakes

Defined once, in the kit context (`templates/kit-context.md`, installed as `00_KIT.md`), and used by every command. A reply
to a change opens with `Level: quick|standard|full` and why, even when the agent then asks or is blocked. The level
follows what the change can break and whether that can be undone, not its size.

| Level | When | What happens |
| --- | --- | --- |
| quick | local, obvious behaviour, no contract changed | no artifact; do it, run the check that covers it |
| standard | small feature, a few files | short alignment, then a failing acceptance test approved before code |
| full | large or fuzzy; production, a shared contract, irreversible or personal data | useful artifacts; risks first: how a failure shows and how to undo it (for an irreversible operation, the backup or way back); acceptance before code, then as standard |

A request that changes a business rule or a KPI, or says people disagree on one, is full: the deciding question comes
before code or a query. Tests are never weakened, skipped or deleted to hide a regression.

The acceptance tests at standard and full levels, and why they come before the code: [the SDLC workflow](sdlc-workflow.md#inside-build-the-one-stop-that-matters).

## Steps

The SDLC commands. `workflows/sdlc.md` is the same table, generated from `commands/` by `scripts/workflows.py`.

| Step | Command | Installed | Artifact | What it does |
| --- | --- | --- | --- | --- |
| Plan | `/intent` | default | `intent.md` | interview in rounds (grilling), glossary terms and decisions (domain-modeling) |
| Plan | `/map` | optional | decision tickets | work too large for one session, decisions first (wayfinder) |
| Design | `/spec` | default | `spec.md` | from the accepted intent, no new interview; one file, never a ticket (to-spec) |
| Build | `/build` | default | diff and tests; `plan.md` for a full change | quick: the existing checks; standard and full: a failing acceptance test you approve before any code, then free slices (tdd's loop optional), then a review of the whole change (code-review) |
| Build | `/design` | optional | interface sketch or prototype | module shapes compared (codebase-design), or a throwaway prototype |
| Test | `/test` | default | real output of the checks | what changed and what depends on it; pastes the output (tdd) |
| Deploy | `/review` | default | ranked findings | committed and uncommitted changes, six passes, one severity scale; a change at risk gets independent reviewers; `quick` or `full` ([review](review.md)) (code-review) |
| Deploy | `/ship` | default | merge request description | visual summary, evidence, merge danger; pushes nothing (mr) |
| Maintain | `/diagnose` | default | root cause and regression test | red/green signal before any fix (diagnosing-bugs) |
| Maintain | `/triage` | optional | agent-ready issues | triage state machine for incoming tickets (ticket-sorting) |

Artifacts: one folder per change, `docs/sdlc/<YYYY-MM-DD>-<slug>/`, unless the repo's `AGENTS.md` says otherwise.
`spec.md` and `REVIEW.md` are committed; `intent.md`, `plan.md` and `review-guide.md` are local notes, ignored by git. Section headings stay in
English; the content is in the team's language. The agent never commits or pushes without the person's agreement.

## Tools

| Command | Installed | What it does | Skills |
| --- | --- | --- | --- |
| `/guide` | default | which command, tool and level fit the situation | routing |
| `/me` | default | fills or refreshes `USER.md` through a short interview, written only after a yes | none |
| `/friction` | default | logs one line about what got in the way, locally ([frictions](frictions.md)) | none |
| `/learn` | default | a perimeter or concept over several sessions; shared material in `docs/learn/<topic>/`, personal progress in `~/.ai-kit/learning/<topic>/` | teach |
| `/explain` | default | a map of a code area one level up, an analysis of a question with evidence, or the last answer re-pitched | zoom-out, analysis, wait-what |
| `/retro` | default | improves the agent's environment (AGENTS.md, checks, REVIEW.md), one proposal at a time | retrospective |
| `/research` | default | a question against primary sources, recorded in `docs/research/<slug>.md` | investigation |
| `/ask` | optional | a questionnaire for whoever holds a missing decision | to-questionnaire |
| `/handoff` | optional | a handover note for another session or person | handover |
| `/wizard` | optional | an interactive bash wizard for steps only a human can do | manual-steps |
| `/audit` | optional | HTML report of modules to deepen, then an interview | improve-codebase-architecture |
| `/news` | optional | writes an announcement in the `NEWS.md` of the Core repository open in the session, shown once at session start after the Core's next tag ([guardrails](hooks.md#whats-new)) | none |

An optional command is turned on by a Team (`extra_commands` in its `[defaults]`) or by the person (`extra_commands` in
`~/.ai-kit/aikit.toml` `[user]`, then `ai-kit sync --offline`). A command is installed only when all its skills are.

## Workflows

`workflows/` holds three indexes, never prompts: `sdlc.md` (generated, above), `analysis.md` (entry `/explain` with a
question, skill analysis, agents repo-investigator and verifier when installed) and `research.md` (entry `/research`, skill
investigation, agent doubter for the challenge step). `python3 scripts/workflows.py` says whether they are current;
`--write` rewrites them; a test checks them ([ADR 0026](adr/0026-analysis-and-research-entry-points.md)).

## Skills

Users go through commands; skill names are for people who extend the kit. Categories: `workflow` (a step), `tool` (a
utility behind a command), `domain` (a playbook activated by the task), `reference` (vocabulary other skills read),
`setup` (repo setup). `default` means `aikit-default: "true"`, installed for everyone; the rest is optional.

| Category | Core default | Optional |
| --- | --- | --- |
| workflow | analysis, code-review, diagnosing-bugs, grilling, grill-with-docs\*, implement\*, mr, review-guide, tdd, to-spec | grill-me\*, implement-spec\*, prototype, ticket-sorting, to-tickets\*, wayfinder |
| tool | investigation, retrospective, routing, teach, wait-what, zoom-out | handover, improve-codebase-architecture, manual-steps, to-questionnaire, workflow-guide\*, write-a-skill |
| reference | domain-modeling, writing-for-agents | codebase-design, writing-great-skills\* |
| setup | init-project-context, setup-workflow\* | |
| domain | | the playbooks below |

\* user-only (`disable-model-invocation: true`): the person calls it directly; no command chains it
([ADR 0020](adr/0020-commands-chain-only-model-invocable-skills.md)). Skills with `aikit-origin: upstream` are adapted from
the licensed upstream source listed in [sources](sources.md) (`skills/LICENSE-UPSTREAM-MIT`, `skills/upstream.lock.json`);
`internal` ones are written for the kit; `contrib` ones live in `skills/contrib/` with a named owner and are always optional.
No skill shares a command's name, because some CLIs make a command of every skill.

## Domain playbooks

All optional, turned on by a Team or a person. Each, except architecture-decision, ends with a `## In the kit commands` section saying what it changes in
the steps below, and a rationalizations table. The commands name no domain: `/build`, `/test`, `/diagnose`, `/intent`, `/review` and
`/learn` tell the agent to follow the installed playbook matching the files or the task
([ADR 0021](adr/0021-workflow-extensions-reuse-the-playbook-section.md)).

| Playbook | Extends | Role |
| --- | --- | --- |
| kpi-definition | `/intent`, `/build` | grain, population, period, exclusions, source of truth, owner, before any query |
| sql-review | `/diagnose`, `/review` | grain, join cardinalities, NULL, dates, suspicious results |
| dbt-model-change | `/build`, `/test`, `/review` | test-first on the development target; downstream models as cross-area impact |
| incremental-replay | `/build`, `/diagnose` | unique key, late data, reprocessing window, idempotence |
| bigquery-query-review | `/build`, `/diagnose` | preserved semantics, partitions, execution plan |
| bigquery-cost-review | `/build`, `/diagnose` | bytes, slots, frequency, budget before running |
| perimeter-brief | `/learn` | HTML brief of a data perimeter, quiz, candidate glossary terms |
| code-change | `/build` | a change to application code in any language: the repo's conventions, public contracts, no new library or implicit framework migration, the approved acceptance test first; per language, the community standard, the repo's own tools and classic traps in `references/<language>.md` (Python, JavaScript and TypeScript, Java, PHP, Go, Scala), read only for that language |
| infra-change | `/build`, `/diagnose` | blast radius, read-only evidence (plan, diff), never an apply, rollback |
| architecture-decision | none (activated by the task) | options, criteria, consequences, reversibility, ADR |

## Agents

Each CLI's native sub-agents, installed as `ai-kit-<name>`. They inherit the session's model; the kit names none. The reviewers work as a [cold review](review.md): the raw diff and references, never the author's narrative.

| Agent | Installed | Mission |
| --- | --- | --- |
| repo-investigator | default | understand the repo's flows and dependencies, without modifying files |
| verifier | default | run the checks the repo declares and report what was run and observed, without fixing; proves that the approved acceptance tests fail without the code, tells new failures from old ones ([ADR 0033](adr/0033-verifier-swaps-files-to-prove-a-test.md)) |
| doubter | default | adversarial review in a fresh context: doubt each claim, find proof or a counterexample, then a position (no objection, concerns, oppose) with the strongest objection (`/review full`, and a change at risk) |
| code-reviewer | default | concrete regressions in a code change |
| blast-radius | default | what a change can reach (callers, public contracts, downstream dbt models, configuration, other areas), with a Mermaid map and what to test (`/spec` and `/review` at the full level) |
| contribution-auditor | default | a change to agent configuration (`AGENTS.md`, skills, agents, hooks, MCP): hidden instructions, invisible characters, widened tools, data sent out; such a change is at risk |
| security-reviewer | default | secrets, injections, permissions, exposure, dependencies; checks the spec's Threats (a change at risk) |
| infra-reviewer | optional (called by infra-change) | blast radius, destructions, permissions, rollback of an infrastructure change |
| architecture-reviewer | optional (called by architecture-decision) | options, criteria and consequences of a proposal or an ADR |
| silent-failure-hunter | optional | errors a change swallows, fallbacks that hide an outage, return codes ignored, rows that vanish in SQL (`/review` when not quick, merged into Bugs) |
| pattern-scout | optional | before code: two or three places that already do the same thing and their convention (`/build`, through code-change) |
| rule-miner | optional | before a business rule or a KPI changes: the rules already in the code, as Given / When / Then (`/spec`, kpi-definition) |
| fresh-eyes | optional | reads a spec or an MR description as a newcomer and lists what it cannot understand (`/spec`, `/ship`) |
| sql-reviewer, dbt-reviewer | optional | grain, joins, aggregations; dbt models, incremental logic, tests |

How the review agents are briefed and when they run: [review](review.md). Where a CLI states an agent's tools
instead of enforcing them, the reviewers keep to reading by instruction only ([CLI matrix](cli/matrice.md)).

Reviewers get read and search tools only; the verifier can also list folders and run commands. Defaults (tools, 12 turns,
5 minutes) are in `agents/defaults.json`; the verifier has 15 turns and 10 minutes. Whether a CLI enforces the tool list or
only states it, and where it reads the limits, is in the [CLI matrix](cli/matrice.md). The Core and Team practices are
included in each agent's prompt; `USER.md` is not.

## Project context

What the agent reads in a repository, what wins on a conflict, and the files a repository keeps (`AGENTS.md`, `REVIEW.md`,
`GLOSSARY.md`, ADRs, the change folders), set up by init-project-context: [project context](project-context.md).
