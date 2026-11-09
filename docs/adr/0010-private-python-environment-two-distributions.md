---
status: accepted, amended: the package holds only the engine; content comes from a Core Git repository (`ai-kit sync`, ADR 0013 and 0016), and the release ZIP ships the Core as a git bundle
since: 0.34.0, completed in 0.46.0 (reconstructed from the CHANGELOG)
---
# A private Python environment and two distributions, with no administrator rights

A launcher finds a Python, creates `~/.ai-kit/runtime/venv` and installs the kit there: no activation, no change to the global Python or to the machine PATH, no administrator rights. Two distributions: a git clone by default (`update` fetches, reinstalls, reapplies) and a release ZIP that carries the kit's wheel and its libraries' wheels and installs with `--no-index`, for workstations without git or a package index. The `ai-kit` command goes on the person's own PATH only. Workstations without admin rights and behind restricted networks are the normal case, not the exception.

**Considered**: a global or per-user tool install through a package manager (proposed to developers until 0.33). Rejected: it created a second copy that shadowed the installed one, and it required a package index the workstation did not always reach.
