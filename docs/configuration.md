# Configuration

With this page you know which file to change for what, who wins when two files disagree, and every key each file accepts. Concepts: [architecture](architecture.md).

## The files a human writes

| File | Who writes it | Where |
| --- | --- | --- |
| `managed.toml` | IT | macOS `/Library/Application Support/ai-kit/managed.toml`, Windows `C:\ProgramData\ai-kit\managed.toml`, Linux `/etc/ai-kit/managed.toml` |
| `aikit.toml` of a Team | the team, by merge request | root of the Team repository ([repositories](repositories.md#team-repository)) |
| `aikit.toml` of the person | you | `~/.ai-kit/aikit.toml`, created by `init` from `templates/user-aikit.toml` |
| `USER.md` | you (or `/me`) | `~/.ai-kit/context/USER.md` |

The Core's choices are not a file you write: its default selection is the `aikit-default: "true"` metadata of each skill and agent (a command with `default: false` is optional, turned on with `extra_commands`), and its MCP servers are in its `mcp/servers.toml` ([MCP](mcp.md)). After a change, run `ai-kit sync --offline`, then start a new CLI session.

## Precedence

| Layer | Sets | Rule |
| --- | --- | --- |
| Core | default selection, MCP servers | the base |
| Team `[defaults]` | optional resources turned on, its own skills, agents, context and MCP servers | adds to the Core |
| Your `aikit.toml` | your additions and removals, guardrails, MCP on or off, frictions, sources | lists add up; a `disabled_*` name or a `denied` server wins |
| `managed.toml` | what IT imposes | every key present wins, whatever its value; its restrictions add to the others and nobody lifts them |

`ai-kit status --verbose` (or `doctor`) prints where each effective setting comes from (`Core`, `team`, `you`, `IT`).

## Your `~/.ai-kit/aikit.toml`

`schema = 1` is required. A wrong type stops the command; an unknown key is reported and ignored.

| Key | Value | Effect |
| --- | --- | --- |
| `[user] extra_skills`, `extra_commands`, `extra_agents` | list of names | add to the selection; a command added also installs its skills |
| `[user] disabled_skills`, `disabled_commands`, `disabled_agents` | list of names | remove from the selection |
| `[user] skill_prefix` | up to 20 of `a-z0-9-`, or `""` | prefix of the kit skills in Claude Code (always), and in the other CLIs of a kit skill or command whose name you already use (default `ai-kit-`) |
| `[user] active_team` | name or `none` | written by `team use` and `rollback`; editing it does not switch Team |
| `[hooks] <guardrail>` | `true` or `false` | turns a guardrail on or off ([guardrails](hooks.md)) |
| `[mcp] enabled`, `denied` | list of server names | turns a Core or Team server on, or off ([MCP](mcp.md)) |
| `[frictions] capture` | `propose`, `auto`, `off` | how the agent logs frictions ([frictions](frictions.md)) |
| `[frictions] publication` | `approval`, `disabled` | `disabled` keeps your frictions local |
| `[core] repo` | Git URL | your Core repository (IT's `enterprise.core` wins) |
| `[git] allow_prerelease` | `true` or `false` | also follow `vX.Y.Z-rc.N` tags, unless IT decides |
| `[teams.<name>] repo` | Git URL | a known Team; written by `team use --url` |

```toml
schema = 1

[user]
extra_skills = ["sql-review"]
disabled_commands = ["learn"]

[hooks]
dbt-prod-guard = true

[mcp]
enabled = ["docs"]
```

Never write a secret here: `doctor` flags one. Write `${VARIABLE}` and define the variable in your environment.

## A Team's `aikit.toml`

| Key | Value |
| --- | --- |
| `schema` | `1` |
| `name` | the Team name, the one people type in `team use <name>` |
| `kind` | `"team"` |
| `min_engine` | optional `X.Y.Z`: an older AI Kit refuses the content |
| `[defaults] extra_skills`, `extra_agents`, `extra_commands`, `disabled_skills`, `disabled_agents`, `disabled_commands` | lists of names |

## `managed.toml` (IT)

Closed schema (`schemas/managed.schema.json`). A file that is unreadable, writable by the user (POSIX: not owned by root, or its folder writable), has an unknown key or a wrong type is refused: every command that changes files stops with exit code 3 and nothing changes. A missing file means not administered.

| Key | Value | Effect |
| --- | --- | --- |
| `managed_schema` | `1` | required |
| `[enterprise] core` | Git URL | the Core every workstation uses; no trust question |
| `[git] allowed_hosts` | list | Git hosts accepted, exactly |
| `[git] allowed_groups` | list | path prefixes accepted (a whole group) |
| `[git] allowed_schemes` | `https`, `ssh` | schemes accepted (default both) |
| `[git] allow_prerelease` | bool | replaces the person's choice |
| `[git] revoked` | 40-hex commit SHAs | never activated, even by `rollback` |
| `[git] signers` | SSH public keys | a tag must carry an SSH signature from one of them |
| `[teams] allowed` | Team URLs or prefixes | only these Teams |
| `[teams] allow_unknown` | bool | `false`: no Team that is not already known |
| `[hooks] locked` | guardrail names | kept on, whatever anyone writes |
| `[hooks] <guardrail>` | bool | on or off for everyone |
| `[mcp] allow_stdio` | bool | `false`: no local server |
| `[mcp] allowed_stdio`, `allowed_http` | `sha256:<64 hex>` identities | only these local or remote servers |
| `[mcp] denied` | names, URL prefixes or executables | never installed |
| `[frictions] capture` | `propose`, `auto`, `off` | replaces the person's choice |
| `[frictions] publication` | `approval`, `auto`, `disabled` | how frictions reach the tracker |
| `[frictions] retention_days` | integer, 1 or more | local frictions purged after this (default 30) |
| `[frictions] tracker` | table: `kind` (`gitlab`, `github`), `project`, `host`, `labels`, `sources` | where frictions go ([frictions](frictions.md)) |

`ai-kit managed-settings --out <empty folder>` writes the CLI policy files IT can deploy, built from the Core and `managed.toml` ([guardrails](hooks.md#rules-it-can-enforce)).

## `USER.md`, your personal context

Your role, your domains, how you want answers. The agent reads it in every session; the project's instructions take precedence. The kit creates it once and never rewrites it. Edit it with `ai-kit user edit` (your `$VISUAL` or `$EDITOR`, else the system's text editor) or `/me` in the CLI. Keep it plain UTF-8 text: `doctor` says when it is not, or when it seems to hold a secret.

The rule layers next to it (`00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` or the active Team's layer) belong to the kit: a hand edit is restored at the next run, your copy kept in `~/.ai-kit/backups`.

## Identity

`init` detects an identity, in order: the CLI's active account where the kit can read it, the global Git `user.email` and `user.name`, the system login. You confirm it at a terminal, or pass `--user <email>`. It is recorded in `~/.ai-kit/state.json`; only your name goes in the header of `USER.md` when the file is created, never your email. `doctor` prints it and, where the CLI exposes its active account, checks that they match. The identity is not authentication and grants no rights; tokens are never read.

## Authentication and model

The kit never sets the CLI's sign-in, project or model. Follow your IT procedure in each CLI ([CLI pages](cli/matrice.md)). `doctor --live` names a missing setting when the call fails.
