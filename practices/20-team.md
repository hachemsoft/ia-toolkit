# Team practices — proposed baseline, to validate
These practices apply to everyone; each repo refines them in its `AGENTS.md`.
- Read the repo's instructions and conventions before modifying anything.
- Keep architecture, commands, reference data, indicators and decisions (ADRs) in the owning repo.
- Reuse existing tools and abstractions; keep changes proportionate to the need.
- For a data transformation or a query: establish the grain, join cardinalities, date rules and NULLs.
- Verify business logic on representative cases, not just compilation.
- Measure cost and performance before/after when they motivate the change.
- Run the relevant checks and report the results actually observed.
- Use the scopes and environments explicitly defined by the project; never production without an instruction.
