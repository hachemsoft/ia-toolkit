# shop-big

A dbt project with staging and marts layers, for the kit evaluations of the review.

## Verifying your work
1. Changed files: `git diff --name-only main...HEAD` plus `git status --short`.
2. Run `dbt build --select <model>+ --target dev` for each model touched.
3. Never run against production: development target `dev` only.
