---
status: accepted
since: 0.8.0 (reconstructed from the CHANGELOG)
---
# Ship a broad Core default, then slim it by measured usage, decided by people

Nobody knows up front which skills a team will use, and every installed skill costs context on every prompt. The Core
therefore ships a broad default selection, which Teams and people extend (ADR 0018), and corrects that bet with the usage
review: `ai-kit usage` counts, locally and without a model, the commands typed, skills activated and agents called over a
window, recommends nothing below a data threshold, and lists default skills never activated nor required by a used command
as candidates to remove from the default. The review proposes; people decide; nothing is removed automatically, and domain
playbooks are never candidates because they activate on the nature of a task, not on frequency.

**Considered**: deciding each team's selection up front. Rejected: a guess, and one that charges a context tax on every
message while it is wrong.
