---
name: friction
description: "Record a friction met in this session, one line, locally, for the team's usage review"
category: tool
skills: []
order: 115
---

Input: {{args}} (optional: the friction in the user's own words).

Record one friction: something that slowed the person down, surprised them or made them work around the kit (a command that did not do what its description says, a skill that fired for nothing, a guardrail in the way, a wrong page of documentation, a missing tool, an authentication problem). If the input is empty, ask for it in one sentence and wait. Pick one category: command, skill, guardrail, rule (the agent went against a rule written in AGENTS.md, the kit context or a playbook), docs, tool, auth, other. Then run the script the kit installed, never write the file yourself:

Pass the sentence on standard input, never on the command line, so that the shell expands nothing in it (no `$(...)`, no backticks). One sentence, no secret, no prompt text, no repository path. On macOS or Linux:

python3 ~/.ai-kit/bin/friction.py --category <category> --command <the kit command in use, or none> --cli <gemini, agy or codex: the CLI you are> <<'FRICTION'
<the sentence>
FRICTION

On Windows (PowerShell), the same with a literal here-string:

@'
<the sentence>
'@ | py -3 $HOME/.ai-kit/bin/friction.py --category <category> --command <command or none> --cli <gemini, agy or codex>

The script adds the kit version, profile and operating system itself. The line lands in ~/.ai-kit/frictions.jsonl on this machine only; nothing is sent anywhere. Confirm in one line what was recorded, then go back to the work in progress.
