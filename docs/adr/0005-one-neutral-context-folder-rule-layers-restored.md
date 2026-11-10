---
status: accepted
since: 0.31.0 and 0.39.0 (reconstructed from the CHANGELOG)
---
# One neutral folder for the context layers; rule layers are restored, the personal layer never rewritten

The context layers (`00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` or the Team's own, and the personal `USER.md`, ADR 0024)
live in `~/.ai-kit/context/`, whatever CLIs are installed. Claude Code and agy import them from there; Gemini CLI and Codex
get a copy, refreshed by every activation (`sync`, `sync --offline`, `team use`, `rollback`). A rule layer edited by hand is
put back at the next activation and the edited copy kept in `~/.ai-kit/backups/`; `USER.md` is personal and the engine never
rewrites it.

**Why**: the rule layers are company and team rules, not settings. Keeping them in one CLI's folder puzzled people who never
used that CLI.

**Considered**: stopping the activation on an edited rule layer, as for any other managed file. Rejected: it blocked every
change over an edit the person is not meant to make there; a personal rule belongs in `USER.md` or the repo's `AGENTS.md`.
