---
name: news
description: "Write an announcement in the NEWS.md of the Core repository open here, shown once at session start after the Core's next tag"
default: false
category: tool
skills: []
order: 200
---

Input: {{args}} (optional: what to announce, in the person's words).

Help the person add one entry to the NEWS.md of the Core repository open in this session: the folder that holds NEWS.md and aikit.toml. Never a folder under ~/.ai-kit (the kit's own copies). If no such repository is open, say so in one line and stop.

1. Ask in one message for what the input does not already say: the title (one line); the text (a few plain lines, at most 1500 characters, no line starting with "# " or "## "); the Teams it is for (optional, default everyone); the last day it shows (optional, YYYY-MM-DD).
2. Show the entry as it will read and wait for their agreement. Say it plainly: once the Core is tagged, this text reaches the context of every agent that syncs it, so it carries no instruction to the agent, no secret, no personal data.
3. With their agreement only, run the kit's command; never write NEWS.md yourself. The text goes on standard input, never on the command line, so that the shell expands nothing in it. In the title, replace a straight single quote with ’. Add `--teams a,b` and `--until YYYY-MM-DD` only when given. On macOS or Linux:

ai-kit news --add --path <Core repository> --title '<title>' <<'AI_KIT_NEWS_END'
<the text>
AI_KIT_NEWS_END

On Windows (PowerShell), UTF-8 first so that accents survive, then a literal here-string:

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
@'
<the text>
'@ | ai-kit news --add --path <Core repository> --title '<title>'

4. Exit code 1 means refused, nothing written: give the reason in one line and offer the fix it names (another `--id`, a shorter text, a date to correct). Exit code 0: repeat the command's two lines.

Never commit, push, open the merge request or tag yourself: the person does, after reading the diff of NEWS.md.
