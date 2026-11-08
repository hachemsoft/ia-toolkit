---
name: explain
description: "Explain or analyse a code area, a data flow or a question about the project, with evidence; or re-pitch the last answer simply"
category: tool
skills: [zoom-out, wait-what, analysis]
order: 130
---

Answer in the user's language (where wait-what asks for Simplified Technical English, keep its rules of short sentences and one idea per sentence, in the user's language). If the input names a code area, module, model or data flow, activate the zoom-out skill (if this skill is not installed here, follow these instructions directly) and give a map one level up: the relevant modules or models, their callers and dependencies, in the vocabulary of GLOSSARY.md. If the input is a question about the project (why, how, is it true that), activate the analysis skill (if it is not installed here, follow these steps directly: frame, explore, verify each claim, report verdict, evidence and unknowns). If the input is empty or says the last answer was unclear, activate the wait-what skill and re-pitch the last message with context, in plain language, using the glossary's terms.

Input: {{args}}

Read-only: use the file-reading and search tools; for a question, a command only if it changes nothing and costs nothing (git log, a test listing), named in the answer; never builds, deployments or queries.

When the explanation is worth keeping, offer to save it as a reference sheet under docs/learn/<topic-slug>/reference/.
