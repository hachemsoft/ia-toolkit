# Workflow: six steps, one command per step

The kit follows the cycle from Anthropic's ["AI-native SDLC playbook"](https://claude.com/resources/articles/the-ai-native-sdlc-playbook): each step ends with an artifact that the next step reads (versioned in the repo, or a local working note for `intent.md` and `plan.md`). Commands are English verbs typed in the CLI; the skills that carry them out stay under the hood. `/guide` explains where to start.

## Ceremony matches the stakes

| Stakes | What to do | Commands |
| --- | --- | --- |
| Small fix (label, filter, colour) | do it, check it yourself | none; `/test` if the repo has tests |
| Visual or exploratory | iterate with the agent, look, start again | `/design` for a throwaway prototype |
| Small feature | short framing, then test-first | short `/intent`, `/build`, `/test`, `/ship` |
| Large or unclear | spec, phased plan, verification between phases | `/intent`, `/spec`, `/build` per ticket, `/review`, `/ship` |
| Production, irreversible, sensitive data | all of the above, full review | `/review full`, guardrails active |

Each command states in one line the level it chose. `/review` accepts `quick` or `full` as an argument.

## The steps

The installed commands depend on the profile: see the [profile table](getting-started.md#3-work-one-command-per-step). A missing command is added with one line, `extra_commands` in `~/.ai-kit/overrides.json`, then `update`.

| Step | Command | Artifact | What the command does |
| --- | --- | --- | --- |
| Plan | `/intent <idea, ticket, incident>` | `intent.md` | interview in rounds until shared understanding; problem, expected outcome, affected users and systems, constraints, open questions; glossary and ADRs updated |
| Plan | `/map <work item>` (developers) | decision tickets | map a piece of work too large for one session, decisions first, then `/spec` |
| Design | `/spec` | `spec.md` | from the accepted intent, without a new interview: goal, scope, requirements with acceptance criteria, data contracts (grain, keys, sources, freshness), rules applied while writing, points of attention; one file, never a ticket (splitting into tickets is `to-tickets`, on request) |
| Build | `/design <question>` (developers) | interface sketch or prototype | several shapes of a module compared, or a throwaway prototype to decide |
| Build | `/build <ticket or spec>` | `plan.md`, then diff and tests | plan in plan mode (files, order, risks, evidence), accepted before any code; implementation one slice at a time, failing test first; final check by the verifier agent when installed |
| Test | `/test [scope]` | real output of the checks | tests what changed and what depends on it, whatever the team: files changed against the base branch, the "Changed" command of each stack in the "Verifying your work" block of `AGENTS.md`, full suite if a shared file changed; same rule with the repo's tools if the block is missing, looked up in CI first; if no command can be inferred, it says so, asks for the commands and offers to write them into `AGENTS.md`; pastes the output; fixes the code, never the test |
| Deploy | `/review [base] [quick\|full]` | sorted findings | bug, security, data and compliance passes against `spec.md` (and `plan.md` when present locally), following the repo's `REVIEW.md` or the kit template; these passes replace the upstream skill's axes; in `full` mode, a doubt pass on each claim |
| Deploy | `/ship` | MR description | visual summary, before/after evidence, one-way or two-way door; pushes nothing |
| Maintain | `/diagnose <symptom>` | proven cause, regression test | red/green signal before any fix (a failing test; for data, an assertion query; for infrastructure, a plan or a dry run); the finding can become an `intent.md` again |
| Maintain | `/triage` (developers) | tickets ready for an agent | triage state machine for incoming tickets |

The templates for `intent.md`, `spec.md`, `plan.md`, `REVIEW.md` and `AGENTS.md` are installed with the `init-project-context` skill. Location convention: one folder per change, `docs/sdlc/<AAAA-MM-JJ>-<slug>/`, holding the three artifacts. `REVIEW.md` stays at the root. A repo can document another convention in `AGENTS.md`.

**What is versioned.** `spec.md` and `REVIEW.md` are committed: the spec is the contract the reviewer reads in the MR, and `REVIEW.md` holds its review axes. `intent.md` and `plan.md` are local working notes, ignored by git (`init-project-context` proposes the `.gitignore` lines): nobody wants to reread an interview or a work plan in the history, and they change at each iteration. A team that prefers to version everything says so in `AGENTS.md`, and `/review` then also compares against `plan.md`. In every case, the agent never commits without approval.

**Language.** Artifact section headings stay in English, as in the templates: they are stable and searchable. The content is in the team's language; the agent's answers are in the person's language. Command descriptions shown by `/help` are in English.

## Domain playbooks

Domain skills, activated by the model when the task calls for them and chained by the commands:

| Playbook | Chained by | Role |
| --- | --- | --- |
| `kpi-definition` | `/intent` | grain, population, period, exclusions, source of truth, owner, before any query |
| `sql-review` | `/diagnose` | grain, join cardinalities, NULL, dates, suspicious results |
| `dbt-model-change` | `/build` | test-first with `dbt test` on the development target |
| `incremental-replay` | `/build`, `/diagnose` | unique key, late data, reprocessing window, replay idempotence |
| `bigquery-query-review` | `/build`, `/diagnose` | preserved semantics, partitions, execution plan |
| `bigquery-cost-review` | `/build`, `/diagnose` | bytes, slots, frequency, monthly cost, budget before execution |
| `perimeter-brief` | `/learn` | HTML sheet for an area, quiz, candidate glossary terms |
| `python-js-change` | `/build` (Data Developer) | repo conventions, TDD, interface before implementation |
| `java-change` | `/build` (Java Developer) | repo and Maven or Gradle build conventions, JUnit, public contracts |
| `infra-change` | `/build`, `/diagnose` (DevOps) | blast radius, read-only evidence (plan, diff), never an apply or a deployment, rollback |
| `architecture-decision` | `/spec` (Architect) | compared options, criteria, consequences, reversibility, ADR |

The Data playbooks are in both Data profiles; `python-js-change`, `java-change`, `infra-change` and `architecture-decision` are each in the profile shown. A playbook from another profile is added with `extra_skills` in `overrides.json`. Rationalization tables, description triggers and "Forbidden" sections are what make a playbook activate at the right time.

Each playbook ends with a "Rationalizations and rebuttals" table: the reasons an agent gives to skip a step, and the reply it gets. When the agent finds a new rationalization, it goes into the table.

## Adversarial review

`/review full` adds a doubt pass: the `ai-kit-doubter` agent, in a fresh read-only context, extracts the claims the change depends on, looks for evidence or a counter-example for each, and classifies them as proven, refuted or unproven. A claim without readable evidence is reported as Important.

## Setting up a repo

1. "Initialize the project context": a one-page `AGENTS.md` (Commands, Verifying your work, Conventions, Architecture, Things the agent gets wrong), `GLOSSARY.md` pre-filled with the repo's vocabulary, `REVIEW.md`, and the `.gitignore` lines for local notes. No empty ADR, no copy of the templates.
2. Later, only if the team wants the agent to read and create tickets (`/map`, `/triage`, `to-tickets`): `setup-workflow`, which requires `glab` (GitLab) or `gh` (GitHub) installed and logged in, or chooses local markdown mode. It writes `docs/agents/issue-tracker.md` and a block in `AGENTS.md`.

A repo can replace a kit command only where the CLI supports it (row "Override a command in a repository" of the [CLI matrix](cli/matrice.md)); otherwise, a skill with a name of its own to the project, cited in `AGENTS.md` ([add or replace a skill](extending.md#for-a-repo)).

## Under the hood

Commands are written once in `commands/<name>.md` ([pivot format](format.md)); each adapter derives its CLI's form from it ([matrix](cli/matrice.md)). Their prompt activates one or more skills. Their behaviour is checked with the [evals](evals.md) suite. The list of skills, their category and origin are in [skills-reference.md](skills-reference.md); tools outside the flow are in [tools.md](tools.md).
