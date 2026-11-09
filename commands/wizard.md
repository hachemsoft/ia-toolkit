---
name: wizard
description: "Generate an interactive bash wizard for steps only a human can do"
default: false
category: tool
skills: [manual-steps]
order: 180
---

Activate the manual-steps skill (if this skill is not installed here, follow the instructions below directly).

Procedure: {{args}}

Only for steps a human must perform (credentials, dashboards, approvals, one-off migrations). If the agent could do the step itself, say so instead of generating a wizard.
