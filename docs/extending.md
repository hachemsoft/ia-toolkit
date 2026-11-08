# Add or replace a skill

Three scopes, three places. The choice depends on who must see the skill, not on what it does.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

| For | Where to put it | Seen by | Kit update |
| --- | --- | --- | --- |
| you only | your CLI's skills folder, `<name>/SKILL.md` (matrix row "Your own skills": [matrix](cli/matrice.md)) | your CLI | untouched: the kit only touches folders it installed itself |
| a repo and its whole team | `<repo>/.agents/skills/<name>/SKILL.md`, versioned | CLIs that read `.agents/skills/` ([matrix](cli/matrice.md)) | no effect |
| the whole organization | `skills/internal/<category>/<name>/` in the kit, plus the catalog | every workstation at the next distribution | it is the kit |

A skill is a folder with a `SKILL.md` that starts with a `name` and `description` header, then short instructions. Supporting files (templates, references) go in the same folder. The `write-a-skill` skill and the `writing-great-skills` reference, both optional (`extra_skills`), help you write it. The rule that matters: the description says when to use it, the body says what to do, nothing else (full example [below](#full-example-a-dashboard-check-tool-in-twenty-minutes)).

## For you only

Create `<name>/SKILL.md` in your CLI's skills folder ([matrix](cli/matrice.md)), with a **name that does not exist in the kit**. The CLI reads it at the next start; `update` leaves it as is. To check, list the skills in the CLI (the command is on its page, see the [matrix](cli/matrice.md)).

Two things to know. If a folder in that location has the name of a kit skill, the kit never overwrites it: it keeps yours and installs its own as `ai-kit-<name>` (`skill_prefix`), and `update` says so. And some CLIs read a second skills folder that wins on equal names and hides the kit skill (see your CLI's page); `doctor` lists skills hidden this way. To replace a kit skill without these effects, go through a repo or the kit, below.

## For a repo

Create `<repo>/.agents/skills/<name>/SKILL.md` and version it. In a monorepo, prefix the name with the zone (`finance-cloture-mensuelle`): repo skills apply to all teams. CLIs that read `.agents/skills/` find it in that repo. **Give it a name of its own**: a repo skill named like a kit skill replaces it in one CLI, is ignored in another, and is listed next to it in a third, verified ([matrix](cli/matrice.md)). To adapt a shipped playbook for one project (for example the repo's SQL conventions), write `<repo>-sql-review` and say in `AGENTS.md`: "for SQL reviews in this repo, use the `<repo>-sql-review` skill". `doctor`, run from the repo, lists clashing names.

Repo skills escape the kit's own review: protect `.agents/` with a `CODEOWNERS` line, and run the kit's skills check in the repo's CI, from a checkout of the kit at a tag (the URL of your organization's copy, or the public one):

```yaml
# GitHub Actions, in .github/workflows/skills-check.yml
on: { pull_request: { paths: ['.agents/**'] } }
jobs:
  skills-check:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: |
          git clone --depth 1 --branch v0.49.0 <kit repository URL> "$RUNNER_TEMP/ai-kit"
          python3 "$RUNNER_TEMP/ai-kit/runtime/check_skills.py" .agents/skills
```

```yaml
# GitLab CI, in .gitlab-ci.yml
skills-check:
  image: python:3.12
  rules:
    - changes: [".agents/**/*"]
  script:
    - git clone --depth 1 --branch v0.49.0 <kit repository URL> /tmp/ai-kit
    - python3 /tmp/ai-kit/runtime/check_skills.py .agents/skills
```

A script the repo's skills really need is listed with `--allow <path>` after review.

A kit command can be overridden in a repo only where the CLI supports it ([matrix](cli/matrice.md)); elsewhere, write the project rule in `AGENTS.md`.

## For the organization: in the kit

### Create a component with `ai-kit new`

From a git clone of the kit, one command does the steps below that can be automated. A ZIP installation has no clone, so it is refused there.

```sh
ai-kit new skill --name dashboard-check --owner team-reporting   # asks what is missing
ai-kit new agent --name release-reviewer --owner team-platform
ai-kit new command --name dashboard-check-run --skill dashboard-check
ai-kit new profile --name mobile-developer --label "Mobile Developer: iOS and Android"
```

| What | Where it goes | What the command adds |
| --- | --- | --- |
| skill | always `skills/contrib/<name>/`, with an owner | its catalog entry at version `1.0.0`, a skeleton eval case and its section in [eval cases](eval-cases.md); a `domain` playbook gets its two required sections |
| agent | always `agents/contrib/<name>.md`, with an owner | its catalog entry at version `1.0.0`; read-only tools |
| command | `commands/<name>.md` | the pivot format, activating an existing skill |
| profile | `profiles/<name>.toml` | a start from `general.toml`, the playbooks and agents you choose, the profile table |

Moving a skill or an agent from `contrib/` to `internal/` stays a maintainer's act, at a usage review.

Then the checks run: `runtime/check_skills.py`, `scripts/versions.py --update`, `tests/snapshot.py --update`, `scripts/profile_table.py --write` for a profile or a command, and the tests a new component must respect. A failure stops before any commit and shows the real output; the files stay for review. An uncommitted change in a file these steps rewrite, or in what the version lock and the snapshot read (`skills/`, `agents/`, `commands/`, `installer/`…), stops the command before it writes anything: they would record it without the commit carrying it.

Last, two questions, always asked: the commit on a branch `new-<type>-<name>`, then the push and the merge request, through your own `glab` or `gh` when signed in, otherwise the page to open it by hand. `--yes` answers only the questions about the content, never these two; `--no-mr` stops after the checks. Without a terminal, a pipe or an agent's shell for instance, the command refuses before writing anything, unless both `--no-mr` and `--yes` are given: nothing but a person answers these two questions.

Every stop says how to undo it, Ctrl+C included. Before the commit, it gives the `git restore` line and what to delete. After the commit, it gives `git switch` and `git branch -D`. After the push, it adds closing the merge request and `git push origin --delete`. A commit that fails, on a hook or a missing identity, comes back to the branch it started from. The push question names where the push really goes, even when it differs from where git fetches.

What the command does not write is marked `<…>`, and listed at the end: the skill's instructions, the eval case's prompt and criteria. A skeleton eval case is never sent to a model: `evals/run.py` skips it until its prompt is written. The `write-a-skill` skill helps with the content. The skeleton is recorded at `1.0.0`, so its first content takes a new version: `1.0.1` in the catalog, then `python3 scripts/versions.py --update`.

A command joins every profile that installs its skill and has no `commands` list of its own, so it can change the snapshot and the profile table: the command refreshes both and shows the size of the changes to existing files before the commit; the new files are listed before they are written. On Windows the snapshot is not rewritten, because its reference holds POSIX paths: after a command or a profile, run `python3 tests/snapshot.py --update` on Mac or Linux.

### The steps by hand

Two folders, two levels of commitment. `skills/internal/`: shipped and maintained by the kit maintainers, in the profiles. `skills/contrib/`: proposed by a person or a team who stays its owner, never installed by default (`tier: optional`, `origin: contrib`, `owner` in the catalog), enabled with one line by anyone who wants it. A contributed skill that is widely used moves to `internal` at a usage review; a skill without a reachable owner is removed. The rules are in `skills/contrib/README.md` and checked by the tests. The steps below apply to both; only the folder and the `origin`, `owner`, `tier` fields change.


1. **The folder**: `skills/internal/<category>/<name>/SKILL.md` (existing categories: `common` for workflow and tools, then one per domain: `development`, `operations`, `architecture`, `analytics`), or `skills/contrib/<name>/SKILL.md` for a contribution. The folder name and the header `name` are identical.
2. **Its metadata** (AI Kit 2): the skill describes itself in its front matter, `metadata` keys `aikit-version`, `aikit-origin`, `aikit-summary`, `aikit-category`, `aikit-tier`, `aikit-requires` (comma-separated), and one `aikit-optional-<skill>: "<what to do without it>"` per optional skill; AI Kit reads them and removes them from the installed file. `ai-kit validate` checks a content tree. An example in the [full example](#full-example-a-dashboard-check-tool-in-twenty-minutes).
   `category`: `workflow` (a step, behind a command), `tool` (utility, behind a command), `domain` (domain playbook, activated by the task), `reference` (vocabulary read by other skills), `setup`. `tier`: `core` (in all profiles, a test checks it), `profile` (depends on the profile), `optional` (installed by the profiles that list it, otherwise through `extra_skills` or `extra_commands`). `requires` installs the skills it cannot work without, with it; `optional` maps a skill it cites but can do without to what to do instead (`{"codebase-design": "keep interfaces small…"}`): when that skill is not installed, the installed `SKILL.md` ends with a "Not installed here" section giving the alternative. A test checks that every skill a `SKILL.md` cites is in one of the two. `needs_agents: true` signals that it delegates to subagents.
3. **The profiles** `profiles/*.toml`: add it to the profiles that need it, or leave it `optional`. A domain playbook is never in the `general` profile. A playbook that a step chains ends with a `## In the kit commands` section (what it changes in `/build`, `/diagnose`, `/review`…): the commands stay neutral and send to the matching playbook.
4. **A command, if it is a step or a tool**: a `commands/<name>.md` file, with a header (`name`, `description` in English, `category`, `stage` for a workflow, `skills`, `order`) and a prompt with `{{args}}`; see [the pivot format](format.md). Each adapter turns it into its CLI's command. Add an entry in `docs/tools.md` for a tool.
5. **An eval case** `evals/cases/NN-<name>.json` with the prompt that must trigger the skill and an observable criterion, then `python3 scripts/offline_tests.py` and `python3 evals/run.py --dry-run` (a real run, `--confirm-paid-run`, is billed).
6. **Version**: a new skill starts at `"version": "1.0.0"` in its catalog entry; a changed one raises it (patch for a wording, minor for a behaviour added, major when what it produces or needs changes), then `python3 scripts/versions.py --update` records it in `versions.lock.json`. The tests refuse a skill or an agent changed under the same version. The CHANGELOG says what changed, naming the skill and its version; `update` tells each person which skills and agents changed.
7. **Distribute**: commit, merge request (MR), tag; workstations get it with the next version of the kit (a new ZIP, or `update` in a git clone, which pulls first).

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

2. Its metadata, in the front matter of the same `SKILL.md` (AI Kit reads it and removes it from the installed file):

   ```yaml
   metadata:
     aikit-version: "1.0.0"
     aikit-origin: "contrib"
     aikit-owner: "equipe-reporting"
     aikit-summary: "Review a dashboard before publishing: filters, period, totals, labels."
     aikit-category: "tool"
     aikit-tier: "optional"
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

   Activate the dashboard-check skill (if this skill is not installed here, follow the instructions below directly).

   Input: {{args}} (the dashboard, its SQL or a screenshot description).

   Answer in the user's language. State in one line whether this is a quick check or a full review. Follow the skill's four steps and end with what blocks publication.
   ```

4. The eval case, `evals/cases/13-dashboard-check-totals.json`:

   ```json
   {
     "name": "dashboard-check-totals",
     "prompt": "/dashboard-check the monthly sales dashboard, October total 1,240 orders",
     "cwd": "dbt-mini",
     "requires": { "commands": ["dashboard-check"] },
     "expect": { "regex": ["(total|1,240)", "(filter|period)"] }
   }
   ```

5. Check and distribute: `python3 scripts/offline_tests.py`, `python3 evals/run.py --dry-run --only dashboard-check-totals` (then, if the maintainer decides it, `--confirm-paid-run`: billed), then commit, merge request (MR) and tag (version and distribution: steps 6 and 7 above). Anyone who wants the tool enables it with one line: `extra_commands = ["dashboard-check"]` in `~/.ai-kit/overrides.toml`, then `update`; `/dashboard-check` appears in every supported CLI.

## Replace a kit skill for the organization

Keep the name and, if there is one, the command: other skills and the docs refer to them. Two cases.

- **Internal skill** (`origin: internal`): edit the `SKILL.md` in place, rerun tests and evals.
- **Base skill** (`origin: upstream`, taken as is under the MIT license): do not edit it; the next upstream copy will overwrite it. Write a short in-house version in `skills/internal/<category>/<name>/`, same name, and change `path` and `origin` in the catalog. The old version stays available if you keep it under another name as `optional`. This is what the [usage review](usage-review.md) calls an "in-house version".

## Remove a skill

For yourself: `disabled_skills = ["<name>"]` in `~/.ai-kit/overrides.toml`, then `update`. A skill required by another one cannot be disabled on its own; `update` says so. For the organization: set it to `optional` in the catalog rather than deleting it, so it stays available with one line.

## What a skill does not customize

Form and language preferences: `~/.ai-kit/context/30_USER.md` (`/me` fills it). A repo's rules: its `AGENTS.md`. Deterministic guardrails: the `[hooks]` section of `overrides.toml` and the repo's `.ai-kit/protected-paths` file. Agents: `extra_agents` and `disabled_agents`, or an `agents/internal/<category>/<name>.md` file in the kit with its `aikit-*` metadata. See [customization](customization.md).
