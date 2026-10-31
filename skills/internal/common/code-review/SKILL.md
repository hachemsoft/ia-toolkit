---
name: code-review
description: "Review changes, committed or not: the branch's commits, the staged and unstaged changes and the new files, by default; or a narrower scope the person names. Finds bugs, security issues, breaks of the repo's standards and of the spec when there is one, ranked on one severity scale. Use when the person asks to review their work, a branch, a PR or MR, or \"what changed since X\"; /review runs it."
---

The kit's single review behaviour: `/review` and a plain request ("review my changes") both follow it, with the same scope rule, passes and severities. Report only: fix nothing.

## 1. Scope: everything that changed, unless the person narrows it

By default, review all of these, against the base (the branch the work will merge into: what the person names, otherwise the repo's default branch):

```sh
git rev-parse --abbrev-ref origin/HEAD                 # default base, e.g. origin/main (else main or master)
git merge-base <base> HEAD                             # where the branch started
git log --oneline <merge-base>..HEAD                   # commits of the branch
git diff <merge-base>                                  # committed + staged + unstaged changes to tracked files
git diff --cached --stat                               # what is staged
git ls-files --others --exclude-standard               # new files not yet added
```

Read the new files that matter (source, tests, configuration); skip generated output, data dumps and binaries, and say so. State the scope in one line before the findings: "Reviewing N commits since <base>, staged and unstaged changes, K new files". The person can narrow it: "only staged" (`git diff --cached`), "only my local changes" (`git diff HEAD` plus new files), "since <ref>", a path, a commit. Conclude "nothing to review" only when all of the above are empty, never from the commits alone.

## 2. What the change should do

Use what exists, in this order: a spec, intent or plan the person points to; `spec.md`, `intent.md` or `plan.md` in the change folder; a ticket the commits or the person cite, when a tracker is reachable. None of them is required: for a small change without a written spec, the expected behaviour is what the person said; skip the Compliance pass and say so in one line. Never ask for a spec or a tracker before reviewing.

## 3. Passes

Run them in sequence, or delegate them to the installed `ai-kit-*` review agents when available (give them the scope commands and the files):

- **Bugs**: logic, edge cases, error handling, regressions in callers.
- **Security**: secrets, injection, unsafe paths, personal data in logs or outputs, permissions.
- **Domain**: the checks of the installed playbooks matching the files (listed in 00_KIT.md).
- **Standards**: `REVIEW.md` when it exists (its passes, severity rule, nit cap and exclusions win), `AGENTS.md`, `CONTRIBUTING.md` or `CODING_STANDARDS.md`, the practices in your context, and the smell baseline below.
- **Compliance**: matches the spec, intent or plan from step 2; skipped without one.

On top of whatever the repo documents, the Standards pass always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

## 4. Severity, the same wherever the review starts

- **Important**: breaks behaviour, data, security or a written policy; must be fixed before merging.
- **Minor**: a real defect with limited impact, or a missing test for changed behaviour.
- **Nit**: style or naming; at most five, the rest dropped.

A smell from the baseline is at most Minor and always worded as a judgement call. Tag each finding with its pass, severity, file and line, and the evidence (the hunk, the failing input). Rank by severity.

## 5. Report

The scope line, the findings ranked, then the limits (what was not reviewed and why). If the repo's `AGENTS.md` or the person's `30_USER.md` has a "## Report" section, shape the report as it says.
