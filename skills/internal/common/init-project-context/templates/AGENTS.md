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
2. Run the "Changed" command of each stack touched. Run its "Full" command instead when a shared file changed: `<shared files: lockfiles, shared config, shared test setup such as conftest.py; for dbt, macros/, dbt_project.yml, packages.yml, seeds/>`.
3. Say in one line which scope you ran and why. Paste the real output. If a test fails, fix the code, never the test; never skip or delete one.
4. Never run against production: development target `<dev target or environment>` only.

| Stack | Changed | Full |
| --- | --- | --- |
| Python | `pytest <tests of the changed modules>` | `pytest` |
| JS / TS | `npx vitest run --changed <base branch>` or `npx jest --changedSince=<base branch>` | `npm test` |
| Java (Maven) | `mvn -pl <changed modules> -am test` | `mvn verify` |
| dbt | `dbt build --select state:modified+ --defer --state <production manifest dir> --target <dev>` (only what changed, the rest read from production); without a manifest: `dbt build --select <model>+ --target <dev>` | `dbt build --target <dev>` |
| Terraform | `terraform plan` in each changed root module | `terraform validate` and `plan` in every root module |
| Lint and types | `<linter> <changed files>` | `<lint and type-check command>` |
| Build | `<build command>` (must end with "<success marker>") | same |

Delete the rows of stacks this repo does not use; add one per other stack, same two columns.

## Report
<Optional. How /build, /test, /diagnose and /review end their report in this repo; delete this section to keep the kit's default.>
- <e.g. one line in business terms; components touched; commands run and their result; risks for what depends on them; what is left and who decides>

## Conventions
- Vocabulary: `GLOSSARY.md`; use its terms in code, models and messages.
- Decisions: `docs/adr/`; propose one for any decision that is hard to reverse.
- Artifacts: one folder per change, `docs/sdlc/<YYYY-MM-DD>-<slug>/` with `intent.md`, `spec.md`, `plan.md`; `REVIEW.md` at the root for review passes. `spec.md` and `REVIEW.md` are committed; `intent.md` and `plan.md` are local working notes ignored by git (change this line if the team decides otherwise). Never commit without being asked.
- Commits and MR: `<convention>`

## Architecture
- Environments: development `<target or environment>`; never `<production>` without instruction
- Layers or modules: `<e.g. api → service → repository, or source → staging → mart>`
- External systems: `<databases, warehouse project, queues, cloud accounts>`
- `<folder>` holds `<what>`; never edit `<generated>`

## Things the agent gets wrong
<!-- One line per mistake seen twice: the rule, then (since YYYY-MM: what happened). The date lets the team remove a rule that no longer serves. -->
- <Rule that prevents the mistake> (since <YYYY-MM>: <what the agent did>)

## Where the rest lives
- Architecture: `docs/<file>`
- Domain reference (APIs, models, KPIs): `<path>`
- Runbooks: `<path>`
