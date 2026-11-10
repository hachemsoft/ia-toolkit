---
status: accepted
since: 0.34.0, completed in 0.46.0 (reconstructed from the CHANGELOG)
---
# A private Python environment and two distributions, with no administrator rights

A launcher finds a Python, creates `~/.ai-kit/runtime/venv` and installs the engine there: no activation, no change to the
global Python or to the machine PATH, no administrator rights. The package holds only the engine; the content comes from a
Core Git repository (ADR 0013 and 0016). Two distributions: a git clone, and a release ZIP that carries the engine's wheel,
its libraries' wheels (installed with `--no-index`) and the Core as `core/ai-kit-core.bundle`, so `init` works without
network or package index. The `ai-kit` command goes on the person's own PATH only.

**Why**: workstations without admin rights and behind restricted networks are the normal case, not the exception.

**Considered**: a global or per-user tool install through a package manager. Rejected: it created a second copy that
shadowed the installed one, and it required a package index the workstation did not always reach.
