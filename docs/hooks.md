# Guardrails

A skill is an advisory control: it makes a violation rare. A CLI hook is deterministic: it makes it nearly impossible. The kit ships two, off by default, to enable in `~/.ai-kit/overrides.json`:

```json
{
  "hooks": {
    "dbt-prod-guard": true,
    "protected-paths": true
  }
}
```

Then `update`. The scripts are installed once, in `~/.ai-kit/hooks/`, and declared to each CLI in the form it reads ([matrix](cli/matrice.md)); your own hooks are kept. The same scripts understand the tool call of each supported CLI. `doctor` shows the active guardrails. Hooks run with the Python that launched the installer.

## `dbt-prod-guard`

Blocks any `dbt` shell command (also `./dbt`, `/path/dbt`, `dbt.exe`, any case) whose target is `prod`, `production` or `prd`, written `--target prod`, `--target=prod`, `-t prod`, `-tprod`, with or without quotes, or `DBT_TARGET=prod`. Change the list with the `AI_KIT_PROD_TARGETS` variable, comma-separated. An authorized person can export `AI_KIT_ALLOW_PROD=1` in their session; the hook then lets the command through and says so.

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

Without this file, everything is allowed. The old location `<repo>/.gemini/protected-paths` is still read as well; `.ai-kit/` is neutral and valid for all CLIs. Version the file with the repo; it is where the paths that `AGENTS.md` declares under "Things the agent gets wrong: never edit …" belong. The guardrail reads the file in the folder where the agent starts and in each parent folder up to the repo root, each relative to its own folder: in a monorepo, the root's protected paths also apply from a zone. Matching ignores case (`TARGET/x.sql` is protected by `target/**`) and respects folder boundaries (`targets/x.sql` is not). On Windows, a file on a different drive from the repo is outside the patterns, so it is allowed.

## Limits

- Hooks only cover actions that go through the CLI's tools. A script run outside the CLI is not covered.
- They protect one workstation. An organization's non-negotiable rules belong to policies administered on the platform side, not to the kit.
- A hook that crashes lets the action through and does not interrupt the CLI: the scripts always return JSON, even on invalid input.

## Add a guardrail

A Python script in `runtime/hooks/` (shared by all CLIs), an entry in `hooks.json` (event, matcher, script, description), tests in `tests/test_hooks.py` that feed it the input JSON of each supported CLI, and a section here.
