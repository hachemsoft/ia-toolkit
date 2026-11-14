# <Project name>

<One sentence: what this repo does and for whom.>

## Commands
- Versions: `<language and version, framework and version, build tool>`
- Install: `<command>`
- Run: `<command>`

## Verifying your work
Test what changed and what depends on it, whoever owns it. The full suite runs in CI.

1. Changed files: `git diff --name-only <base branch>...HEAD` plus `git status --short`. Base branch: `<main>`.
2. Run the "Changed" command of each stack touched. Run its "Full" command instead when a shared file changed: `<shared files: lockfiles, shared config, shared test setup such as conftest.py; for dbt, macros/, dbt_project.yml, packages.yml, seeds/>`.
3. Say in one line which scope you ran and why. Paste the real output.
4. Never run against production: development target `<dev target or environment>` only.

| Stack | Changed | Full |
| --- | --- | --- |
| Python | `pytest <tests of the changed modules>` | `pytest` |
| JS / TS | `npx vitest run --changed <base branch>` or `npx jest --changedSince=<base branch>` | `npm test` |
| Java (Maven) | `mvn -pl <changed modules> -am test` | `mvn verify` |
| Java (Gradle) | `./gradlew :<changed module>:test` | `./gradlew check` |
| PHP | `vendor/bin/phpunit <tests of the changed classes>` | `composer test` or `vendor/bin/phpunit` |
| Go | `go test ./<changed packages>/...` | `go test ./...` |
| Scala (sbt) | `sbt "<changed project>/test"` | `sbt test` |
| dbt | `dbt build --select state:modified+ --defer --state <production manifest dir> --target <dev>` (only what changed; reads the production manifest, never writes there); without a manifest: `dbt build --select <model>+ --target <dev>` | `dbt build --target <dev>` |
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
- Review rules: `REVIEW.md`
- Repo skills: `<.agents/skills/<name>/>`, what each is for
- Architecture: `docs/<file>`
- Domain reference (APIs, models, KPIs): `<path>`
- Runbooks: `<path>`
