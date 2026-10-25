# ventes-mini

Mini repo dbt de test pour les évaluations du kit.

## Commands
- Test: `dbt test --target dev`

## Verifying your work
Test what changed and what depends on it, whoever owns it. The full suite runs in CI.

1. Changed files: `git diff --name-only main...HEAD` plus `git status --short`. Base branch: `main`.
2. Run the "Changed" command of each stack touched; run "Full" when `macros/`, `dbt_project.yml` or `seeds/` changed.
3. Say which scope you ran and why. Paste the real output.
4. Never run against production: development target `dev` only.

| Stack | Changed | Full |
| --- | --- | --- |
| dbt | `dbt build --select <model>+ --target dev` | `dbt build --target dev` |

## Conventions
- Vocabulary: `GLOSSARY.md`.
- Development target: `dev`; never build on `prod` without instruction.
