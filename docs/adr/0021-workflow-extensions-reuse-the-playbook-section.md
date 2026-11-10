---
status: accepted
since: 4.0.0
---
# Workflow extensions reuse the playbook section "In the kit commands"

An additive extension of a Core workflow is a skill with `aikit-category: domain` (Core optional or Team) whose last H2 is
`## In the kit commands`. Each bullet starts with one or more backticked command names and a colon
(`` - `/build`, `/diagnose`: … ``) and adds steps or checks inside that command's step. The insertion points are the
commands whose prompt tells the agent to follow "the installed playbook matching the files or the task, including its
"In the kit commands" section": `/intent`, `/build`, `/review`, `/diagnose` and `/learn`. A Team never edits a Core command,
removes a step, lowers a level or lifts a gate; a Team that needs another sequence ships its own skill. When several
playbooks match, all apply, and on conflict the agent applies the more cautious and says so. `workflows/*.md` are indexes,
never prompts.

**Why**: the mechanism already carried ten playbooks and is covered by eval cases. No code reads the section: the model
does, after activating the playbook, so its form is checked by tests and its effect measured by evals.

**Consequences**: `tests/test_evals_and_playbooks.py` checks that the five commands carry the sentence, that no command names
a domain, and that the domain playbooks have the section. `architecture-decision` has no section and is activated by the
task alone. Following an extension is never promised.

**Considered**: `### /command` sub-headings (would rewrite every playbook for no gain); separate workflow files with
insertion points (would split each playbook from its steps and add no deterministic execution).
