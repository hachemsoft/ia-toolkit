---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
metadata:
  aikit-default: "true"
  aikit-version: "1.0.0"
  aikit-origin: "upstream"
  aikit-license: "skills/LICENSE-UPSTREAM-MIT"
  aikit-summary: "Challenge a plan, a decision or an idea through rounds of questions before implementing it."
  aikit-category: "workflow"
  aikit-tier: "core"
---

Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question, give its options and your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs>
- **A** - <option>: <what it implies>
- **B** - <option>: <what it implies>

➡️ <the option you recommend, and why in one line>

---

❓ **Q2** - **<question title>**: <question body>
- **A** - <option>: <what it implies>
- **B** - <option>: <what it implies>
- **C** - <option>: <what it implies>

➡️ <the option you recommend, and why in one line>
```

Every question offers at least two real options, each with what it implies, so the user can choose without asking you to rephrase; a question with a single possible answer is not a decision, state it as an assumption instead. Word each question so "yes" accepts your recommended answer.

Stay inside the scope the user set: the plan, or the step in progress. Ask only the decisions this step needs. A decision that can wait (hosting, access, operations, when the step is framing what to build) is not asked: list it under **Later** at the end of the round, one line each, and move on.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every in-scope branch of the design tree visited, nothing left silently assumed, the **Later** list handed over. Do not act on it until the user confirms you have reached a shared understanding.
