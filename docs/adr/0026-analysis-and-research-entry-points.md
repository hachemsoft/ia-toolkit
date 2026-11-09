---
status: accepted
since: 4.0.0
---
# Analysis and Research are two light Core workflows; Research enters by /research, Analysis by /explain

The Core provides two workflows besides the SDLC, never required for a small question.

- **Research**: frame the question and the criteria, search primary sources, compare options, challenge (counter-examples,
  assumptions that change the result), recommend one option and one ruled-out alternative, recorded in the repo. Entry:
  `/research`, a Core default. Skill: `investigation` (no skill may share a command's name); sub-agents are optional; the
  doubter agent for the challenge step when installed.
- **Analysis**: frame in one line, explore the project's sources, verify each claim (observed, with the file or read-only
  command, or assumed), report verdict, evidence and unknowns. Entry: `/explain`, whose description is "Explain or analyse a
  code area, a data flow or a question about the project, with evidence": a question activates the `analysis` skill; a code
  area keeps `zoom-out`; an empty input or an unclear last answer keeps `wait-what`. repo-investigator and verifier when
  installed.
- `/guide` routes to both. `workflows/analysis.md` and `workflows/research.md` are indexes written by `scripts/workflows.py`,
  never prompts.

**Why**: an explicit entry point is needed, since activation cannot rely on a skill firing on its own, and one already
existed for each. A new `/analyze` would make five overlapping entries (explain, analyze, research, learn, diagnose).

**Consequences**: one new skill (`analysis`); `investigation` changed content, not name; eval case `explain-uses-glossary`
keeps `/explain` honest on a code area.

**Considered**: `/analyze` as a new command (overlap); routing by `/guide` only (`/guide` proposes, it does not run the
workflow); renaming `investigation` to `research` (skill and command names would collide).
