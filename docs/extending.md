# Add or replace a skill

Three scopes, three places. The choice depends on who must see the skill, not on what it does.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

| For | Where to put it | Seen by | Kit update |
| --- | --- | --- | --- |
| you only | your CLI's skills folder, `<name>/SKILL.md` (matrix row "Your own skills": [matrix](cli/matrice.md)) | your CLI | untouched: the kit only touches folders it installed itself |
| a repo and its whole team | `<repo>/.agents/skills/<name>/SKILL.md`, versioned | CLIs that read `.agents/skills/` ([matrix](cli/matrice.md)) | no effect |
| the whole organization | `skills/internal/<category>/<name>/` in the kit, plus the catalog | every workstation at the next distribution | it is the kit |

A skill is a folder with a `SKILL.md` that starts with a `name` and `description` header, then short instructions. Supporting files (templates, references) go in the same folder. The `write-a-skill` skill and the `writing-great-skills` reference, both optional (`extra_skills`), help you write it. The rule that matters: the description says when to use it, the body says what to do, nothing else.

```markdown
---
name: revue-dashboard
description: "Review a dashboard before publishing: filters, periods, totals, labels. Triggers: review this dashboard, before publishing, the total does not match."
---

# revue-dashboard
1. List the active filters and the period; compare with the title.
2. Recompute a total on a known period; tolerated gap: none.
3. ...
```

## For you only

Create `<name>/SKILL.md` in your CLI's skills folder ([matrix](cli/matrice.md)), with a **name that does not exist in the kit**. The CLI reads it at the next start; `update` leaves it as is. To check, list the skills in the CLI (the command is on its page, see the [matrix](cli/matrice.md)).

