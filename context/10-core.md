# Core practices
The organization's rules, from its Core repository; an active Team adds its own after them. Each repo refines them in its `AGENTS.md`.
- Respect access rights and use the services authorized by the organization.
- Keep secrets out of code, prompts, logs and commits.
- Minimize personal data exposed in examples and results.
- State assumptions explicitly and ask for missing business decisions.
- Read the repo's instructions and conventions before modifying anything.
- Keep architecture, commands, reference data, indicators and decisions (ADRs) in the owning repo; document cross-cutting decisions according to the project's process.
- Reuse existing tools and abstractions; keep changes proportionate to the need.
- Before changing a component, state what it guarantees (contract, invariants, shape of its data or outputs) and keep it, or say what changes.
- Verify business logic on representative cases, not just compilation.
- Measure cost and performance before/after when they motivate the change.
- Run the relevant checks and report the results actually observed.
- Use the scopes and environments explicitly defined by the project; never production without an instruction.
- Text instructions do not replace IAM controls or administered policies.
