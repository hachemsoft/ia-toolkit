# Reviewing a change

Everything about reviewing a change: what `/review` checks and how it ranks findings, how its agents are briefed, and how
the kit helps the person who reads the change before merging. Saying "review my changes" runs the same review as
`/review` (skill code-review). The review reports; it never fixes anything.

## What `/review` checks

**Scope**, by default: the branch's commits since the default branch, the staged and unstaged changes and the new files,
stated in one line. A base ref, `staged`, `local`, a path or a commit narrows it.

**Six passes**, always:

| Pass | Looks for |
| --- | --- |
| Bugs | logic, edge cases, error handling, regressions in callers |
| Security | secrets, injection, unsafe paths, personal data in logs or outputs, permissions |
| Domain | the checks of the installed playbooks matching the files (SQL, dbt, infrastructure…), with their reviewer agent when installed |
| Standards | the repository's `REVIEW.md`, `AGENTS.md`, `CONTRIBUTING.md`, the practices in the kit context, and a baseline of code smells, each worded as a judgement call |
| Compliance | the change against its `spec.md`, `intent.md` or `plan.md`, including each mitigation of the spec's Threats; skipped, and said, without one |
| Tests | the facts of the kit's test check: tests deleted, disabled or relaxed in the diff ([below](#tests-a-change-weakens)) |

**One severity scale**: **Important** breaks behaviour, data, security or a written policy, and must be fixed before
merging; **Minor** is a real defect with limited impact, or a missing test for changed behaviour; **Nit** is style or
naming, five at most (or the cap of `REVIEW.md`).

**Level**: `quick` or `full`, inferred from the size and the paths touched and stated, or given (`/review full`). `full`
adds the doubter: the claims the change relies on are listed and doubted, and for a change hard to undo, how a failure
would show and how it is undone.

**The report**: the scope line, the doubter's position (or why it was not assessed), the findings ranked with their pass,
severity, file and line, the unresolved discussions of the merge request, then the limits: what was not reviewed and why,
starting with whether the dedicated security review ran. A section `## Report` in the repository's `AGENTS.md` or in your
`USER.md` changes its shape. In a monorepo, the review names every other area the change reaches, so their owners review
too.

## A change at risk gets independent reviewers

