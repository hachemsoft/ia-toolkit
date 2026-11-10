---
status: accepted
since: 4.0.0
---
# Frictions stay in a local log; housekeeping runs at session start; publication is approved in a terminal

Capture: `/friction`, and the agent when `[frictions] capture` is `propose` (offers) or `auto` (logs itself), append one line
to `~/.ai-kit/frictions.jsonl` (mode 0600) through the script the kit installs (`~/.ai-kit/bin/friction.py`). One function,
`housekeep`, purges entries older than the retention (30 days, `managed.toml` `frictions.retention_days`) and counts those
waiting for publication. It runs in the `whats-new` session hook and in `ai-kit status`; it reads only `frictions.jsonl`,
never the CLIs' logs or the network, and rewrites the file under a lock with an atomic replace. Each entry carries a
fingerprint (category, command, component, text without digits), so the same friction told twice is one issue with its count.

Publication: `approval` (default), `auto` or `disabled`, set in `managed.toml` `[frictions]`. Without a tracker
(`[frictions.tracker]` in `managed.toml`) nothing is sent. With `approval`, the session hook only tells the agent how many
frictions wait, and the person sends them with `ai-kit friction --publish` in a terminal; the agent's shell is refused that
command. With `auto`, a friction is sent when logged. Either way the person's own `glab` or `gh` creates the issue; emails,
home paths and internal hosts are redacted. A person keeps theirs local with `[frictions] publication = "disabled"`.

**Why**: session start is the only event the kit writes on all four CLIs, and the local file is small, so housekeeping costs
milliseconds; mining the CLIs' logs at every start would be slow and would read prompts in the background. Approval by the
agent in chat would not be the person's consent.

**Consequences**: signals from the CLIs' logs stay in `ai-kit usage`, run by the person. A CHANGELOG line citing
`(frictions: <id>)` lets `usage` tell each person which of theirs were fixed.

**Considered**: analysing the previous session's logs at start (cost, false positives); an end-of-session hook (not on all
four CLIs, missed on abrupt exit); a per-tool-call hook (cost on every call).
