---
name: architecture-decision
description: "Investigate and document an architecture decision (ADR): options, criteria, consequences, reversibility. Triggers: which architecture to choose, should we split this service, choose a database or a framework, write an ADR, review this design, is this decision reversible."
---

# architecture-decision

Start from the problem, not the solution: constraints, required qualities (latency, volume, availability, cost, security, the team's capacity to maintain it) and what is out of scope. Read the repo's existing ADRs and the current architecture before proposing anything; a decision that contradicts another one says so and explicitly proposes to supersede it. If the need is unclear, clarify it first with the grilling skill. Lay out at least two real options, including "change nothing" when it holds, and compare them on the same criteria, with the available evidence (measurements, documentation, a throwaway prototype with the prototype skill). For each option: consequences, exit cost, what becomes harder. Classify the decision: cheap to reverse (decide quickly) or hard to undo (take the time, get it reviewed). Write the ADR in the repo's folder and format (otherwise `docs/adr/NNNN-title.md`: context, decision, rejected options, consequences, status) and ask for confirmation before writing. Keep the domain vocabulary with the domain-modeling skill.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "There is only one serious option" | Then comparing it to "change nothing" takes five lines; otherwise you do not know what you are buying. |
| "We'll document the decision later" | Later, the reasons are forgotten and only the decision remains; the short ADR gets written now. |
| "Everyone uses this technology" | The question is what it costs here, with this team and these constraints. |
| "It's reversible anyway" | Say what going back would cost: migrated data, published contracts, skills to acquire. |
