# data-mono

Monorepo dbt partagé par deux équipes : finance et marketing. Un seul projet dbt.

## Areas
- `finance/`: own AGENTS.md, owner team finance.
- `marketing/`: own AGENTS.md, owner team marketing.

## Verifying your work
Test what changed and what depends on it, whoever owns it. The full suite runs in CI.

1. Changed files: `git diff --name-only main...HEAD` plus `git status --short`. Base branch: `main`.
2. Run the "Changed" command of each stack touched; run "Full" when `macros/` or `dbt_project.yml` changed.
3. Say which scope you ran and why. Paste the real output.
4. Never run against production: development target `dev` only.

| Stack | Changed | Full |
| --- | --- | --- |
| dbt | `dbt build --select <model>+ --target dev` | `dbt build --target dev` |
