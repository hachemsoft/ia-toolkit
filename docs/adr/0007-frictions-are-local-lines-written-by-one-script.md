---
status: accepted
since: 0.14.0, hardened in 0.16.0 and 0.41.0 (reconstructed from the CHANGELOG)
---
# A friction is one local line, written by one script, and nothing is sent

A friction (something that slowed the person down or made them work around the kit) is one JSON line in `~/.ai-kit/frictions.jsonl`, written by a single script that both the `/friction` command and `ai-kit friction` run: the sentence comes through standard input so the shell expands nothing, secrets are redacted, the file is readable by the person only, and each line gets a stable short id. Nothing leaves the workstation; `usage --json` exports the lines only when the person chooses to share, and the team aggregates the shared files. When a version fixes a friction, the CHANGELOG cites its id and `usage` tells the person.

**Considered**: sending frictions to a tracker or a telemetry endpoint. Rejected: it needs a network and a consent the kit cannot assume, and a feedback loop people distrust gets no feedback.
