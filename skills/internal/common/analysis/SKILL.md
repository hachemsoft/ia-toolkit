---
name: analysis
description: "Analyse a question about the project with evidence: frame it, explore the sources, verify each claim, report a verdict. Triggers: analyse, why does, how does, is it true that, what happens when."
metadata:
  aikit-default: "true"
  aikit-version: "1.0.0"
  aikit-origin: "internal"
  aikit-summary: "Analyse a question about the project: explore, verify each claim, report verdict, evidence and unknowns."
  aikit-category: "workflow"
---

# analysis

A question about this project gets an answer backed by what you read, not by what is usual elsewhere.

1. Frame it in one line: the question, and what would settle it. A small question gets a direct answer: skip to step 4.
2. Explore the project's own sources: code, configuration, models, tests, docs, its AGENTS.md and GLOSSARY.md. When a repo-investigator agent is available, give it the question and the paths; otherwise do it yourself.
3. Analyse, then verify each claim you will make: observed (cite the file and line, or the read-only command and its output) or assumed (say so, and what would confirm it). When a verifier agent is available and a check needs running, ask it; run nothing that changes a file or costs money.
4. Report: the verdict first, then the evidence, then what stays unknown and the one assumption that would change the verdict.

## In the kit commands

- `/explain`: a question about the project comes here; a code area or an empty input stays with zoom-out and wait-what.

## Forbidden

- An answer from memory when the repository can be read.
- A claim without its file or command, presented as verified.
- Changing a file, running a build, a deployment or a paid query to answer.
