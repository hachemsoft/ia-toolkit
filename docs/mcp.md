# MCP connections

Catalog definitions are preparation sheets, not working servers. The kit configures each CLI from the user overrides (overrides.json), in the form the CLI reads ([matrix](cli/matrice.md)). The team may prefill these configurations in a later version.

## Approved remote server

In `~/.ai-kit/overrides.json`, add an entry with `enabled: true` and `server`. Illustrative example only: replace the URL with your approved server before enabling it.

```json
{
  "extra_skills": [],
  "disabled_skills": [],
  "mcp": {
    "documentation": {
      "enabled": true,
      "server": {
        "httpUrl": "https://mcp.example.org/mcp"
      }
    }
  }
}
```

Run `update`, then restart the CLI and check its MCP servers with its command (see its page). Depending on the server, follow its authentication flow. The kit handles neither OAuth nor tokens. For an approved SSE transport, use `url` instead of `httpUrl`.

## Approved local server

The `server` field can contain `command`, `args` and the server settings. The kit never downloads or runs this command. The required executables must be available on the workstation; prefer a remote endpoint or a runtime already present. A command with a Mac-specific path must be adapted on Windows.

Keep the environment variable references the server requires; do not put secrets in plain text in the files. Do not enable `trust: true`: this kit rejects it. Backups can contain your previous configuration; treat them as sensitive personal files.

## Disabling

Set `enabled` to false or remove the entry, then run `update`. Only the connection prefixed `ai-kit-` that the kit managed before is removed. Other MCP servers are kept. If a managed MCP was edited directly in the settings, the kit asks you to resolve the conflict.

## BigQuery and dbt

- Have the platform team choose the server and the authentication mode.
- Actually limit rights through IAM and the allowed tools; instructions are not access control.
- Keep specific GCP projects, datasets, dbt targets and budgets in the owning repo.
- Check that dbt tools are compatible with your versions and your deployment mode.
- Test discovery, connection and allowed operations from each CLI on a development environment.

`doctor` checks that the configuration exists, and the local executable if there is one. It does not ping, query, validate identity or test permissions.
