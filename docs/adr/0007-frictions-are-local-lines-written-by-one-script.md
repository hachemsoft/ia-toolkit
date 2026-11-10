---
status: accepted
since: 0.14.0, hardened in 0.16.0 and 0.41.0 (reconstructed from the CHANGELOG)
---
# A friction is one local line, written by one script

A friction (something that slowed the person down or made them work around the kit) is one JSON line in
`~/.ai-kit/frictions.jsonl`, written by a single script that both the `/friction` command and `ai-kit friction` run: the
sentence comes through standard input so the shell expands nothing, secrets are redacted, the file is readable by the
person only, and each line gets a stable short id. When a version fixes a friction, the CHANGELOG cites its id and `usage`
tells the person.

Nothing is sent unless IT sets a tracker in `managed.toml` `[frictions.tracker]`; publication, its approval in a terminal
and local housekeeping are decided in ADR 0023.

**Why**: a feedback loop people distrust gets no feedback; a local line needs no network and no consent the kit cannot
assume.

**Considered**: a telemetry endpoint. Rejected: a network dependency and a consent the kit cannot assume.
