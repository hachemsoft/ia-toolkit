---
status: accepted
since: 4.20.0
---
# Resuming reads the files and git; the evals measure it over several turns

An agent that picks up earlier work, in the same CLI or another one, starts from what any of them can read: the change's
artifacts and git. One line of the kit context says how (4.21.0, completed in 4.22.0): first read `git status`, the branch,
the other branches, the log and the artifacts; name the artifact and the step resumed from; an approved test or plan changed
since its approval, or whose approval nothing records, is shown and asked again, never restored or assumed; a change outside
the plan the agent did not make is named and asked about before building on it; an operation with side effects already run
is not replayed. The kit keeps no task state, adds no hook and runs no loop of its own: the CLI's agent loop, the commands'
gates and the correction limit of `/build` and `/diagnose` (three different fixes of the same check, then stop) stay as
they were. A behaviour is changed only after an eval shows a gap, and measured again after the change.

The evals measure it (4.20.0): a case may hold several `turns`, each resuming the previous session (`claude -c -p`,
`codex exec resume --last`) or starting afresh; a `between` builds the state a previous session left (a commit on a
branch, a file changed since) without a billed turn; `file_regex` and `unchanged` judge the files, not only the answer.
Antigravity runs every case with `--sandbox`, the only mode where its print mode runs shell commands; a writable case on
Claude Code may run `python -m pytest`, `python3 -m pytest` and `git`, nothing else of the shell.

**Why**: the audit of 2026-11-21 found nothing that could measure a resume or the correction loop: one-turn evals, criteria
on the answer only, writes refused. Measured before the rule (one run per case, cases 40-44): Claude 4/5, Codex 1/5,
Antigravity not measurable; after: 5/5 on all three. A new session ignored the other branches, did not name the plan it
followed, restored a changed approved test on its own, assumed an approval nothing recorded, built on someone else's change
before asking. The correction loop (cases 45, 46, 31) showed no gap on any of the three, so its text did not change.

**Consequences**: the kit context's budget goes from 3 800 to 4 300 characters (about 110 tokens more per session; ADR 0034
still says 3 800). A resume is as good as the files: a standard change leaves no plan, and its approval is asked again.
One run per case is a signal, not a statistic. A criterion is widened only when an answer shows the right behaviour in
other words (cases 31, 41, 44 so far), and the widening keeps the earlier verdicts. On Antigravity, print mode returns
before a sub-agent it started has answered, and `--sandbox` lets it write in the case's copy where the others cannot.

**Considered**: a Stop or AfterAgent hook that sends the agent back to work: the four CLIs have one, with different contracts
(`block`, `deny`, `continue`), unverified on Antigravity, and a wrong condition loops and bills. A task state file or a
`## Progress` section: no measured gap needed it once the rule was in place. A deterministic orchestrator or a task graph
by default: no gap measured; `to-tickets` and `implement-spec` stay optional. Trace assertions parsed from each CLI's
transcript: four formats that change with each version; files and git were enough. A model as judge: not deterministic.
