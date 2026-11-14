---
status: accepted
since: 4.8.0
---
# Check the result, not the command: protected-paths reads no shell command but the kit's own

The need is narrow: when the CLI no longer asks before a command (an auto-approve or "yolo" mode, an "always allow" rule),
the agent must not change by mistake the configuration that watches it (the kit's rules and hooks, the CLI's settings, the
kit folder's git configuration) without anyone seeing it. Outside those modes the CLI's own approval prompt covers it.

`protected-paths` keeps refusing what it can judge exactly: a write tool aimed at that configuration (the CLI gives the
path) and the kit's own commands that change the installation or bill a model call. It reads no other shell command. An
integrity check runs after each tool call (Claude Code and Codex `PostToolUse`, Gemini CLI `AfterTool`) and at each
session start: it compares the files the kit installed, and the kit folder's `.git/config` and hooks, with what
`state.json` recorded (size and time first, a digest when they differ), and reports a change once, to the agent
(`additionalContext`) and to the person (`systemMessage`), with the command that restores it. On agy, whose post-tool
output is not documented, the check runs at session start only. A repo's own protected paths (`.ai-kit/protected-paths`,
4.6.0) are removed; a repo's CLI settings stay protected from the write tools. Supersedes ADR 0006.

**Why**: judging a shell command from its text does not converge. A closed list of readers refused reads all the time (five
false refusals in one session of 2026-11-14); relaxing it case by case opened writes it used to refuse (`cd`, `sed`); a
closed list of obvious writes refused 97 of 109 writes with no false alarm on 191 labelled commands, yet two independent
reviews found about fifteen holes in it (shell keywords, wrapper options, glued values, PowerShell and cmd forms,
`git --git-dir`, wildcards on folder names), each shell and each system bringing its own. The text of a command does not
hold what a variable, an alias or a script will do; a classifier model did worse than the rules
([research note](../research/classifier-model-for-guardrails.md)). Comparing files with what was recorded gives the same
answer on every system, whatever wrote them, at about 22 ms for 237 files. A comparable kit read for this decision protects
its configuration by none of these means.

**Consequences**: a shell command can change the configuration; it is reported after the call, not prevented, and the
actions after it run with the change until it is restored (`ai-kit sync --offline`). An agent that removes the post-tool
hook itself is seen at the next session start. The kit runs git without global configuration (repositories), so
`~/.gitconfig` is protected from the write tools only. The guardrail and the check ship together. Tests that expected a
shell refusal are listed in the 4.8.0 changelog.

**Considered**: a closed list of readers (false refusals); a closed list of obvious writes (holes per shell and system,
reviewed); a classifier model before each command (a model on every workstation, about 190 ms per command, probabilistic
errors, worse on the measured set); writing deny rules into each CLI's permissions (the kit never writes a person's
permissions; IT can deploy them as managed settings); a check at session start only (a change would act for the rest of
the session unreported).
