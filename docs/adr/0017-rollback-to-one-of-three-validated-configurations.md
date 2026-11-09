---
status: accepted, amended: lock.toml keeps one `[previous]` configuration, not a history of three validated entries; there is no `rollback --list` or `--to`
since: 4.0.0
---
# Rollback re-activates the previous Core and Team configuration; lock.toml is written in the activation's transaction

`~/.ai-kit/lock.toml` is authoritative. Besides the active configuration (Core and Team: URL, tag, tag object, commit, tree
digest) it keeps the previous one, `[previous]`, replaced whenever an activation changes the sources. `ai-kit rollback`
re-activates `[previous]` through the same path as `sync`, without network: it re-reads the current `managed.toml`,
re-checks each origin (an origin forbidden since is not re-activated), extracts the trees from the cached repositories,
and puts `user.active_team` back in line. Being an activation, it pushes the configuration it leaves into `[previous]`, so
a second `rollback` comes back. The caches keep the objects of every tag `lock.toml` cites.

During an activation, the backup manifest is written first with `status = pending`; `state.json`, `lock.toml` and
`aikit.toml` are among the writes of the same transaction, so they are backed up and restored with the CLIs' files; the
manifest becomes `done` last. A `pending` manifest at the next start restores that backup before anything else.

**Why**: the person needs a way back to the last configuration that worked, without network. Writing `lock.toml` after the
transaction would leave a new lock beside restored files after a machine stop.

**Consequences**: a managed file edited by hand blocks `rollback`, as any activation, and the command names it. Rolling back
does not undo `managed.toml`, which always applies. The engine itself is out of scope (a new ZIP or the launcher). Promise:
nothing changes when an error occurs before the writes; everything is restored on error or Ctrl+C; a machine stop is
recovered at the next start.

**Considered**: a history of three validated configurations with `--list` and `--to` (designed, not built: a single previous
entry covers the common case); keeping extracted trees per generation (digests already verify each extraction).
