# shop-mini

Mini dbt repo with data tests, for the kit evaluations of the review.

## Commands
- Test: `dbt test --target dev`

## Verifying your work
1. Changed files: `git diff --name-only main...HEAD` plus `git status --short`.
2. Run `dbt build --select <model>+ --target dev` for each model touched.
3. Never run against production: development target `dev` only.

## Conventions
- Development target: `dev`; never build on `prod` without instruction.
