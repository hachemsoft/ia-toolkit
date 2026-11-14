# Reviewing a change

How the kit helps the two kinds of reviewer of a change: the review agents, and the person who reads it before merging.

## Cold review: the agents judge the change, not the story

`/review` gives its passes to sub-agents in a fresh context (code-reviewer, security-reviewer, doubter, and the domain
reviewers of the installed playbooks). A fresh context only helps if it is not filled with the author's account: "I
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
