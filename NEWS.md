# News

Announcements the kit shows once, at session start, to the people they are aimed at: a new skill, a training, a tip.
One section per entry, `## <YYYY-MM-DD> <id> : <title>`, then optional lines `profiles: data-analyst, data-developer`
(ids of `profiles/`), `teams: data` (teams of `organization.toml`) and `until: YYYY-MM-DD` (not shown after that day),
then the text. Without `profiles` or `teams`, an entry goes to everyone. An organization writes its own entries in its
copy of this repository; the public repository keeps only generic ones. `python3 scripts/check_news.py` checks the file
(the CI runs it). How it reaches people: [docs/hooks.md](docs/hooks.md#whats-new).

## 2026-11-02 session-news : The kit now tells you what is new at session start

Once per version and per announcement, the agent says in its first reply what changed and whether a newer kit version
is available; the update stays yours to run (`ai-kit update`). `ai-kit news --list` shows what was announced.
