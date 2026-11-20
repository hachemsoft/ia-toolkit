---
status: accepted
since: 4.0.0
---
# CLI surface: thirteen commands, with one offline re-apply

`ai-kit` has `init`, `sync` (`--dry-run`; `--offline` re-applies the configuration recorded in `lock.toml` from the cache,
without network; `--from-bundle FILE`), `team list|use <name> [--url]|use none`, `status [--verbose]`, `doctor [--live]`,
`rollback`, `user edit`, `uninstall [--dry-run|--yes]`, `usage`, `friction [--list|--publish]`, `managed-settings --out`,
`validate [--path]` and `news --add [--path]` (4.19.0). With no action it prints `status`. The launchers run `init` when no action is given.

Rules fixed by this decision:

- Exit codes: 0 success, 1 refused or failed (nothing changed, or everything restored), 2 usage or a question impossible
  without a terminal, 3 `managed.toml` unusable, 130 interrupted.
- Writing commands (`init`, `sync`, `team use`, `rollback`) go through one activation that takes the engine lock and resumes
  an interrupted one.
- `status` describes and exits 0 whenever it could print; `doctor` checks and fails. Neither touches the network; only
  `sync` and `team use` read remote tags. `doctor --live` makes one real model call, needs `--yes` without a terminal, and is
  refused when `AI_KIT_NO_LIVE=1`.
- The agent may run `status`, `doctor` without `--live`, `team list`, `usage`, `validate`, `managed-settings`, `user edit`,
  `news --add` and the friction log. `protected-paths` refuses `init`, `sync`, `rollback`, `uninstall`, `team use`, `doctor --live` and
  `friction --publish` in the agent's shell, as defence in depth.
- Without a terminal nothing is asked: an unknown Team needs `--url`, `uninstall` and `doctor --live` need `--yes`.

**Why**: each command answers a need no other covers: `uninstall` removes by digest, `usage` measures before anything is
removed, `friction` makes publication a human act, `managed-settings` is the only generator of enforceable native controls,
`validate` checks Core and Team repositories in their CI. `sync --offline` re-applies a change of personal settings or of
`USER.md` without moving to a newer tag.

**Amended 2026-11-20 (`news --add`, 4.19.0)**: a thirteenth command, `news --add [--path <Core>] [--title] [--id] [--teams] [--until]`, the text on standard input. It writes one entry in a Core repository's `NEWS.md` (a folder with `NEWS.md` and `aikit.toml`, never under `~/.ai-kit`) and keeps it only when the file still reads in full by the rule `whats-new` applies (`installer/news.py`, which `scripts/check_news.py` now calls); otherwise the file is put back. It commits, tags and sends nothing: an entry reaches workstations with the Core's next tag and their `sync`. The agent may run it (the optional `/news` command does, with the person's agreement); refusals exit 1, a missing title or text without a terminal exits 2. Why: the entry was written by hand, and a malformed one was skipped by the hook without a word until the CI refused it.

**Considered**: merging `team list` into `status`; making `managed-settings` a `doctor` option (`doctor` writes nothing);
folding `validate` into `sync --dry-run` (sources refuse local paths by design); `team add`, `skill install` or `--json`
output (not needed: `status --verbose` covers provenance).