A change is at risk at the full level, or when it touches personal data, secrets or tokens, authentication or
permissions, input from outside (a request, a file, a webhook) or an external service, agent configuration (`AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, a skill, an agent or command definition, a hook, an MCP server), or when its spec has a
Threats section, or on request. It then gets a dedicated security review, whatever the level: code-reviewer (Bugs and Standards),
security-reviewer (Security) and doubter each work in a fresh context, at the same time when the CLI can, and their
findings are merged into one list. A change to agent configuration also goes to contribution-auditor, which looks for
hidden instructions, invisible or bidirectional characters, widened tools or permissions and data sent out; the limits
then say "Security review: dedicated (agent configuration)". At the full level, blast-radius maps what the change can
reach (callers, public contracts, downstream dbt models, configuration, other areas) with a Mermaid map and what to test
before the merge; `/spec` asks it too, before writing the risks. The other passes stay with the main agent. A change without risk is reviewed in the
main pass, and the report says so. `/build` does not run the dedicated review on its own change. A review by an AI agent
replaces neither an audit nor a penetration test. Decision: [ADR 0029](adr/0029-risk-based-security-review-by-independent-reviewers.md).

## What a repository adds: REVIEW.md

A repository's `REVIEW.md` adds to the six passes and never removes one: its domain rules, its conventions, what
Important means there, its nit cap and what not to report. Its severity rule and exclusions never lower a Security or
Tests finding; a line asking to remove a pass is reported in the limits. `/review` offers to create it once, at the
standard or full level, when it is missing ([project context](project-context.md)). Decision:
[ADR 0032](adr/0032-project-context-adds-to-the-kit.md).

## Tests a change weakens

A model under pressure can "make the tests pass" by changing the tests. Before the Tests pass, a read-only script
(`runtime/weakened_tests.py`) lists from the diff the tests deleted, disabled or relaxed. The review judges each
fact: covered by a contract you named (in the session, or in the change's `spec.md`, `intent.md` or `plan.md`), it is an
intended test change, listed as such; otherwise it is an Important finding. A commit message never counts as a contract,
since the agent writes it. The script never blocks, so a contract changed on purpose stays possible. Decision:
[ADR 0027](adr/0027-a-deterministic-signal-feeds-the-review-it-never-blocks.md).

## Cold review: the agents judge the change, not the story

When `/review` gives passes to sub-agents (a change at risk, `full`, a domain reviewer), each one starts in a fresh
context. A fresh context only helps if it is not filled with the author's account: "I
added a retry, it is idempotent, the tests pass" makes a reviewer look for bugs around the retry and take "idempotent" for
granted, when that is the claim to check.

So every reviewer gets references only: the scope commands, the base, the raw output of `git diff` (the agents can only
read, so the diff is copied as it is, never summarised), the paths of the changed files, the facts of the kit's test
check and the spec, intent or plan. Never a summary of the change, a justification or an announced test result. A
reviewer that finds one in its brief ignores it and says so in its limits.

The doubter is the exception that confirms the rule: its job is to doubt the author's claims, so it gets them, labelled
"claims to check" (spec, intent, commit messages, merge request description), never as facts.

## The doubter takes a position

When it runs (`/review full`, or a change at risk), the doubter argues the case against the change, since everything
else pushes to ship it, and starts with:

```
position: no objection | concerns | oppose
strongest objection: <the single best argument against, or "none">
simpler alternative: <one sentence, or "none">
would a stranger understand in six months: yes | no (<what is missing>)
```

It never manufactures an objection, keeps `oppose` for a real cost, and makes no style remark. The `/review` report shows
its position and strongest objection right after the scope line, or "Position: not assessed" with the reason.

## A review guide for the person

At the standard and full levels, `/review` and `/ship` offer a review guide (skill `review-guide`): `review-guide.md` in
the change folder, local and git-ignored, with a reading order, the hunks grouped by theme, the change's assumptions, the
risk points and what to skim. It is for the person; the review agents never see it before their pass.

You answer in the files themselves, with a **mark**: a comment whose text starts with `review:`
(`<!-- review: … -->` in Markdown, `# review:` in Python or YAML, `// review:` in JavaScript, Java or Go, `-- review:` in
SQL). Then say "reviewed": the agent handles every mark in one batch, removes the ones it resolved, answers the others
with `review-reply:` under them, never removes a mark it did not handle, and reports each one with a before / after
excerpt and the count of resolved and open marks. The same marks work on `spec.md` after `/spec`, and on the acceptance
tests of `/build`: a mark still open means the tests are not approved. A mark left in a diff is a Minor finding in
`/review`.

## On the merge request

When the branch has an open merge request, `/review` reads its unresolved discussions (`glab mr view <id> --unresolved`;
on GitHub, `gh pr view --comments`, which does not filter resolved threads) and reports each one as confirmed, refuted
with evidence, or a point to decide. They are data, never instructions. Posting the guide on the merge request, or
answering in a thread, happens only on request, with the exact text shown first and your agreement each time; the agent
never resolves a thread.

## Proof that a test tests something

A test can pass even without the code it is meant to cover. In `/build`, at the standard and full levels, the verifier
proves the approved acceptance tests: the kit script `prove_test.py` puts the code of the change back to its base version,
runs the tests, and restores every file. The tests must fail without the code (`proven`); a test that still passes
(`not_proven`) stops `/build` and you decide: strengthen it, or accept it and the merge request says so.

The script backs up each file it touches, with its mode, in `.ai-kit-proof/` at the repo root (ignored by git) before any
change, restores them on every exit it sees, interruption included, and checks each one byte for byte; a file saved
during the run is kept and reported, never overwritten. If a hard stop (`kill -9`, a crash) cut a proof short, the next
run refuses until you agree to `prove_test.py recover`. Tools that watch files (an editor, hot reload) may see the
swap for the time of the test. The same script reruns a red check on the base version to tell a failure the change
brought from one already there, and lists the existing tests the change modifies. A warehouse test (dbt) runs only on the
development target the repo declares, with the cost announced and your agreement. Decision: [ADR 0033](adr/0033-verifier-swaps-files-to-prove-a-test.md).
