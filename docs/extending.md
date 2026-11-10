# Extending and contributing

How to add or change a skill, a command, an agent or a workflow, the content format, the checks to run before a merge
request, and how a release is made. The content is text an agent reads: it is reviewed and tested like code.

## Where a change goes

| For | Where | Reaches |
| --- | --- | --- |
| you only | your CLI's own skills folder, a name the kit does not use ([matrix](cli/matrice.md)) | your CLI; the kit never touches it |
| one repo | `<repo>/.agents/skills/<name>/SKILL.md`, versioned, a name of its own | the CLIs that read `.agents/skills/` |
| one team | a Team repository: its skills, agents, `context/*.md` and `[defaults]` ([repositories](repositories.md)) | the Team's members, at `ai-kit sync` |
| everyone | the Core (this repository): `skills/`, `agents/`, `commands/`, `context/` | every workstation, at the next tag |

A repo's skills escape the kit's review: protect `.agents/` with `CODEOWNERS` and run the kit's check in the repo's CI,
from a checkout of the kit at a tag: `python3 <kit>/runtime/check_skills.py .agents/skills` (a reviewed script is listed with
`--allow <path>`). A Team repository is checked with `ai-kit validate --path <folder>` before it is tagged.

## Content format

**Skill**: `skills/internal/<category>/<name>/SKILL.md` (categories `common`, `development`, `operations`, `architecture`,
`analytics`), or `skills/contrib/<name>/SKILL.md`. The folder name equals the front matter `name`. Supporting files sit in
the same folder. The description says when to use it, the body what to do. AI Kit reads the `aikit-*` metadata and strips it
from the installed file:

```yaml
---
name: dashboard-check
description: "Review a dashboard before publishing: filters, period, totals, labels. Triggers: review this dashboard."
metadata:
  aikit-version: "1.0.0"         # required; raised at every change
  aikit-origin: "contrib"        # internal | upstream | contrib
  aikit-owner: "team-reporting"  # required for contrib
  aikit-default: "false"         # "true": installed for everyone
  aikit-category: "tool"         # workflow | tool | domain | reference | setup
  aikit-summary: "Review a dashboard before publishing."
  aikit-requires: "grilling"     # installed with it; comma-separated
  aikit-optional-tdd: "write the check first by hand"   # what to do when an optional skill is absent
---
```

Other keys read: `aikit-license`, `aikit-needs-agents: "true"` (it delegates to sub-agents), `aikit-protected: "true"` (a
Team cannot replace it). A required skill that does not exist, or a cycle, is refused before anything is installed.
`disable-model-invocation: true` makes a skill user-only: no command may chain it.

**Agent**: `agents/internal/<category>/<name>.md` or `agents/contrib/<name>.md`, front matter `name` (the file name),
`description`, optional `tools`, `max_turns`, `timeout_mins`, and `metadata` with `aikit-version`, `aikit-origin`,
`aikit-default`, `aikit-owner`. A file without `aikit-version` is not installable. Defaults: `agents/defaults.json`.

**Command**: `commands/<name>.md`; each adapter derives its CLI's form ([matrix](cli/matrice.md)).

| Field | Meaning |
| --- | --- |
| `name` | the file name; becomes the command |
| `description` | one line in English; a step starts with its stage (`Plan:`, `Build:`) |
| `category` | `workflow` (a step) or `tool` |
| `stage` | for a workflow: Plan, Design, Build, Test, Deploy or Maintain |
| `skills` | the skills it activates, `[]` for none; installed only when all are |
| `artifact`, `order` | what it produces; position in lists (1000 by default) |
| `default` | `false`: optional, turned on with `extra_commands` |

The body is the prompt; `{{args}}` receives what the person types; no triple double quotes. Every skill named in an
"Activate the X skill" line must be in `skills:`, with the fallback "if this skill is not installed here, follow the
instructions below directly". Commands name no domain; mention a playbook only as "the installed playbook matching the
files or the task". A command that changes something states `Level:` on its first line.

**Context**: `context/NN-<id>.md` becomes `NN_<ID>.md` in `~/.ai-kit/context/` (`10-company.md`, `20-team.md`; a Team's
context replaces the team layer). `templates/kit-context.md` becomes `00_KIT.md`. Business facts stay in the projects.

**News**: `NEWS.md` entries are `## <YYYY-MM-DD> <id> : <title>`, then optional `teams: <names>` and `until: <date>` lines,
then the text; `python3 scripts/check_news.py` checks them.

## Add or change a component

1. Write the skill, agent or command as above. A domain playbook stays optional and ends with `## In the kit commands`,
   one bullet per step it changes (`` - `/build`: … ``). A new user-facing behaviour gets an eval case ([evals](evals.md)).
