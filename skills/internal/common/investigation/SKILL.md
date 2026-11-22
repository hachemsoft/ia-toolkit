---
name: investigation
description: Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent.
metadata:
  aikit-default: "true"
  aikit-version: "1.1.0"
  aikit-origin: "upstream"
  aikit-license: "skills/LICENSE-UPSTREAM-MIT"
  aikit-summary: "Research in five steps: criteria, primary sources, options compared, challenged, one recommendation; recorded in a Markdown file in the repo."
  aikit-category: "tool"
  aikit-needs-agents: "true"
---

Research a question in five steps and record it in the repo. Spin up a **background agent** for the reading when sub-agents are available, so you keep working while it reads; otherwise do it inline.

1. **Frame**: restate the question in one line and name the criteria an answer is judged on (what matters here: cost, risk, effort, fit with the repo). An unclear question: ask once before reading.
2. **Search primary sources** (official docs for the version in use, source code, specs, first-party APIs), not a secondary write-up of them. Follow every claim back to the source that owns it; separate what a source says from what you infer.
3. **Compare the options** against the criteria, in a table when there are more than two. Leave out an option nobody would choose.
4. **Challenge** the comparison before concluding: look for a counter-example, and name the assumptions that change the result. Hand this step to the `ai-kit-doubter` agent when it is installed; otherwise do it yourself, as a separate pass.
5. **Recommend** one option, and name one ruled-out alternative with the reason it loses.

A fact to look up, with one answer and no options to weigh, needs steps 1 and 2 only.

Write the findings to a single Markdown file, citing each claim's source: the question and its criteria, the comparison, what the challenge changed, the recommendation and the ruled-out alternative, what stays unknown. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it somewhere sensible and say where.
