# managed.toml: settings IT imposes on AI Kit

Since 2.0.0, IT can impose some AI Kit settings with one file, deployed by the usual device management and read-only for the person:

| System | Path |
| --- | --- |
| macOS | `/Library/Application Support/ai-kit/managed.toml` |
| Windows | `C:\ProgramData\ai-kit\managed.toml` |
| Linux | `/etc/ai-kit/managed.toml` |

The path is fixed: no environment variable moves it. The workstation is administered when the file exists. AI Kit refuses the file, and changes nothing (exit code 3), when the person could change it (POSIX: not owned by root, or the file or its folder writable by the user; Windows: the user can open it for writing), when it cannot be read, or when it holds a key this version does not apply. `ai-kit doctor` shows which keys it sets, or why it is refused, where each setting comes from, and whether IT changed the file since the last update (then run `ai-kit update`).

## Rules

- Every key present wins over `organization.toml`, the team and the person's `overrides.toml`, whatever its value: `false` and `[]` are values.
- A key absent locks nothing.
- `hooks.locked` and `mcp.denied` are restrictions: they add to the organization's, and nobody else lifts them.
- A person who refused to share their frictions (`share_frictions = false`) keeps them local even when IT sets the publication mode.
- Unknown keys are refused, never ignored: an IT file that expects an effect the kit does not apply is an error to fix, not a silent no-op.

## Keys (managed_schema = 1)

Editors complete and check the file with `schemas/managed.schema.json` (add `#:schema <path to it>` as its first line).

```toml
managed_schema = 1

[hooks]
locked = ["protected-paths"]     # guardrails nobody can turn off
dbt-prod-guard = true            # a guardrail switched on (or off) for everyone

[mcp]
allow_stdio = false              # no local (stdio) MCP server is installed
denied = ["legacy-db"]           # these servers are not installed

[frictions]
capture = "propose"              # propose | auto | off: what the agent does on a friction
publication = "approval"         # approval (default) | auto | disabled
```

`publication`: with `approval`, a friction is never sent on its own; the person sends it from a terminal with `ai-kit friction --sync` (the agent may not run it). With `auto`, it is sent when logged, as before 2.0.0. With `disabled`, nothing is sent.

## What it does not do

`managed.toml` configures AI Kit. It does not lock the workstation, the CLIs' own settings, or another program a person runs: for rules that must hold, deploy the CLIs' native managed settings as well (`ai-kit managed-settings`, see [hooks](hooks.md#rules-it-can-enforce)). Further keys (Git sources, allowed Teams, MCP identities) arrive with the next 2.x releases; a file using them is refused by an older 2.x until the kit is updated.