Two traps. A folder in that location with the same name as a kit skill blocks `update` ("existing file not managed by the kit"): the kit refuses to overwrite what it did not install. And some CLIs read a second skills folder that wins on equal names and hides the kit skill (see your CLI's page); `doctor` lists skills hidden this way. To replace a kit skill without these effects, go through a repo or the kit, below.

## For a repo

Create `<repo>/.agents/skills/<name>/SKILL.md` and version it. In a monorepo, prefix the name with the zone (`finance-cloture-mensuelle`): repo skills apply to all teams. CLIs that read `.agents/skills/` find it in that repo. **Give it a name of its own**: a repo skill named like a kit skill replaces it in one CLI, is ignored in another, and is listed next to it in a third, verified ([matrix](cli/matrice.md)). To adapt a shipped playbook for one project (for example the repo's SQL conventions), write `<repo>-sql-review` and say in `AGENTS.md`: "for SQL reviews in this repo, use the `<repo>-sql-review` skill". `doctor`, run from the repo, lists clashing names.

A kit command can be overridden in a repo only where the CLI supports it ([matrix](cli/matrice.md)); elsewhere, write the project rule in `AGENTS.md`.

## For the organization: in the kit

Two folders, two levels of commitment. `skills/internal/`: shipped and maintained by the kit maintainers, in the profiles. `skills/contrib/`: proposed by a person or a team who stays its owner, never installed by default (`tier: optional`, `origin: contrib`, `owner` in the catalog), enabled with one line by anyone who wants it. A contributed skill that is widely used moves to `internal` at a usage review; a skill without a reachable owner is removed. The rules are in `skills/contrib/README.md` and checked by the tests. The steps below apply to both; only the folder and the `origin`, `owner`, `tier` fields change.


1. **The folder**: `skills/internal/<category>/<name>/SKILL.md` (existing categories: `common` for workflow and tools, then one per domain: `development`, `operations`, `architecture`, `analytics`), or `skills/contrib/<name>/SKILL.md` for a contribution. The folder name and the header `name` are identical.
2. **The catalog** `skills/catalog.json`, one entry per skill:
   ```json
   "revue-dashboard": {
     "path": "skills/internal/analytics/revue-dashboard",
     "origin": "internal",
     "description": "Review a dashboard before publishing: filters, periods, totals, labels.",
     "category": "domain",
     "tier": "profile",
     "requires": []
   }
   ```
   `category`: `workflow` (a step, behind a command), `tool` (utility, behind a command), `domain` (domain playbook, activated by the task), `reference` (vocabulary read by other skills), `setup`. `tier`: `core` (in all profiles, a test checks it), `profile` (depends on the profile), `optional` (through `extra_skills` or `extra_commands`). `requires` installs the skills it cannot work without, with it; `optional` maps a skill it cites but can do without to what to do instead (`{"codebase-design": "keep interfaces small…"}`): when that skill is not installed, the installed `SKILL.md` ends with a "Not installed here" section giving the alternative. A test checks that every skill a `SKILL.md` cites is in one of the two. `needs_agents: true` signals that it delegates to subagents.
3. **The profiles** `profiles/*.json`: add it to the profiles that need it, or leave it `optional`. A domain playbook is never in the `general` profile. It ends with a `## In the kit commands` section (what it changes in `/build`, `/diagnose`, `/review`…): the commands stay neutral and send to the matching playbook.
4. **A command, if it is a step or a tool**: a `commands/<name>.md` file, with a header (`name`, `description` in English, `category`, `stage` for a workflow, `skills`, `order`) and a prompt with `{{args}}`; see [the pivot format](format.md). Each adapter turns it into its CLI's command. Add an entry in `docs/tools.md` for a tool.
5. **An eval case** `evals/cases/NN-<name>.json` with the prompt that must trigger the skill and an observable criterion, then `python3 scripts/offline_tests.py` and `python3 evals/run.py --dry-run` (a real run, `--confirm-paid-run`, is billed).
6. **Distribute**: commit, merge request (MR), tag; workstations get it with the next version of the kit (a new ZIP, or `update` in a git clone, which pulls first).

## Full example: a `/dashboard-check` tool in twenty minutes

The need: review a dashboard before publishing. One skill, one command, one eval case, and it exists in every supported CLI.

1. The skill, `skills/contrib/dashboard-check/SKILL.md` (contributed by an analyst who stays its owner):

   ```markdown
   ---
   name: dashboard-check
   description: "Review a dashboard before publishing: filters, period, totals, labels. Triggers: review this dashboard, before publishing, the total does not match."
   ---

   # dashboard-check
   1. List the active filters and the period; check that they match the title.
   2. Recompute a total on a period whose figure is known; tolerated gap: none.
   3. Check each label against the repo's GLOSSARY.md; propose the missing terms.
   4. Report: what is verified, what is not, what must be fixed before publishing.

   ## Forbidden
   No validation on a sample; no "roughly right" total.
   ```

2. The catalog entry, in `skills/catalog.json`:

   ```json
   "dashboard-check": {
     "path": "skills/contrib/dashboard-check",
     "origin": "contrib",
     "owner": "equipe-reporting",
     "description": "Review a dashboard before publishing: filters, period, totals, labels.",
     "category": "tool",
     "tier": "optional"
   }
   ```

3. The command, `commands/dashboard-check.md`:

   ```markdown
   ---
   name: dashboard-check
   description: "Review a dashboard before publishing: filters, period, totals, labels"
   category: tool
   skills: [dashboard-check]
   order: 140
   ---

   Activate the dashboard-check skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

   Input: {{args}} (the dashboard, its SQL or a screenshot description).

   Answer in the user's language. State in one line whether this is a quick check or a full review. Follow the skill's four steps and end with what blocks publication.
   ```

4. The eval case, `evals/cases/05-dashboard-check-totals.json`:

   ```json
   {
     "name": "dashboard-check-totals",
     "prompt": "/dashboard-check the monthly sales dashboard, October total 1,240 orders",
     "cwd": "dbt-mini",
     "expect": { "regex": ["(total|1,240)", "(filter|period)"] }
   }
   ```

5. Check and distribute: `python3 -m unittest discover -s tests`, `python3 evals/run.py --dry-run --only dashboard-check-totals` (then, if the maintainer decides it, `--confirm-paid-run`: billed), then commit, merge request (MR) and tag; workstations get it with the next version of the kit (a new ZIP, or `update` in a git clone, which pulls first). Anyone who wants the tool enables it with one line: `{"extra_commands": ["dashboard-check"]}` in `~/.ai-kit/overrides.json`, then `update`; `/dashboard-check` appears in every supported CLI.

## Replace a kit skill for the organization

Keep the name and, if there is one, the command: other skills and the docs refer to them. Two cases.

- **Internal skill** (`origin: internal`): edit the `SKILL.md` in place, rerun tests and evals.
- **Base skill** (`origin: upstream`, taken as is under the MIT license): do not edit it; the next upstream copy will overwrite it. Write a short in-house version in `skills/internal/<category>/<name>/`, same name, and change `path` and `origin` in the catalog. The old version stays available if you keep it under another name as `optional`. This is what the [usage review](usage-review.md) calls an "in-house version".

## Remove a skill

For yourself: `"disabled_skills": ["<name>"]` in `~/.ai-kit/overrides.json`, then `update`. A skill required by another one cannot be disabled on its own; `update` says so. For the organization: set it to `optional` in the catalog rather than deleting it, so it stays available with one line.

## What a skill does not customize

Form and language preferences: `30_USER.md` in the CLI folder. A repo's rules: its `AGENTS.md`. Deterministic guardrails: `overrides.json` under `hooks` and the repo's `.ai-kit/protected-paths` file. Agents: `extra_agents` and `disabled_agents`, or a file in the kit's `agents/internal/`. See [customization](customization.md).
