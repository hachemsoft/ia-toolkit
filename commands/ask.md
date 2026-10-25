---
name: ask
description: "Write a questionnaire for the person who holds the missing information"
category: tool
skills: [to-questionnaire]
order: 150
---

Activate the to-questionnaire skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly).

Input: {{args}} (who it goes to, and what decision it unblocks).

Interview the user about the send, not the subject: recipient, what is needed back, by when. Produce the questionnaire as a file the user can send; one idea per question, an answer stub under each. Say how the answers feed back: into /intent, into GLOSSARY.md, or into spec.md.
