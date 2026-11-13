---
status: accepted
since: 0.23.0, widened in 0.31.0 (reconstructed from the CHANGELOG); title and scope narrowed to what the code does
---
# A guardrail makes it harder for the agent to change its own configuration by mistake

The `protected-paths` guardrail is on by default. It refuses the usual writes to the kit's settings, state, scripts and rule layers and to the CLIs' settings and `.env` files, from the CLI's write tools and from shell commands; a repo's declared protected paths are refused from write tools and, since 4.6.0, from a shell command that names the file and changes or deletes it. Reading stays allowed. The kit context also tells the agent to say what to change rather than change it. A text instruction alone is not a control: an honest mistake could switch a guardrail off or change a model, and nobody would notice. This does not stop an agent or a person determined to change the configuration: the limits are in [guardrails](../hooks.md#limits).

**Consequences**: the kit's own scripts live in a protected folder, so running them (not writing them) has to be allowed explicitly; the organization can lock a guardrail so that a personal setting cannot turn it off, which is a default and not a lock either.
