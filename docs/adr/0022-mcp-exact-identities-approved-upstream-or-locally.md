---
status: accepted
since: 4.0.0
---
# MCP: exact identities, approved by IT or on the workstation; what policy forbids is not installed

The Core defines its servers in `mcp/servers.toml`; a Team may ship its own; the person turns servers on or off
(`[mcp] enabled`, `denied`). A server's keys are a closed list (`command`, `args`, `env`, `cwd`, `httpUrl`, `url`, `headers`,
`required`); `trust` is refused; a remote server must use HTTPS; an `env` or `headers` value that looks secret is refused
(`${VARIABLE}` only); `args` and URLs are not searched for secrets. A server's identity is the SHA-256 of its exact command, args, env templates and folder (stdio), or of
its URL and header templates (http): a rename does not change it, a changed argument does.

`managed.toml` decides first: `mcp.denied` matches a name, a URL prefix or an executable; `mcp.allow_stdio = false` refuses
every local server; `mcp.allowed_stdio` and `mcp.allowed_http`, when present, allow only the listed identities. A local
server a Team brings is kept only when IT lists its identity or the person approves it once in a terminal (recorded as
`mcp_approvals` in `state.json`); nothing is approved without a terminal, and an unpinned fetch-and-run launcher (`npx`,
`uvx`…) from a Team is refused. A refused server marked `required = true` stops the change; an optional one is skipped with
a notice. Server names stay `ai-kit-<name>`. `managed-settings` builds the CLIs' native allowlists from the same decisions.

**Why**: with Teams, any local entry is code run at every CLI start. Allowing executables by name (`python`, `uvx`) still
runs anything, and denying by name is escaped by a rename. The CLIs' native allowlists match exact command and args; AI
Kit's check agrees with them.

**Consequences**: a person confirms each new or changed Team server once when IT lists none. AI Kit never vouches for a
server's code or package version. A shell as the command, or a key outside the list, is reported with a `[Check]` line when
the configuration is applied, and still installed.

**Considered**: a prefix per source in server names (renames every server for information the state already holds); an
approval flag on the command line (an agent could pass it); probing a server's code (no execution, no false assurance).
