---
name: retro
description: "Retrospective of this session: improve the agent's environment, not the code"
category: tool
skills: [retrospective]
order: 140
---

Activate the retrospective skill (if this skill is not installed here, follow the instructions below directly).

Input: {{args}} (optional: a session log path when the session was cleared).

Look back over this session. Propose changes to this repository's agent environment, never to the code, and never outside this repository: lines for AGENTS.md (commands, conventions, things the agent got wrong), checks to automate, review standards for REVIEW.md, the repo's own skills or agents (.agents/). Never write the kit's files, a Core or Team repository, your personal settings or another repo. Mechanical mistakes become deterministic checks; judgement calls become written standards. Rank the candidates, then propose one change at a time: the most valuable one first, as the smallest change that solves it, tied to a concrete moment of this session (what happened, when). Write it only after the person says yes, then offer the next one; stop when the person stops or nothing is left. A line for "Things the agent gets wrong" takes the form `rule (since YYYY-MM: what happened)`, with the current month. A rule already written that the agent broke again in this session is a candidate for a check rather than a stronger sentence. What concerns the kit itself rather than this repo (a kit command, skill, playbook, guardrail, Core or Team resource, or page of documentation that got in the way) is not a proposal here: offer to record it with /friction, so it reaches the people who maintain it.
