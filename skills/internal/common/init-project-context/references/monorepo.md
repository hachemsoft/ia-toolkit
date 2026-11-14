# Monorepo: one AGENTS.md per layer, only where useful

Read this only when the repo holds several applications.

## Find the layout
Use evidence, most reliable first; never guess:
1. Workspace files that already list the applications: `pnpm-workspace.yaml`, `workspaces` in `package.json`, `nx.json`, `turbo.json`, `lerna.json`, `go.work`, `settings.gradle(.kts)`, a parent `pom.xml` with `<modules>`, a multi-project `build.sbt`, `composer.json` path repositories.
2. Each folder with its own build file is an application: `package.json`, `composer.json`, `pyproject.toml`, `go.mod`, `pom.xml`, `build.gradle`, `dbt_project.yml`, a Terraform root module. Skip dependency and generated folders (`vendor/`, `node_modules/`, `dist/`, `build/`). A folder whose subfolders are applications is a family, even with a build file of its own.
3. Boundaries the team already draws: CI jobs filtered by folder, `CODEOWNERS`.
When the evidence is missing or contradicts itself, ask; do not invent a family.

## Propose layers
- Root `AGENTS.md`: the map, one line per family: folder, role, file to read (`apis/`: back-end APIs, see `apis/AGENTS.md`), and only what the whole repo shares (base branch, CI, the git rule).
- One `AGENTS.md` per family (`ui/`, `apis/`, `functions/`): what its applications share: versions, tools, the "Verifying your work" table, conventions.
- One `AGENTS.md` per application only when it differs from its family: other commands, other rules, other constraints. Fifteen near-identical files are worse than one.

## Inheritance, written out
A family or application file holds only its differences and starts, under its title, with one line:
`Extends <relative path of the parent file>. Overrides: <rule of the parent> → <rule here>.` (or `Overrides: none.`); the parent is the nearest `AGENTS.md` above: the family's, else the root's.
Example: `Extends ../AGENTS.md. Overrides: test command \`vendor/bin/phpunit\` → \`make test-billing\`.`
The CLIs do not settle a conflict between a nested file and its parent the same way (one concatenates every file it finds), so the file says which rule wins.

## Show the map before writing
In the grouped proposal, start with the map: families, applications, the files proposed and why each application file exists ("3 families, 7 apps, 4 files: the root, `ui/`, `apis/`, `functions/`; `ui/admin` has its own build commands, so it gets its own file"). The person regroups or splits; then write.

## Later, one application
"Initialize the context of `apis/billing`": read its parent file, propose only `apis/billing/AGENTS.md` with its differences and its `Extends` line, and the root map line if it changes. Touch no other file. No parent file yet: say so and propose the root map (and the family file) in the same grouped proposal.
