---
status: accepted
since: 0.24.0 and 0.28.0 (reconstructed from the CHANGELOG)
---
# One organization file at the root; defaults merged with the person's settings, never replaced

`organization.toml` at the root of the kit repository holds what belongs to the organization: expected email domains, default settings, teams. Its defaults are always merged with the team's and the person's files (lists add up, objects combine, for a single value the person wins). Before, a personal file replaced the defaults wholesale, and a one-line personal change dropped the organization's guardrails. MCP servers are resolved from the three sources separately: the organization says how to reach a server, a profile says which ones are on, the person turns one on or off; a merged `"github": true` used to erase the server's definition.

**Consequences**: the organization changes its file by merge request and the change reaches workstations with the next version; `doctor` lists the defaults a person changed.
