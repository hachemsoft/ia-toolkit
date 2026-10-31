# MCP connections

An MCP server gives the agent access to a tool or to data: a documentation site, BigQuery, dbt, GitHub. The kit writes the same server into each installed CLI, under the name `ai-kit-<name>` ([where, CLI by CLI](cli/matrice.md)). It never downloads, starts or tests a server, and handles neither tokens nor OAuth.

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

## The rule: who decides what

| File | Who writes it | What it says | Example |
| --- | --- | --- | --- |
| `organization.json` (kit repository) | the platform team, by merge request | **how** to reach each approved server | `"bigquery": {"server": {"httpUrl": "https://…"}}` |
| `profiles/<profile>.json` (kit repository) | the kit maintainers | **which** servers are on for that job | `"mcp": ["bigquery", "dbt"]` |
| `organization.json`, under `teams.<team>` | the team, by merge request | **the team's exceptions**, same formats as yours | `"mcp": {"github": true}` |
| `~/.ai-kit/overrides.json` (your workstation) | you | **your exceptions**: turn one on or off, or add your own | `"mcp": {"dbt": false, "github": true}` |

A server is installed when it is **defined** (in `organization.json` or in your file) **and on** (through your profile, through `"enabled": true` in `organization.json`, through your team, or through your file). Order: organization, profile, team, you; your file has the last word. Teams: [customization](customization.md#teams). After any change: `update`, then restart the CLI.

## For the platform team: define the approved servers

In `organization.json`, under `defaults`, describe each server once. A server listed here is off, except for the profiles that list it:

```json
{
  "defaults": {
    "mcp": {
      "bigquery": { "server": { "httpUrl": "https://bigquery-mcp.example.org/mcp" } },
      "dbt": { "server": { "command": "dbt-mcp" } },
      "github": {
        "server": {
          "command": "docker",
          "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server:<pinned version>"],
          "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" }
        }
      },
      "docs": { "enabled": true, "server": { "httpUrl": "https://docs-mcp.example.org/mcp" } }
    }
  }
}
```

- `"enabled": true` (here `docs`) turns a server on for **every** profile.
- `server` has a single transport. Use `httpUrl` (streamable HTTP) or `url` (SSE), always `https://`, for a remote server. Use `command`, with `args` and `env`, for a local server.
- **Never write a secret.** Write `${VARIABLE}`, and each person defines the variable in their environment. `doctor` flags a key or token written in plain text.
- Pin image and package versions (`:1.2.3`, not `:latest`): a new version should arrive by your choice, not by itself.
- A local server needs its executable on the workstation (`docker`, `dbt-mcp`…), installed by the IT procedure. The kit does not install it. Prefer a remote server when one exists: nothing to install on the workstations.
- `trust: true` is refused: the CLI must keep asking before a server's tools act.

## For the kit maintainers: choose per profile

In `profiles/<profile>.json`, the list of servers that job needs:

```json
"mcp": ["bigquery", "dbt"]
```

These are names only. The address and the authentication depend on the organization, not on the job. A name that `organization.json` does not define installs nothing, and `doctor` reports it as "chosen but not defined in organization.json". In the public kit, `data-analyst` lists `bigquery` and `dbt`, and `data-developer` lists `bigquery`. No server is defined, so nothing is installed until the organization defines them.

## For each person: your exceptions and your own servers

In `~/.ai-kit/overrides.json`, under `mcp`, one line per exception:

| You want | You write |
| --- | --- |
| a server of the organization that your profile does not turn on | `"github": true` |
| to turn off a server your profile turns on | `"dbt": false` |
| your own server, for the three CLIs | `"mine": {"server": {"command": "my-mcp", "env": {"TOKEN": "${MY_TOKEN}"}}}` |
| to keep your server's definition but turn it off for now | `"mine": {"enabled": false, "server": {…}}` |

Full example:

```json
{
  "mcp": {
    "github": true,
    "dbt": false,
    "mine": { "server": { "httpUrl": "https://my-mcp.example.org/mcp" } }
  }
}
```

Then `update`, and restart the CLI (Claude Code: close its sessions before `update`, see [its page](cli/claude-code.md#close-claude-code-before-an-update)). Check with the CLI's own MCP command that the server answers (each CLI's command and settings file: [CLI matrix](cli/matrice.md)). Then run `doctor`: its line `[Info] MCP servers: …` lists what is installed.

The older format, `{"enabled": true, "server": {…}}` for a server of your own or `{"enabled": true}` for one of the organization, still works.

**A server for one CLI only:** add it directly in that CLI's own settings ([CLI matrix](cli/matrice.md)). The kit only manages the servers named `ai-kit-<name>` and never touches the others.

## Removing

Remove the name from the profile or from `organization.json`, or write `"<name>": false` in your file, then `update`. Only the `ai-kit-<name>` server is removed; the others stay. If a managed server was edited by hand in a CLI's settings, `update` stops and asks you to choose: move the change to `overrides.json`, or restore the server.

## BigQuery and dbt

- The platform team chooses the server and the authentication mode.
- Real limits come from IAM and from the tools the server exposes. Instructions to the agent are not access control.
- Specific GCP projects, datasets, dbt targets and budgets stay in the repo that owns them.
- Check that the dbt tools match your versions and your deployment mode.
- Test discovery, connection and allowed operations from each CLI on a development environment.

`doctor` checks that the configuration is written, and that a local server's executable exists. It does not call the server, check the identity or test permissions.
