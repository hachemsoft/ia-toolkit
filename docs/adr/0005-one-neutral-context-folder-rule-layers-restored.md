---
status: accepted, amended: the layers are `00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` and the personal `USER.md` (ADR 0024); copies are refreshed by every activation (`ai-kit sync --offline`)
since: 0.31.0 and 0.39.0 (reconstructed from the CHANGELOG)
---
# One neutral folder for the context layers; rule layers are restored, the personal layer never rewritten

The four context layers (`00_KIT.md`, `10_COMPANY.md`, `20_<TEAM>.md`, `30_USER.md`) live in `~/.ai-kit/context/`, whatever CLIs are installed: Claude Code and agy import them from there, Gemini CLI and Codex get a copy at each `update`. Before 0.39 they sat in a CLI's own folder when that CLI was chosen, which puzzled people who never used it. At `update`, a rule layer (00, 10, 20) edited by hand is put back and the edited copy kept in the backup, because these are company and team rules, not settings; `30_USER.md` is personal and is never rewritten.

**Considered**: stopping `update` on an edited rule layer, as for any other managed file (the behaviour until 0.30). Rejected: it blocked every update over an edit the person is not meant to make there; the right place for a personal rule is `30_USER.md` or the repo's `AGENTS.md`.
