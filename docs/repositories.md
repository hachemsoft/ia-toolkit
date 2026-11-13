# Core and Team repositories

With this page you publish a Core or a Team repository, understand how versions reach workstations, and work offline. Concepts: [architecture](architecture.md).

## Two kinds of source

| Source | Holds | Set by |
| --- | --- | --- |
| Core | the base everyone gets: skills, agents, commands, context, templates, workflows, `mcp/servers.toml` | IT's `enterprise.core`, else `[core] repo` in the person's `aikit.toml` |
| Team | what one team adds: skills, agents, context, `mcp/servers.toml`, `[defaults]` | `ai-kit team use <name> --url <URL>` |

Both are Git repositories with an `aikit.toml` manifest at their root (`schema`, `name`, `kind`, `min_engine`). A source whose `min_engine` is newer than the running AI Kit is refused. This repository is itself a Core: its own `aikit.toml` declares `name = "core"`.

## Team repository

Start from `examples/team-repo/`:

```text
team-repo/
  aikit.toml              # schema = 1, name = "reporting", kind = "team", [defaults]
  context/team.md         # every context/*.md becomes the team's context layer
  skills/report-check/SKILL.md
  agents/                 # <name>.md, same format as the Core's
  mcp/servers.toml        # optional: the team's own MCP servers
```

```toml
schema = 1
name = "reporting"
kind = "team"

[defaults]
extra_skills = ["sql-review", "report-check"]
extra_agents = ["sql-reviewer"]
```

Rules the kit enforces:

- `name` and `kind = "team"` must match the name people type in `team use <name>`.
- A Team may not hold `commands/`, `policies/`, `hooks/` or `runtime/`: only the Core defines them.
- A Team skill or agent with the name of a Core one replaces it, unless the Core marks it `aikit-protected: "true"` (refused).
- Each skill and agent declares `aikit-version` in its metadata.
- A Team's MCP servers are on for its members; a local one needs an approval ([MCP](mcp.md#team-servers)).

## Tags and versions

- Only stable tags `vX.Y.Z` are followed, never a branch. `vX.Y.Z-rc.N` only with `git.allow_prerelease`.
- `sync` takes the highest eligible tag and never goes below the active one; only `rollback` goes back.
- A published tag must never move: the kit records every tag it has seen, and a tag that now points to another commit stops the sync.
- Git runs with no global or system configuration, no hooks, no redirects, and only a credential helper from a closed list (`manager`, `manager-core`, `osxkeychain`, `libsecret`, `wincred`). A URL rewritten by Git is refused.
- Accepted URLs: `https`, and `ssh` (also `git@host:path`); no credentials in the URL. IT can narrow hosts, groups and schemes.
- Only regular files are extracted: a symbolic link, a submodule, an unsafe path or two paths that differ only by case are refused.

Publishing: protect the tags on your Git host, run `ai-kit validate --path <folder>`, then tag `vX.Y.Z` and push the tag.

## Lock and cache

| Path | Holds |
| --- | --- |
| `~/.ai-kit/lock.toml` | the active Core and Team (URL, tag, tag object, commit, tree digest), the previous configuration for `rollback`, the known Teams. Written by `sync`, `team use` and `rollback`; do not edit it (`doctor` notices). |
| `~/.ai-kit/sources/` | one bare Git cache per source, pruned to the tags `lock.toml` cites |

Every command reads the locked content from the cache, without network. `sync --offline` re-applies it. Changing to a Team already in the cache needs no network either.

## Offline bundle

The release ZIP ships the Core as a Git bundle, `core/ai-kit-core.bundle`. A first install from the ZIP activates it offline, recorded under the configured Core URL (IT's `enterprise.core`, your `[core] repo`, else this kit's repository). Later, `ai-kit sync --from-bundle <file>` installs the highest tag of a bundle offline; it uses the configured Core repository, else the one recorded at the first install.

## Signed tags

When IT lists SSH public keys in `managed.toml` `git.signers`, a tag must carry an SSH signature from one of them, or nothing changes. Sign with Git's SSH signing (`gpg.format = ssh`) when you tag.

## Validate before you tag

```sh
ai-kit validate --path <folder>   # default: the kit's own content
```

Read-only; one `[Check]` line per problem; exit code 1 when there is one.

| Kind | Checks |
| --- | --- |
| Core | manifest; each skill and agent describes itself (`aikit-*` metadata, `aikit-version`, name = folder or file); required skills exist, no cycle; commands' skills exist; no skill named like a command; the content scan (secrets, pipe to shell, prompt injection, guardrail off, configuration writes, undeclared scripts) |
| Team | manifest; no `commands/`, `policies/`, `hooks/`, `runtime/`; skills and agents describe themselves; the content scan |

To create a Core repository from a clone of this kit: `python3 scripts/export_core.py <empty folder> --git` (one commit, tag `v<VERSION>`, nothing pushed).
