---
name: explain
description: "Map a code area or data flow in glossary terms, or re-pitch the last answer simply"
category: tool
skills: [zoom-out, wait-what]
order: 130
---

Answer in the user's language (where wait-what asks for Simplified Technical English, keep its rules of short sentences and one idea per sentence, in the user's language). If the input names a code area, module, model or data flow, activate the zoom-out skill (if the skill tool is unavailable here, do not look for an agent of that name: follow these instructions directly) and give a map one level up: the relevant modules or models, their callers and dependencies, in the vocabulary of GLOSSARY.md. If the input is empty or says the last answer was unclear, activate the wait-what skill and re-pitch the last message with context, in plain language, using the glossary's terms.

Input: {{args}}

Read-only: use the file-reading and search tools only; never run shell commands, builds or queries for this command.

When the explanation is worth keeping, offer to save it as a reference sheet under docs/learn/<topic-slug>/reference/.
