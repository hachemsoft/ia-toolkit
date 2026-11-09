---
status: accepted, amended: there is no Core policy layer and no `resources.denied_*` key; the restrictions implemented are `hooks.locked`, `mcp.denied` and the MCP allowlists
since: 4.0.0
---
# managed.toml wins on every key it sets; values resolve by precedence, restrictions all apply

IT's `managed.toml` is read from a fixed administered path (`C:\ProgramData\ai-kit\managed.toml`,
`/Library/Application Support/ai-kit/managed.toml`, `/etc/ai-kit/managed.toml`), never from an environment variable.
Managed mode is on if and only if that file exists. Every key present takes effect whatever its value (`false`, `0`, `""`
and `[]` included), and no other layer can replace or cancel it. Three kinds of keys:

- **value** (a guardrail switch, `frictions.capture`, `skill_prefix`…): one effective value, the first present in
  `managed.toml`, the person's `~/.ai-kit/aikit.toml`, the Core default, the engine default. A personal value that a managed one replaces is ignored with an
  `[Info]` line.
- **restriction** (`hooks.locked`, `mcp.denied`, `mcp.allow_stdio = false`, `mcp.allowed_stdio`, `mcp.allowed_http`,
  `teams.allowed`, `git.allowed_*`, `git.revoked`): each applies, none lifts another. In an allowlist, an absent key means
  unrestricted and `[]` means nothing allowed. The person's own refusals (`[mcp] denied`, `[frictions] publication =
  "disabled"`) are restrictions too, which no other layer lifts.
- **selection** (`extra_*`, `disabled_*`): the Team's then the person's choices, inside the restrictions.

The schema is closed (`schemas/managed.schema.json`): an unknown key, a wrong type, or a file not owned by root (POSIX) or
writable by the current user refuses every change with exit code 3 and keeps the active configuration. `managed.toml` is re-read by every
command; its digest is recorded at each activation so that `status` reports a change not yet applied.

**Why**: a person's file must not lift what IT set, and treating a deny list as a mergeable value would let one owner lift
another's prohibition unknowingly; reading `[]` as "unrestricted" would turn an IT "none" into "all".

**Consequences**: `managed.toml` governs AI Kit only, not the workstation or the CLIs' own files: enforceable controls are the
CLIs' managed settings that `ai-kit managed-settings` generates from the same decisions. IT sets the friction publication
mode, never a person's consent.

**Considered**: the person wins with lists added up (the previous behaviour, which let one personal line drop an
organization's guardrails); a union of deny lists as an exception to "managed wins" (an exception inside an absolute rule).
