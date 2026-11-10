---
name: friction
description: "Record a friction met in this session, one line, locally, for the team's usage review"
category: tool
skills: []
order: 115
---

Input: {{args}} (optional: the friction in the user's own words).

Record one friction: something that slowed the person down, surprised them or made them work around the kit (a command that did not do what its description says, a skill that fired for nothing, a guardrail in the way, a wrong page of documentation, a missing tool, an authentication problem). If the input is empty, ask for it in one sentence and wait. Pick one category: command, skill, guardrail, rule (the agent went against a rule written in AGENTS.md, the kit context or a playbook), docs, tool, auth, other. Then run the script the kit installed, never write the file yourself:

Pass the sentence on standard input, never on the command line, so that the shell expands nothing in it (no `$(...)`, no backticks). One sentence on one line (never a line that is only the end marker), no secret, no prompt text, no repository path. On macOS or Linux:

python3 ~/.ai-kit/bin/friction.py --category <category> --command <the kit command in use, or none> --cli <gemini, agy, codex or claude: the CLI you are> --source person <<'AI_KIT_FRICTION_END'
<the sentence, on one line>
AI_KIT_FRICTION_END

On Windows (PowerShell), the same with a literal here-string:

@'
<the sentence>
'@ | py -3 $HOME/.ai-kit/bin/friction.py --category <category> --command <command or none> --cli <gemini, agy, codex or claude> --source person

`--source person` when the person asked for this friction; `--source agent` when you log it on your own, as the Frictions rule of your context may ask.

The script adds the kit version, team and operating system itself. The line lands in ~/.ai-kit/frictions.jsonl on this machine; nothing is sent, unless the organization set a friction tracker: then the script itself creates an issue with the person's own glab or gh and prints its URL (a failure keeps the friction local). Repeat the script's output in one line (what was recorded, the issue URL if any), then go back to the work in progress.
