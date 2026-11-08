---
name: investigation
description: Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent.
metadata:
  aikit-version: "1.0.0"
  aikit-origin: "upstream"
  aikit-license: "skills/LICENSE-UPSTREAM-MIT"
  aikit-summary: "Research on primary sources, recorded in a Markdown file in the repo, delegated to a background agent."
  aikit-category: "tool"
  aikit-tier: "optional"
  aikit-needs-agents: "true"
---

Spin up a **background agent** to do the research, so you keep working while it reads.

Its job:

1. Investigate the question against **primary sources** (official docs, source code, specs, first-party APIs), not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Write the findings to a single Markdown file, citing each claim's source.
3. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it somewhere sensible and say where.
