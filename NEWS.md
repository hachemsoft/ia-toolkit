# News

Announcements the kit shows once, at session start, to the people they are aimed at: a new skill, a training, a tip.
One section per entry, `## <YYYY-MM-DD> <id> : <title>`, then optional lines `teams: data`
(the active Team) and `until: YYYY-MM-DD` (not shown after that day),
then the text. Without `teams`, an entry goes to everyone. An organization writes its own entries in its
copy of this repository; the public repository keeps only generic ones. `python3 scripts/check_news.py` checks the file
(the CI runs it). How it reaches people: [docs/hooks.md](docs/hooks.md#whats-new).

## 2026-11-09 ai-kit-4-0 : AI Kit 4.0: one base for everyone, your team adds the rest

The kit installs the same base for everyone; your team adds its own (`ai-kit team use <name>`), and you adjust yours in
`~/.ai-kit/aikit.toml`. Your personal context is now `USER.md` (`ai-kit user edit`). Commands: `ai-kit sync` to update,
`ai-kit rollback` to go back, `ai-kit status` to see what is active.
