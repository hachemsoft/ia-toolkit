---
name: zoom-out
description: "Tell the agent to zoom out and give broader context or a higher-level perspective. Use when you're unfamiliar with a section of code or need to understand how it fits into the bigger picture. Use when the user types /explain or explicitly asks for this step; do not activate on your own for unrelated requests."
metadata:
  aikit-default: "true"
  aikit-version: "1.1.0"
  aikit-origin: "upstream"
  aikit-license: "skills/LICENSE-UPSTREAM-MIT"
  aikit-summary: "Step back: wider context and big picture."
  aikit-category: "tool"
---

I don't know this area of code well. Go up a layer of abstraction. Give me a map of all the relevant modules and callers, using the project's domain glossary vocabulary.
