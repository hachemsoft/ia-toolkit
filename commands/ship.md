---
name: ship
description: "Deploy: write the merge request body: visual summary, evidence, merge danger"
category: workflow
stage: Deploy
skills: [mr]
artifact: "MR description"
order: 60
---

State in one line the level of ceremony this change had (tweak, small feature, large change, production) so the reviewer knows what evidence to expect.
Activate the mr skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Stage: Deploy. Goal: a merge request description that reads without opening the diff.

Input: {{args}} (optional: ticket link, base ref, notes).

Monorepo: when the change reaches areas with their own AGENTS.md, list them in the MR description under "Areas touched", with the owners from CODEOWNERS when the file exists, so they are asked to review.

Before writing, read the diff since the base and the latest verification output. Sections: Summary (the smallest visual that shows the change), Evidence (before/after, real command output or test names, never a check you did not run), Merge Danger (one-way or two-way door, blast radius), plus a link to spec.md or the ticket when they exist. Follow the repo's title convention. Deliver the text; do not push or create the MR unless the user asks.
