# Guardrails

With this page you know which guardrails run, how to turn one on or off, what IT can lock, and what the agent is refused. A guardrail is a script the CLI runs before a tool call: it blocks some mistakes in the forms it recognises. It is not a sandbox. Concepts: [architecture](architecture.md).

## The list

From `runtime/hooks/hooks.json`:

| Name | Runs | Default | Blocks |
| --- | --- | --- | --- |
| `protected-paths` | before a write or shell tool | on | agent writes to the configuration of the kit and of the CLIs, and under a repo's protected paths |
| `dbt-prod-guard` | before a shell tool | off | a dbt command on a production target |
| `whats-new` | at session start | on | nothing: not a guardrail, it tells the agent what is new |

The scripts are copied to `~/.ai-kit/hooks/` and declared to each CLI in its own format ([CLI pages](cli/matrice.md)). They run with the kit's private Python, isolated with `-I`. Your own hooks are kept.

## Turning one on or off

```toml
# ~/.ai-kit/aikit.toml
[hooks]
dbt-prod-guard = true
protected-paths = true
```

Then `ai-kit sync --offline`. IT decides above you in `managed.toml`:

| Key | Effect |
| --- | --- |
| `[hooks] locked = ["protected-paths"]` | stays on, whatever you write; the run says `[Info] Guardrail <name> stays on` |
| `[hooks] <guardrail> = true` or `false` | on or off for everyone; your value is ignored, and the run says so |

Only `protected-paths` and `dbt-prod-guard` are guardrails IT can name.

## `protected-paths`

Always blocks an agent's write to:

- `~/.ai-kit/`: `aikit.toml`, `lock.toml`, `sources/`, `state.json`, `hooks/`, `bin/`, `backups/`, `runtime/`, `schemas/`, and the rule layers `00_`, `10_`, `20_` in `context/`;
- the CLIs' settings and instruction files the kit manages, and every file the kit installed (skills, commands, agents);
- Git's own configuration, `~/.gitconfig` and `~/.config/git/config`, and the `.git/config` and `.git/hooks` of the kit folder;
- in a repository: `.ai-kit/protected-paths` and the CLI settings files that could turn hooks off; a `.env` that sets `AI_KIT_*` or `DBT_TARGET`.

`USER.md` and `~/.ai-kit/learning/` stay writable.

A shell command that names a protected file is allowed only when every program it runs only reads (`cat`, `grep`, `ls`…); a redirection to it, or a `cd` into a configuration folder, is refused.

**Your repo's own protected paths.** List glob patterns, one per line, `#` for comments, in `<repo>/.ai-kit/protected-paths`:

```text
target/**
models/legacy/**
*.lock
```

The file is read in the starting folder and each parent up to the repo root. Matching ignores case. These patterns apply to the agent's write tools, not to shell commands.

**Kit commands the agent may not run.** `ai-kit init`, `sync`, `rollback`, `uninstall`, `team use`, `doctor --live`, `friction --publish` (also through `python -m ai_kit` or the launchers). The agent tells you the command to run in a terminal. Reading commands (`status`, `doctor`, `usage`, `friction --list`) stay allowed.

The refusal reaches the agent as a tool error starting with `Blocked by the kit:`.

## `dbt-prod-guard`

Blocks a `dbt` command whose target is `prod`, `production` or `prd` (or the comma-separated list in `AI_KIT_PROD_TARGETS`), written as `--target`, `-t` or `DBT_TARGET`. Without a target, it reads the default target in `profiles.yml` (`--profiles-dir`, `DBT_PROFILES_DIR`, the repo, `~/.dbt`). A target only known at run time (`$VAR`, `$(…)`) is blocked too.

An authorised person exports `AI_KIT_ALLOW_PROD=1` in the shell that starts the CLI. The same variable in a `.env` file the agent could write is ignored.

## `whats-new`

At the start of a new or resumed session, tells the agent once, so that it says it in its first reply:

- the `CHANGELOG.md` section of the installed version;
- the entries of the content's `NEWS.md` aimed at everyone or at the active Team (`teams:`), until their `until:` date.

Both are copies the installation writes to `~/.ai-kit/news/`: no network, no remote text. What was announced is recorded in `~/.ai-kit/news.json`. It also runs the local friction upkeep ([frictions](frictions.md)) and never blocks a session.

## Rules IT can enforce

The guardrails above are installed per person. To make them hold whatever a person or an agent changes, IT deploys CLI policy files:

```sh
ai-kit managed-settings --out <empty folder> [--managed-hooks-only] [--managed-mcp-only]
```

| Option | Adds |
| --- | --- |
| (none) | deny rules on the kit's and the CLI's configuration, the guardrails on by default plus IT's `locked`, a sandbox requirement where the CLI has one |
| `--managed-hooks-only` | the CLI ignores hooks from any other source |
| `--managed-mcp-only` | only the Core's MCP servers are allowed |

The generated `README.txt` says where each file goes, per system and per CLI. Windows has its own files under `windows/`, where the guardrails run through PowerShell; for a CLI whose docs do not say which shell runs a hook on Windows, that file writes no guardrail (`README.txt` names it).

## Limits

- A rule on the text of a command is defeated by an alias, a wrapper script or a program the hook does not know.
- A path or a command built at run time (a variable, `base64`, `eval`, a script written then run) is not seen: the hook reads the text it is given, before it runs.
- A tool renamed or added by a CLI release is matched only once the kit's matchers name it; `doctor` probes each guardrail, the weekly drift check reads each CLI's help.
- A guardrail calls a script and a Python under your home folder; a hook that cannot start blocks nothing.
- Real access limits come from rights on the data and systems (IAM), not from the agent's instructions.