2. Version: a new component starts at `1.0.0`; a change raises it (patch for wording, minor for an added behaviour, major
   when what it produces or needs changes), then `python3 scripts/versions.py --update` records it in `versions.lock.json`.
   The tests refuse a change under the same version.
3. Regenerate what depends on it: `python3 scripts/workflows.py --write` after a command change,
   `python3 scripts/selection_table.py --write` after a change to what is installed by default (it rewrites a table in
   `docs/getting-started.md`), `python3 tests/snapshot.py --update` when installed files change on purpose (on Mac or
   Linux: the reference holds POSIX paths). Review the diffs.
4. Run the checks below, then open a merge request. The CHANGELOG names the component and its version.

A contributed skill or agent moves from `contrib/` to `internal/` at a usage review; one without a reachable owner is
removed. To replace an upstream skill, write an in-house version under `skills/internal/` with the same name and
`aikit-origin: "internal"`; do not edit upstream text in place without recording it in `skills/upstream.lock.json`. To
retire a skill, set `aikit-default: "false"` rather than delete it. A new CLI is one adapter module ([matrix](cli/matrice.md#add-a-cli)).

## Checks before a merge request

What CI runs (`.github/workflows/portability.yml`, mirrored for Linux runners in `.gitlab-ci.yml`), all without a model:

| Check | Command |
| --- | --- |
| tests, every model CLI taken off the PATH | `python scripts/offline_tests.py discover -s tests -v` |
| lint | `ruff check .` (ruff 0.6.9) |
| settings files follow their schemas | `check-jsonschema --schemafile schemas/source.schema.json aikit.toml examples/team-repo/aikit.toml` |
| `NEWS.md` well formed | `python3 scripts/check_news.py` |
| no risky instruction, secret or undeclared script | `python3 runtime/check_skills.py` |
| release ZIP builds and installs offline | `python scripts/build_release.py` (needs the full git history) |

The test job first fills a local wheelhouse that stands for a package index:
`python -m pip download --quiet --only-binary=:all: --no-deps -d build/wheelhouse -r packaging/runtime.txt hatchling==1.27.0 packaging pathspec pluggy trove-classifiers`,
then `python -m pip install --quiet --no-index --find-links build/wheelhouse -r packaging/runtime.txt`. Without these, the
interface and launcher tests are skipped. Also useful, and run by the tests: `python3 scripts/versions.py`,
`python3 scripts/workflows.py`, and `python3 -m installer validate` (the kit's own content). Paid evals are never part of
these checks.

`runtime/check_skills.py` refuses a download piped into a shell, an instruction to drop previous instructions, a
permission bypass, an instruction to turn a guardrail off or to change the kit's or a CLI's configuration, a secret, and
a script not listed in its `KIT_ALLOWED`. It finds obvious forms only: review stays the barrier.

## Releasing

1. Set the version in `VERSION` and `pyproject.toml` (a test checks they match), and `min_engine` in `aikit.toml` when the
   content needs a newer engine. Write the CHANGELOG section `## <version>`; a fixed friction is cited by id,
   `(frictions: <id>)`.
2. To try a build before committing: `python3 scripts/build_release.py --worktree` (a test ZIP; never publish it).
3. Merge, then push the tag `v<version>` alone. On a tag, CI builds the ZIP from the committed files (the engine wheel,
   the pure-Python dependency wheels pinned in `packaging/runtime.txt`, the launchers, `INSTALL.txt`, the docs, and the
   Core as `core/ai-kit-core.bundle` at that tag), tests it on Linux, macOS and Windows with Python 3.11 and 3.14 and no
   package index, then publishes it with `SHA256SUMS.txt`, a build provenance attestation and the CHANGELOG section.
   A published asset is never overwritten.
4. Workstations take the new content with `ai-kit sync`, which installs the highest stable `vX.Y.Z` tag of their Core;
   a tag must never move. When IT lists `git.signers`, the tag must carry an SSH signature from one of those keys.

`scripts/export_core.py <empty folder> [--git]` writes the content in the flat layout of a separate Core repository, for an
organization that keeps its Core apart from the engine.

## Contributing

- Read `AGENTS.md` and the ADRs ([index](adr/README.md)) first; a change that reverses one comes with a new ADR.
- The repository is generic and public, in English: no organization, project or person names, no competing products.
- `CODEOWNERS` names who approves `skills/`, `agents/`, `commands/`, `templates/`, `runtime/`; an organization's copy
  fills it in and requires the code owners' review on the default branch.
- From a clone, run the engine with `python3 -m installer` (plain output without the interface libraries); try a change in
  an isolated home with `--home <folder>`.
- A support ticket is never answered twice the same way: it becomes a `doctor` check, a line in
  [troubleshooting](troubleshooting.md), or an eval case.
