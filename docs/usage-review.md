# Usage review

The usage review is the procedure a team uses to slim down the kit based on facts rather than opinions. The kit deliberately ships a broad core at first, because nobody knows yet what will be useful; the usage review is the mechanism that corrects this bet, regularly, based on what people actually type.

## Why it is needed

**Every installed skill has a permanent cost, even when nobody uses it.** Its description is injected into the context of every prompt so the model knows it exists (`doctor` shows this weight). The more skills, the more context is used before the question even starts, and the more likely the model is to activate a skill that misses the request. A core of twenty skills that are never activated charges this tax on every message from every person.

**Every component is a potential support ticket.** A skill that triggers when nobody wants it, a command nobody understands, an agent that is never called: all things to explain, document, test and maintain at each update of the upstream skills. The kit exists to reduce support, not to feed it.

**Ceremony matches the stakes.** The kit's rule is not to install everything. But deciding up front what an analyst or a developer will use is a guess. The usage report replaces the guess with a measurement.

**Commands nobody types are a signal, not a failure.** If `/retro` is never typed, the question is not "should we remove it" but "does `/guide` suggest it, and is its entry clear". The review also serves this purpose.

## What the review does and does not do

| The review can | The review never |
| --- | --- |
| move a skill from the core (`core`) to optional (`optional`): one `extra_skills` line re-enables it for anyone who wants it | deletes a skill from the repository or from a workstation without a team decision |
| replace an upstream skill the team departs from with a short in-house version, same name, same command | renames a command or changes an artifact (`intent.md`, `spec.md`, `plan.md`, `REVIEW.md`): that is the contract with the team |
| fix `/guide`, an entry or a prompt when a command is never typed | touches the guardrails: they do not depend on usage frequency |
| shorten `00_KIT.md` and the templates | acts automatically: the report proposes, people decide |

Data playbooks and vocabulary skills (`domain`, `reference`) are never proposed for removal: they activate based on the nature of the task, not on frequency. A BigQuery cost review playbook is used twice a year, and that is fine.

## The report

```sh
python3 -m installer usage                           # 42-day window
python3 -m installer usage --since 90 --json releve.json
python3 -m installer usage --min-sessions 5 --min-prompts 20
```

The report reads, locally and without sending anything, the session logs each CLI already writes on the workstation (locations in the [matrix](cli/matrice.md)). Over the window, it counts:

- kit commands typed, by name;
- skills activated by the model, when the CLI logs them (see its page);
- kit agents called;
- errors;
- frictions logged with `/friction` (`~/.ai-kit/frictions.jsonl`: date, category, command, one sentence), counted by category;
- then, by difference, the installed commands, skills and agents that were never used.

It contains neither prompt text, nor repo file names, nor the person's identity. The JSON can be shared as is.

**Data threshold.** Below ten sessions and fifty prompts over the window (change with `--min-sessions` and `--min-prompts`), the report shows the counts but recommends nothing: too little data to conclude. Above it, it lists the candidates to move to optional: core skills of category `workflow` or `tool` that were never activated, and that are required neither by a typed command nor by an activated skill (the catalog's `requires` dependencies are followed). A skill never activated but required by `/intent`, which itself was typed, is not a candidate.

**What the report does not measure.** Quality. A skill activated once may have saved a day of work; a skill activated twenty times may have got in the way twenty times. The report says "never", "rarely", "often"; the review says "useful" or "not useful". That is why the review stays human.

## What it looks like

On one workstation, after three weeks:

```
$ python3 -m installer usage
Window: 42 days | 14 sessions | 86 prompts | 2 errors
Commands typed: intent ×9, build ×7, test ×6, guide ×4, diagnose ×2, friction ×2
Skills activated: grill-with-docs ×9, implement ×7, tdd ×6, dbt-model-change ×5, sql-review ×2
Agents called: ai-kit-verifier ×5
Never used: 2 commands, 9 skills, 2 agents.
Frictions logged: 2 (docs ×1, command ×1); /friction to log one.
Candidates to remove from the core (never activated, not required by a used command): retro
Procedure: docs/usage-review.md. The logs read are local; nothing is sent.
```

Each person exports (`usage --json prenom.json`) and shares if they want to; the team aggregates:

```
$ python3 scripts/usage-aggregate.py releves/*.json
# Aggregated usage report

6 workstations | 71 sessions | 412 prompts | 9 errors

### Commands typed
| Name | Total |
| --- | --- |
| `intent` | 41 |
| `build` | 33 |
| `test` | 29 |
...
### Core candidates never activated on any workstation
`retro`

### Frictions (7)
| Category | Command | Friction |
| --- | --- | --- |
| command | /test | reruns the whole suite when I wanted a single model |
| command | /test | does not find the tests when AGENTS.md is missing |
| docs | /intent | the page says "spec" but the command writes intent.md |
...
By category: command ×4, docs ×2, guardrail ×1
```

Reading: two frictions on `/test` say the same thing, so that is a ticket; `retro`, never activated on six workstations, is a candidate to move to optional, unless someone explains in one line why it stays.

## When to hold it

The kit sets no date. A review makes sense when several workstations have passed the threshold, typically after a pilot phase or a few weeks of use, and then each time the team considers adding skills: adding a component is the right time to remove one.

## Steps

1. Each person runs `usage --json <file>` and shares the file; reports are per workstation. The team aggregates with `python3 scripts/usage-aggregate.py <files>`: totals, commands, skills, agents, candidates never activated on any workstation, and the list of frictions by category, in Markdown ready to paste.
2. The report already lists the groups of two or more frictions (same category, same command) and the measured signals (unknown commands, repeated requests). For each group: one ticket, handled by the support rule (a `doctor` check, a Troubleshooting line, an eval case, or a prompt fix). An isolated friction stays in the report until the next review.
3. For each core candidate: set it to `optional` in `skills/catalog.json`, or write in one line why it stays. Both are valid decisions; no decision is not.
4. For each command never typed: check that `/guide` suggests it in the right cases and that its entry is clear without the docs. If not, fix the router or the entry, not the command.
5. Review the accumulated `/retro` proposals and the playbooks' rationalization tables: each repeated mistake becomes an `AGENTS.md` line, an eval case, or a table row. Never one more prompt to retype.
6. An upstream skill the team departs from is rewritten as a short in-house version, same name, same command; the old one stays available through `extra_skills`. A widely used contributed skill (`skills/contrib/`) moves to `skills/internal/`; a contributed skill without a reachable owner is removed.
7. Rerun the tests and `evals/run.py`, publish the version, and record in the `CHANGELOG` what changed and why.
8. When a fix answers frictions, say so in one line in the `CHANGELOG` ("`/test` no longer reruns the whole suite, reported three times"): people log more when they see it helps.

## Data and privacy

The logs read are the ones the CLIs already write on the workstation. The report does not copy them, does not send them anywhere, and extracts only counts by command, skill and agent name. Sharing the JSON is the person's choice; aggregation runs on the shared files, not on the workstations.
