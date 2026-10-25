---
name: retro
description: "Retrospective of this session: improve the agent's environment, not the code"
category: tool
skills: [retro]
order: 140
---

Activate the retro skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Input: {{args}} (optional: a session log path when the session was cleared).

Look back over this session. Propose changes to the agent's environment, never to the code: lines for AGENTS.md (commands, conventions, things the agent got wrong), checks to automate, review standards for REVIEW.md, skills or playbooks to add or trim, kit commands that were missing or got in the way. Mechanical mistakes become deterministic checks; judgement calls become written standards. Deliver the proposals as a short list the user can accept one by one. For each proposal that concerns the kit itself rather than this repo (a kit command, skill, playbook, guardrail or page of documentation that got in the way), offer to record it with /friction so it reaches the team's usage review.
