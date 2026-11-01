---
status: accepted
since: 0.8.0 (reconstructed from the CHANGELOG)
---
# Ship a broad core, then slim it by measured usage, decided by people

Nobody knows up front which skills a role will use, and every installed skill costs context on every prompt. The kit therefore ships a broad core per profile and corrects that bet with the usage review: `usage` counts, locally and without a model, the commands typed, skills activated and agents called over a window, recommends nothing below a data threshold, and lists candidates to move to optional. The review proposes; people decide; nothing is removed automatically, and domain playbooks are never candidates because they activate on the nature of a task, not on frequency.

**Considered**: deciding the core of each role up front. Rejected: a guess, and one that charges a context tax on every message while it is wrong.
