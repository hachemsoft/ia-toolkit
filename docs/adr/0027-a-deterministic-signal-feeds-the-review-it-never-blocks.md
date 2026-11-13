---
status: accepted
since: 4.3.0
---
# A deterministic signal feeds the review; it never blocks

"Never weaken, skip or delete a test" was a prompt rule only, and a review by a model can miss what it was asked to watch.
The kit now ships `weakened_tests.py`, a read-only script installed next to `friction.py`: it reads the diff of the
review's scope and lists, without judging, the test files deleted or moved in any language, and, per family of test
tools, the tests removed, disabled or focused, the assertions removed or changed, the severities and thresholds relaxed.
dbt is the first family; Java, Python, JavaScript, PHP, Go, Rust and Scala follow, one at a time, each with its own
positive and negative cases. The
code-review skill runs it before its passes and adds a Tests pass: a fact covered by a contract the person named (in the
session, `spec.md`, `intent.md` or `plan.md`; never a commit message, which the agent writes) is reported as an intended
change; a fact without one is an Important finding; a vague contract becomes a question. When the script cannot run, the
review goes on and says so.

**Why**: a deterministic check is reproducible and costs no token, a model's review judges intent; together they catch a
weakened test and still allow a contract changed on purpose, which the kit's test rule permits. Blocking would forbid that
change; a prompt rule alone gave no measured gain (eval case `red-suite-keeps-its-test` ties with and without the kit).

**Consequences**: one more kit tool in the guardrail's allowed list; the skill's version moves; each family of test tools
carries its own rules and negative cases, and a noisy family can be removed alone; eval case `review-flags-weakened-test`
measures the gain. The pattern is reusable: a later signal follows the same shape (read-only script, facts as JSON, the
review judges, nothing blocks).

**Considered**: a hook that blocks writes to test files (it forbids intended contract changes); a review instruction
without a script (still a prompt rule); running the script in `/build` and `/test` too (more places to maintain before the
signal is measured); parsing each language fully (a dependency per language, against the standard-library rule).
