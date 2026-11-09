---
status: accepted, amended: `protected` only stops a Team from replacing a Core resource; `disabled_*` does not check it, and no Core resource carries `aikit-protected` today
since: 4.0.0
---
# `protected` only guards the files AI Kit manages

A Core skill or agent marked `aikit-protected: "true"` cannot be replaced by a Team resource of the same name: the overlay
refuses it at `sync` or `team use` (`installer/sync.py`). Against a project resource of the same name, read natively by the
CLI, AI Kit can impose nothing: what happens depends on the CLI (a repo skill replaces the kit's in one, is ignored in
another, both are listed in a third; [CLI matrix](../cli/matrice.md)). `doctor`, run from a repo, lists those clashes. On
Claude Code the kit's skills keep the `ai-kit-` prefix by default.

**Why**: an organization needs some Core behaviour that a Team cannot silently swap, but the kit has no hold on what a CLI
loads from a repository. The prefix avoids collisions with skills shipped with a CLI and with personal skills.

**Consequences**: `protected` is never presented as a guarantee of invocation or as protection against a project's
instructions; repo content is reviewed through `CODEOWNERS` on `.agents/` and `AGENTS.md`.
