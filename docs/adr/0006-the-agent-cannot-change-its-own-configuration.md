---
status: accepted
since: 0.23.0, widened in 0.31.0 (reconstructed from the CHANGELOG)
---
# The agent cannot change its own configuration: a guardrail, not only a sentence

The `protected-paths` guardrail is on by default and refuses, from the CLI's write tools and from shell commands alike, any write to the kit's settings, state, scripts and rule layers, to the CLIs' settings and `.env` files, and to a repo's declared protected paths; reading stays allowed. The kit context also tells the agent to say what to change rather than change it. A text instruction alone is not a control: an honest mistake or an instruction slipped into a file the agent reads could switch a guardrail off or change a model, and nobody would notice.

**Consequences**: the kit's own scripts live in a protected folder, so running them (not writing them) has to be allowed explicitly; the organization can lock a guardrail so that a personal setting cannot turn it off.
