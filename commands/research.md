---
name: research
description: "Research a question against primary sources and record it in the repo"
category: tool
skills: [investigation]
order: 170
---

Activate the investigation skill (if this skill is not installed here, follow the instructions below directly).

Question: {{args}}

Research in five steps: frame the question and the criteria an answer is judged on; search primary sources only (official docs for the version in use, source code, specifications), cite every claim and separate facts from interpretation; compare the options against the criteria; challenge the comparison (a counter-example, the assumptions that change the result), with the ai-kit-doubter agent when it is installed, yourself otherwise; recommend one option and name one ruled-out alternative with why it loses. A fact to look up, with no options to weigh: frame, search, record. Delegate the reading to a background agent when sub-agents are available; otherwise do it inline. Write docs/research/<slug>.md unless the repo has another convention, and say where it is.
