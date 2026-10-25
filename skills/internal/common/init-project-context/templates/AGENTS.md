# <Project name>

<One sentence: what this repo does and for whom.>

## Commands
- Install: `<command>`
- Run: `<command>`
- Test: `<command>`
- Lint: `<command>`

## Verifying your work
Test what changed and what depends on it, whoever owns it. The full suite runs in CI.

1. Changed files: `git diff --name-only <base branch>...HEAD` plus `git status --short`. Base branch: `<main>`.
2. Run the "Changed" command of each stack touched. Run its "Full" command instead when a shared file changed: `<shared files: macros/, dbt_project.yml, packages.yml, seeds/, package.json, lockfile, conftest.py, shared config>`.
3. Say in one line which scope you ran and why. Paste the real output. If a test fails, fix the code, never the test; never skip or delete one.
4. Never run against production: development target `<dev target or environment>` only.

| Stack | Changed | Full |
| --- | --- | --- |
| dbt | `dbt build --select state:modified+ --defer --state <production manifest dir> --target <dev>` (rebuilds only what changed, reads the rest from production); without a reference manifest: `dbt build --select <model>+ <model>+ --target <dev>` | `dbt build --target <dev>` |
| Python | `pytest <tests of the changed modules>` | `pytest` |
| JS / TS | `npx vitest run --changed <base branch>` or `npx jest --changedSince=<base branch>` | `npm test` |
| Lint and types | `<linter> <changed files>` | `<lint and type-check command>` |
| Build | `<build command>` (must end with "<success marker>") | same |

Delete the rows of stacks this repo does not use; add one per other stack, same two columns.

## Report
<Optional. How /build, /test, /diagnose and /review end their report in this repo; delete this section to keep the kit's default.>
- <e.g. one line in business terms; models touched with their grain; commands run and their result; risks for downstream dashboards; what is left and who decides>

## Conventions
- Vocabulary: `GLOSSARY.md`; use its terms in code, models and messages.
- Decisions: `docs/adr/`; propose one for any decision that is hard to reverse.
- Artifacts: one folder per change, `docs/sdlc/<YYYY-MM-DD>-<slug>/` with `intent.md`, `spec.md`, `plan.md`; `REVIEW.md` at the root for review passes. `spec.md` and `REVIEW.md` are committed; `intent.md` and `plan.md` are local working notes ignored by git (change this line if the team decides otherwise). Never commit without being asked.
- Commits and MR: `<convention>`

## Architecture
- Warehouse and project: `<BigQuery project>`, datasets `<list>`
- Development target: `<dbt target or environment>`; never build on `<prod>` without instruction
- Layers: `<source → staging → intermediate → mart>`; grain documented at the top of each model
- `<folder>` holds `<what>`; never edit `<generated>`

## Things the agent gets wrong
- <Mistake seen twice, and the rule that prevents it.>

## Where the rest lives
- Architecture: `docs/<file>`
- Models and KPIs: `<path>`
- Runbooks: `<path>`
