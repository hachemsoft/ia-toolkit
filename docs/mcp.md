# MCP servers

With this page you know where the agent's MCP servers come from, how to turn one on or off, and what IT and approvals allow. An MCP server gives the agent a tool or data: documentation, an issue tracker, a database. Concepts: [architecture](architecture.md).

The kit writes each server into every installed CLI under the name `ai-kit-<name>`. It never downloads, starts or tests a server, and holds no token.

## Where servers come from

| Source | File | Default |
| --- | --- | --- |
| Core | `mcp/servers.toml` of the Core repository | off, unless the server says `enabled = true` (then on for everyone) |
| Team | `mcp/servers.toml` of the Team repository | on for the Team's members, unless `enabled = false` |
| You | `[mcp] enabled` and `denied` in `~/.ai-kit/aikit.toml` | names only: you turn a defined server on or off |
| A project | the CLI's own project configuration | not touched: the kit never modifies a project repository |

A server is installed when it is defined (Core or Team), turned on, and not refused by IT. Servers you add yourself in a CLI's own settings are left alone: the kit manages only the `ai-kit-<name>` ones.

## Defining a server

One `[servers.<name>]` table per server, a single transport:

```toml
[servers.docs]
enabled = true
httpUrl = "https://docs-mcp.example.org/mcp"

[servers.tracker]
command = "tracker-mcp"
args = ["--read-only"]
env = { TRACKER_TOKEN = "${TRACKER_TOKEN}" }
required = false
```

| Key | Meaning |
| --- | --- |
| `command`, `args`, `env`, `cwd` | a local (stdio) server |
| `httpUrl` or `url` | a remote server; `https://` only |
| `headers` | remote headers |
| `required` | `true`: if the server is refused, the run fails and nothing changes |
| `enabled` | on or off by default, as in the table above |

- A value in `env` or `headers` that looks secret is refused: write `${VARIABLE}`, defined in each person's environment.
- `trust` is refused: the CLI keeps asking before a server's tools act.
- An unknown key, or a shell (or a shell script) as the command, is reported.
- Pin versions (`:1.2.3`, `pkg==1.2.3`, `pkg@1.2.3`), never `latest`.
- A local server needs its program on the workstation, installed by your IT procedure.

## Turning a server on or off

```toml
# ~/.ai-kit/aikit.toml
[mcp]
enabled = ["tracker"]   # a Core or Team server, turned on
denied = ["docs"]       # turned off; a refusal wins over enabled
```

Then `ai-kit sync --offline` and restart the CLI. `doctor` prints `[Info] MCP servers: …`, and the names you chose that nothing defines.

## What IT allows

In `managed.toml` `[mcp]` ([configuration](configuration.md#managedtoml-it)):

| Key | Effect |
| --- | --- |
| `denied` | never installed: a name, a URL prefix (`https://host/path`) or an executable |
| `allow_stdio = false` | no local server at all |
| `allowed_stdio` | only the local servers whose identity is listed |
| `allowed_http` | only the remote servers whose identity is listed |

A refused server is reported: `[Info] MCP server <name> not installed: <why>.` For the CLIs that support it, `ai-kit managed-settings --out <folder> --managed-mcp-only` writes policy files that allow only the Core's servers.

## Team servers

A Team brings its own servers, so the local ones are checked before they run:

| Case | Result |
| --- | --- |
| remote server | installed, subject to IT's rules above |
| local server, identity in IT's `allowed_stdio` | installed |
| local server, approved on this workstation | installed |
| local server, not approved, at a terminal | the kit shows the command and asks: "Allow it on this workstation?" |
| local server, not approved, no terminal | not installed |
| `npx`, `uvx`, `bunx`, `pnpx` or `pipx` with a package without an exact version | refused |
| any refusal of a server marked `required` | the run fails: `MCP server <name> is required by the Team but …: nothing was changed.` |

An approval is recorded once per identity, in `~/.ai-kit/state.json`.

## Identity

A server's identity is `sha256:` of its exact command, arguments, `env` templates and `cwd` (local), or of its URL and header templates (remote). A rename does not change it; a changed argument does, so the server needs a new approval or a new IT entry. `ai-kit status --verbose` prints each installed server's identity, the value IT copies into `allowed_stdio` or `allowed_http`.

## Limits

`doctor` checks that the configuration is written; it does not call the server, check the account or test permissions. Real limits come from the server's own access rights, not from instructions to the agent.
