---
status: accepted
since: 4.0.0
---
# Commands chain only skills the model can invoke; user-only skills are never a command's target

A command names the skills it chains, in its `skills:` list and in its "Activate the X skill" lines. Each must be invocable
by the model. A skill marked `disable-model-invocation: true` (user-only) is never a command's target.

- `/build` chains `tdd`, then `code-review`, directly; `implement` stays user-only, for direct use.
- `/intent` chains `grilling` and `domain-modeling` directly; `grill-with-docs` stays user-only.
- Skills a command carries (`to-spec`, `teach`, `retrospective`, `zoom-out`, `wait-what`, `wayfinder`, `ticket-sorting`,
  `to-questionnaire`, `improve-codebase-architecture`, `handover`) are model-invocable, with a description that says to use
  them only on their command.
- The fallback in every command is "if this skill is not installed here, follow the instructions below directly".
- `tests/test_skill_dependencies.py` fails when a command chains a user-only skill; `ai-kit validate` refuses a command whose
  skill does not exist or that activates a skill it does not list.

**Why**: Claude Code hides user-only skills from the model and refuses them in its Skill tool with a message that forbids
replicating them; Codex omits them from the model's list. A command pointing at such a skill sends the model to something
it cannot see. Removing user-only from every orchestrator would expose `implement` and similar skills to automatic
activation outside the gates of their commands.

**Consequences**: Gemini CLI and agy have no user-only field, so user-only skills may activate on their own there; `doctor`
shows it. Vendor behaviour can change: it is re-checked when an adapter's `VERIFIED` version is raised.

**Considered**: inlining thin skills into their command at render time (dropped: model-invocable skills with a guarded
description were simpler); referencing the skill file by path from the command (reads outside the working folder are
refused in print mode).
