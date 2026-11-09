---
status: accepted
since: 4.0.0
---
# CLI surface: twelve commands, with one offline re-apply

`ai-kit` has `init`, `sync` (`--dry-run`; `--offline` re-applies the configuration recorded in `lock.toml` from the cache,
without network; `--from-bundle FILE`), `team list|use <name> [--url]|use none`, `status [--verbose]`, `doctor [--live]`,
`rollback`, `user edit`, `uninstall [--dry-run|--yes]`, `usage`, `friction [--list|--publish]`, `managed-settings --out` and
`validate [--path]`. With no action it prints `status`. The launchers run `init` when no action is given.

Rules fixed by this decision:

- Exit codes: 0 success, 1 refused or failed (nothing changed, or everything restored), 2 usage or a question impossible
  without a terminal, 3 `managed.toml` unusable, 130 interrupted.
- Writing commands (`init`, `sync`, `team use`, `rollback`) go through one activation that takes the engine lock and resumes
  an interrupted one.
- `status` describes and exits 0 whenever it could print; `doctor` checks and fails. Neither touches the network; only
  `sync` and `team use` read remote tags. `doctor --live` makes one real model call, needs `--yes` without a terminal, and is
  refused when `AI_KIT_NO_LIVE=1`.
- The agent may run `status`, `doctor` without `--live`, `team list`, `usage`, `validate`, `managed-settings`, `user edit` and
  the friction log. `protected-paths` refuses `init`, `sync`, `rollback`, `uninstall`, `team use`, `doctor --live` and
  `friction --publish` in the agent's shell, as defence in depth.
- Without a terminal nothing is asked: an unknown Team needs `--url`, `uninstall` and `doctor --live` need `--yes`.

**Why**: each command answers a need no other covers: `uninstall` removes by digest, `usage` measures before anything is
removed, `friction` makes publication a human act, `managed-settings` is the only generator of enforceable native controls,
`validate` checks Core and Team repositories in their CI. `sync --offline` re-applies a change of personal settings or of
`USER.md` without moving to a newer tag.

**Considered**: merging `team list` into `status`; making `managed-settings` a `doctor` option (`doctor` writes nothing);
folding `validate` into `sync --dry-run` (sources refuse local paths by design); `team add`, `skill install` or `--json`
output (not needed: `status --verbose` covers provenance).
