# Analysis workflow

An index, never a prompt (ADR 0026). Entry: `/explain` with a question about the project; skill `analysis`; agents
repo-investigator and verifier when installed.

1. Frame the question in one line.
2. Explore the project's own sources.
3. Verify each claim: observed (file, line, read-only command) or assumed.
4. Report: verdict, evidence, unknowns.

A Team extends it through the "In the kit commands" section of its skills (`### /explain`).
