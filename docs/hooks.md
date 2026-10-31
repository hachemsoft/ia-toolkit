# Guardrails

A skill is an advisory control: it makes a violation rare. A guardrail is a script the CLI runs before some of its tool calls: it prevents certain mistakes, only in the forms and tools it recognises, and it is not a sandbox. The kit ships two. `protected-paths` is on by default: it keeps the agent from changing the configuration of the kit and of the CLIs. `dbt-prod-guard` is off by default. Both are set in `~/.ai-kit/overrides.json` (`false` turns one off):

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

```json
{
  "hooks": {
    "dbt-prod-guard": true,
    "protected-paths": true
  }
}
```

Then `update`. The scripts are installed once, in `~/.ai-kit/hooks/`, and declared to each CLI in the form it reads ([matrix](cli/matrice.md)); your own hooks are kept. The same scripts understand the tool call of each supported CLI. `doctor` shows the active guardrails. Hooks run with the kit's own Python (the private environment `~/.ai-kit/runtime/venv` when installed through the installer), isolated with `-I`: the extracted kit folder can be deleted.

## `dbt-prod-guard`

Blocks any `dbt` shell command (also `./dbt`, `/path/dbt`, `dbt.exe`, any case, and inside `sh -c "…"`) whose target is `prod`, `production` or `prd`, written `--target prod`, `--target=prod`, `-t prod`, `-tprod`, with or without quotes, or `DBT_TARGET=prod`. Change the list with the `AI_KIT_PROD_TARGETS` variable, comma-separated. A target the shell only resolves when the command runs (`--target $T`, `$(…)`, backticks, glued quotes such as `pr""od`) is blocked too: the kit cannot tell whether it is production, so the agent must write the target in plain text. An authorized person can export `AI_KIT_ALLOW_PROD=1` in the shell that starts the CLI; the hook then lets the command through and says so. The variable is ignored when it comes from a `.env` file the CLI loads (a `.env` in the repo or its parents, or the CLI's own `.env`), since the agent could write it.

The refusal goes back to the agent as a tool error with the kit's message, which redirects it to the development target declared in `AGENTS.md`.

Without `--target` or `DBT_TARGET`, it reads the default target in `profiles.yml` (`--profiles-dir`, then `DBT_PROFILES_DIR`, then the repo, then `~/.dbt`) and blocks if it is production, saying so. Minimal parsing without PyYAML: indented `target:` lines under a profile. With several profiles in the file, the hook may block too much; `AI_KIT_ALLOW_PROD=1` stays the escape hatch.

## `protected-paths`

Blocks an agent tool from writing a file under the patterns listed in `<repo>/.ai-kit/protected-paths`, one glob pattern per line, comments with `#`:

```
# Generated output and frozen contracts
target/**
models/legacy/**
dbt_project.yml
*.lock
```

Without this file, only the configuration below is protected. The old location `<repo>/.gemini/protected-paths` is still read as well; `.ai-kit/` is neutral and valid for all CLIs. Version the file with the repo; it is where the paths that `AGENTS.md` declares under "Things the agent gets wrong: never edit …" belong. The guardrail reads the file in the folder where the agent starts and in each parent folder up to the repo root, each relative to its own folder: in a monorepo, the root's protected paths also apply from a zone. Matching ignores case (`TARGET/x.sql` is protected by `target/**`) and respects folder boundaries (`targets/x.sql` is not). On Windows, a file on a different drive from the repo is outside the patterns, so it is allowed.

Whatever the repo declares, the guardrail always blocks writes to the configuration of the kit and of the CLIs, so that an agent cannot switch off its own guardrails. It sees the CLI's write tools and simple shell commands that write to those files (redirection `>`, `tee`, `sed -i`, `cp`, `mv`, `rm`, `chmod`, and their PowerShell equivalents); reading them (`cat`, `grep`) stays allowed. The protected files: `~/.ai-kit/overrides.json`, `state.json`, `hooks/`, `bin/`, `backups/`, `runtime/` (the kit's private Python environment) and the kit layers `00`, `10` and `20`, wherever they are installed (`~/.ai-kit/context/` or the CLI's folder, see the [matrix](cli/matrice.md)); the settings, `.env`, plugin and configuration files the kit manages for each CLI (listed on each CLI's page, see the [matrix](cli/matrice.md)); and the repo's own `.ai-kit/protected-paths`. Your `30_USER.md` and `~/.ai-kit/learn/` stay writable. Symbolic links are resolved: a link to a protected folder is that folder.

## Checking that guardrails run

Five different facts, never merged: the guardrail is **present** (its Python and script exist), **configured** (declared in the CLI's settings), passes a **synthetic test** (run directly on a case it must block, `dbt run --target prod` or a write to `~/.ai-kit/overrides.json`; `[Check]` if it does not block), is **approved** where the CLI asks for it, and is **invoked** by the CLI; `doctor` reports the first four. A synthetic test proves the script works, not that the CLI calls it; invocation by the CLI is only seen in a real session. For a CLI that runs hooks only after approval, `doctor` reports `[Check]` when no approval is recorded at all, and "approval not verifiable automatically" otherwise: the CLI records approvals with a hash the kit cannot check, possibly for other hooks, so a record is never reported as `[OK]` (details on the CLI's page). Guardrails run with `python -I`, which ignores `PYTHON*` variables and the current folder.

## Limits

- **Comfort, not a security barrier.** The guardrails stop an honest mistake. They do not stop an agent that is determined or misled by planted content: a `make deploy`, a project script, a shell write to a path the repo protects (`echo … >`, `sed -i`: in shell commands only the kit's and the CLIs' configuration is checked), or a command in a form the script does not parse is outside what it can see. The real barriers are the CLI's own sandbox and permissions, the rights of the account, and keeping production credentials off workstations (production dbt profiles served by CI only).

- Hooks only cover actions that go through the CLI's tools. A script run outside the CLI is not covered.
- They protect one workstation. An organization's non-negotiable rules belong to policies administered on the platform side, not to the kit.
- A hook that crashes lets the action through and does not interrupt the CLI: the scripts always return JSON, even on invalid input.

## Add a guardrail

A Python script in `runtime/hooks/` (shared by all CLIs), an entry in `hooks.json` (event, matcher, script, description), tests in `tests/test_hooks.py` that feed it the input JSON of each supported CLI, and a section here.
