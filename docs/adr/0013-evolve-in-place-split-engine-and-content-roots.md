---
status: accepted
since: 4.0.0
---
# One engine, a separate content root: the engine applies whatever Core and Team content is active

The engine (the `installer` package, installed as `ai_kit`, with `runtime/`, `schemas/` and `templates/`) is distinct from
the content it applies (skills, agents, commands, context, workflows). The engine's own files are found from its package
root (`ROOT`); the content from `content_root()`, which `content_from(path)` points at the active tree for the length of a
command: the Core extracted at its locked tag, with the active Team overlaid on it, or the content of the folder the
engine runs from when no Core source is set. The installed package holds only the engine; the release ZIP ships the Core
as a git bundle (`core/ai-kit-core.bundle`) that the first `init` activates offline.

**Why**: the transactional core and the adapters already did their job; what had to change was where content comes from.
Two explicit roots let content come from Git (ADR 0016) without touching the adapters, and keep a single engine that a
golden snapshot test (`tests/snapshot.py`) proves byte for byte.

**Consequences**: every module reads content through `content_root()`, never through `ROOT`; the snapshot changes only for
a contract changed on purpose, its diff reviewed in the same merge request. New modules (`config`, `sources`, `resolve`,
`sync`) stay small; `installer/cli.py` stays under 800 lines.

**Considered**: a new package written beside the old one. Rejected: double maintenance and the loss of the test net.
