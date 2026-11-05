# MCP connections

An MCP server gives the agent access to a tool or to data: a documentation site, GitHub, an issue tracker, a database. The kit writes the same server into each installed CLI, under the name `ai-kit-<name>` ([where, CLI by CLI](cli/matrice.md)). It never downloads, starts or tests a server, and handles neither tokens nor OAuth.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

## The rule: who decides what

| File | Who writes it | What it says | Example |
| --- | --- | --- | --- |
| `organization.toml` (kit repository) | the platform team, by merge request | **how** to reach each approved server | `docs = { server = { httpUrl = "https://…" } }` under `[defaults.mcp]` |
| `profiles/<profile>.toml` (kit repository) | the kit maintainers | **which** servers are on for that job | `mcp = ["github"]` |
| `organization.toml`, under `teams.<team>` | the team, by merge request | **the team's exceptions**, same formats as yours | `mcp = { github = true }` |
| `~/.ai-kit/overrides.toml` (your workstation) | you | **your exceptions**: turn one on or off, or add your own | `mcp = { docs = false, github = true }` |

A server is installed when it is **defined** (in `organization.toml` or in your file) **and on** (through your profile, through `enabled = true` in `organization.toml`, through your team, or through your file). Order: organization, profile, team, you; your file has the last word. Teams: [customization](customization.md#teams). After any change: `update`, then restart the CLI.

## For the platform team: define the approved servers

In `organization.toml`, under `defaults`, describe each server once. A server listed here is off, except for the profiles that list it:

```toml
[defaults.mcp.github.server]
command = "docker"
args = [
  "run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
  "ghcr.io/github/github-mcp-server:<pinned version>",
]
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GITHUB_PERSONAL_ACCESS_TOKEN}" }

[defaults.mcp.docs]
enabled = true
server = { httpUrl = "https://docs-mcp.example.org/mcp" }
```

- `enabled = true` (here `docs`) turns a server on for **every** profile.
- `server` has a single transport. Use `httpUrl` (streamable HTTP) or `url` (SSE), always `https://`, for a remote server. Use `command`, with `args` and `env`, for a local server. Do not use `cwd`: not every CLI has it, and the kit refuses it there; give the full path in `command`.
- **Never write a secret.** Write `${VARIABLE}`, and each person defines the variable in their environment. `doctor` flags a key or token written in plain text in `~/.ai-kit/overrides.toml`; nothing checks `organization.toml`, so review it in the merge request.
- Pin image and package versions (`:1.2.3`, not `:latest`): a new version should arrive by your choice, not by itself.
- A local server needs its executable on the workstation (`docker`, a language runtime…), installed by the IT procedure. The kit does not install it. Prefer a remote server when one exists: nothing to install on the workstations.
- `trust: true` is refused: the CLI must keep asking before a server's tools act.
- To make this list the only one allowed on the workstations, IT deploys the managed settings generated with `managed-settings --managed-mcp-only` ([guardrails](hooks.md#a-lock-nobody-on-the-workstation-can-remove)). Without them, a person can still add a server of their own.

## For the kit maintainers: choose per profile

In `profiles/<profile>.toml`, the list of servers that job needs:

```toml
mcp = ["github"]
```

These are names only. The address and the authentication depend on the organization, not on the job. A name that `organization.toml` does not define installs nothing, and `doctor` reports it as "chosen but not defined in organization.toml". In the public kit, `data-analyst` lists `bigquery` and `dbt`, and `data-developer` lists `bigquery`. No server is defined, so nothing is installed until the organization defines them.

## For each person: your exceptions and your own servers

In `~/.ai-kit/overrides.toml`, under `mcp`, one line per exception:

| You want | You write |
| --- | --- |
| a server of the organization that your profile does not turn on | `github = true` under `[mcp]` |
| to turn off a server your profile turns on | `docs = false` under `[mcp]` |
| your own server, for every installed CLI | `[mcp.mine]` then `server = { command = "my-mcp", env = { TOKEN = "${MY_TOKEN}" } }` |
| to keep your server's definition but turn it off for now | `enabled = false` under `[mcp.mine]`, next to its `server` |

Full example:

```toml
[mcp]
github = true
docs = false

[mcp.mine]
server = { httpUrl = "https://my-mcp.example.org/mcp" }
```

Then `update`, and restart the CLI (some CLIs must be closed before an update that changes MCP: [CLI matrix](cli/matrice.md#known-limits-of-the-clis)). Check with the CLI's own MCP command that the server answers (each CLI's command and settings file: [CLI matrix](cli/matrice.md)). Then run `doctor`: its line `[Info] MCP servers: …` lists what is installed.

**A server for one CLI only:** add it directly in that CLI's own settings ([CLI matrix](cli/matrice.md)), never in a file the kit manages (it rewrites them). The kit only manages the servers named `ai-kit-<name>` and never touches the others.

## Removing

Remove the name from the profile or from `organization.toml`, or write `<name> = false` under `[mcp]` in your file, then `update`. Only the `ai-kit-<name>` server is removed; the others stay. If a managed server was edited by hand in a CLI's settings, `update` stops and asks you to choose: move the change to `overrides.toml`, or restore the server.

## BigQuery and dbt

- The platform team chooses the server and the authentication mode.
- Real limits come from IAM and from the tools the server exposes. Instructions to the agent are not access control.
- Specific GCP projects, datasets, dbt targets and budgets stay in the repo that owns them.
- Check that the dbt tools match your versions and your deployment mode.
- Test discovery, connection and allowed operations from each CLI on a development environment.

`doctor` checks that the configuration is written (and, for some CLIs, that a local server's executable is on the PATH). It does not call the server, check the identity or test permissions.
