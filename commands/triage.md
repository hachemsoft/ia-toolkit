---
name: triage
description: "Maintain: move incoming issues through triage until they are agent-ready"
category: workflow
stage: Maintain
skills: [triage]
artifact: "agent-ready issues"
order: 100
---

Activate the triage skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Input: {{args}} (optional: an issue id or a filter).

Use the tracker and label vocabulary configured by setup-workflow (docs/agents/issue-tracker.md). Only triage issues you did not create; tickets produced by to-tickets are already agent-ready.
