# News

Announcements the kit shows once, at session start, to the people they are aimed at: a new skill, a training, a tip.
One section per entry, `## <YYYY-MM-DD> <id> : <title>`, then optional lines `profiles: data-analyst, data-developer`
(ids of `profiles/`), `teams: data` (teams of `organization.toml`) and `until: YYYY-MM-DD` (not shown after that day),
then the text. Without `profiles` or `teams`, an entry goes to everyone. An organization writes its own entries in its
copy of this repository; the public repository keeps only generic ones. `python3 scripts/check_news.py` checks the file
(the CI runs it). How it reaches people: [docs/hooks.md](docs/hooks.md#whats-new).

## 2026-11-08 ai-kit-2-1 : AI Kit 2.1: Core and Teams from Git

Your organization can now publish the kit content as a Core Git repository and Team repositories: `ai-kit sync`, `ai-kit team use <name>`, `ai-kit rollback`, `ai-kit status`. Without them, nothing changes.

## 2026-11-08 ai-kit-2-0 : AI Kit 2.0 needs Python 3.11

AI Kit 2.0 starts the V2 structure: settings IT can impose (`managed.toml`), frictions sent only with your approval.
It needs Python 3.11 or newer; on an older Python, keep AI Kit 0.52 and ask IT for Python 3.11.

## 2026-11-08 security-0-51-1 : Security fixes in 0.51.1

Version 0.51.1 closes ways an agent could change what the kit installs next or run a program at session start. Update
when the agent proposes it (`ai-kit update`); nothing else changes.

## 2026-11-02 session-news : The kit now tells you what is new at session start

Once per version and per announcement, the agent says in its first reply what changed and whether a newer kit version
is available; the update stays yours to run (`ai-kit update`). `ai-kit news --list` shows what was announced.
