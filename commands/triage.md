---
name: triage
description: "Maintain: move incoming issues through triage until they are agent-ready"
default: false
category: workflow
stage: Maintain
skills: [ticket-sorting]
artifact: "agent-ready issues"
order: 100
---

Activate the ticket-sorting skill (if this skill is not installed here, follow the instructions below directly).

Input: {{args}} (optional: an issue id or a filter).

Use the tracker and label vocabulary configured by setup-workflow (docs/agents/issue-tracker.md). Only triage issues you did not create; tickets produced by to-tickets are already agent-ready.
