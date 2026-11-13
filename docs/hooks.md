# Guardrails

With this page you know which guardrails run, how to turn one on or off, what IT can lock, and what the agent is refused. A guardrail is a script the CLI runs before a tool call: it blocks some mistakes in the forms it recognises. It is not a sandbox. Concepts: [architecture](architecture.md).

## The list

From `runtime/hooks/hooks.json`:

| Name | Runs | Default | Blocks |
| --- | --- | --- | --- |
| `protected-paths` | before a write or shell tool | on | agent writes to the configuration of the kit and of the CLIs, and under a repo's protected paths |
| `dbt-prod-guard` | before a shell tool | off | a dbt command on a production target |
| `git-guard` | before a shell tool | off | the git commands that discard work for good, and a forced push to a main branch |
| `bq-cost-guard` | before a shell tool | off | `bq query` without a dry run or a cap on the bytes billed |
| `infra-prod-guard` | before a shell tool | off | `terraform apply` or `destroy` and the `kubectl` commands that change a cluster, on production |
| `whats-new` | at session start | on | nothing: not a guardrail, it tells the agent what is new |

The scripts are copied to `~/.ai-kit/hooks/` and declared to each CLI in its own format ([CLI pages](cli/matrice.md)). They run with the kit's private Python, isolated with `-I`. Your own hooks are kept.

The four shell guardrails (`dbt-prod-guard`, `git-guard`, `bq-cost-guard`, `infra-prod-guard`) are rules of one script, `shell-guard.py`: each CLI gets one hook, `ai-kit-shell-guard`, told which rules are on. Turning on four costs one program start per shell command, as one does. Measured on one macOS workstation: about 15 ms per guardrail script and per command, more than half of it the start of Python; not measured on Windows.

## Turning one on or off

```toml
# ~/.ai-kit/aikit.toml
[hooks]
dbt-prod-guard = true
git-guard = true
protected-paths = true
```

Then `ai-kit sync --offline`. IT decides above you in `managed.toml`:

| Key | Effect |
| --- | --- |
| `[hooks] locked = ["protected-paths"]` | stays on, whatever you write; the run says `[Info] Guardrail <name> stays on` |
| `[hooks] <guardrail> = true` or `false` | on or off for everyone; your value is ignored, and the run says so |

IT can name every guardrail of the list; `whats-new` is not one.

## `protected-paths`

Always blocks an agent's write to:

- `~/.ai-kit/`: `aikit.toml`, `lock.toml`, `sources/`, `state.json`, `hooks/`, `bin/`, `backups/`, `runtime/`, `schemas/`, `news/`, `news.json`, and the rule layers `00_`, `10_`, `20_` in `context/`;
- the CLIs' settings and instruction files the kit manages, a CLI's own permissions file the kit leaves to you ([agy](cli/agy.md)), and every file the kit installed (skills, commands, agents);
- Git's own configuration, `~/.gitconfig` and `~/.config/git/config`, and the `.git/config` and `.git/hooks` of the kit folder;
- in a repository: `.ai-kit/protected-paths` and the CLI settings files that could turn hooks off; a `.env` that sets `AI_KIT_*` or `DBT_TARGET`, written by a write tool or by a shell command.

`USER.md` and `~/.ai-kit/learning/` stay writable.

A shell command that names a protected file, or a configuration folder itself (`~/.ai-kit`, `~/.claude`…), is allowed only when every program it runs only reads (`cat`, `grep`, `ls`…): `find ~/.ai-kit -delete` is refused. A redirection to a protected file, a `cd` into a configuration folder, or that folder kept in a variable (`p=~/.ai-kit`), is refused.

**Your repo's own protected paths.** List glob patterns, one per line, `#` for comments, in `<repo>/.ai-kit/protected-paths`:

```text
target/**
models/legacy/**
*.lock
```

The file is read in the starting folder and each parent up to the repo root. Matching ignores case. The patterns apply to the agent's write tools and to its shell commands; your own terminal is never concerned.

In a shell command, the guardrail refuses a command that names a protected file and changes or deletes it:

| The agent's command | Result |
| --- | --- |
| `echo x > poetry.lock`, `… \| tee poetry.lock` | refused: a redirection to the file |
| `sed -i … poetry.lock`, `perl -pi … poetry.lock`, `truncate`, `touch`, `chmod` | refused |
| `rm`, `rmdir`, `unlink`, `mv` (either side), `cp` or `ln` to the file | refused |
| `git checkout -- poetry.lock`, `git restore`, `git rm`, `git mv`, `git clean target` | refused: they replace or delete the file |
| `Remove-Item`, `Set-Content`, `Out-File`, `del`, `move`… | refused |
| `cat`, `grep`, `ls`, `diff`, `git diff`, `git add`, `cp poetry.lock elsewhere` | runs: the file is read, not changed |
| `poetry lock`, `npm install`, `dbt run`, `terraform init` | runs: the tool that generates the file does not name it |

So a pattern protects a file against a direct change, not against the tool whose job is to write it. The programs read are a closed list; `sudo`, `xargs`, `sh -c` in front of them change nothing.

**Kit commands the agent may not run.** `ai-kit init`, `sync`, `rollback`, `uninstall`, `team use`, `doctor --live`, `friction --publish`, wherever their options are written, also through `python -m ai_kit` or a launcher (`Installer.cmd`, `bootstrap.sh`, `bootstrap.ps1`, `launcher.py`), however it is run. A launcher of a kit folder with no action installs: it is refused too. The agent tells you the command to run in a terminal. Reading commands (`status`, `doctor`, `usage`, `friction --list`) stay allowed, and so do the kit's own scripts in `~/.ai-kit/bin/`: `friction.py` for `/friction`, `weakened_tests.py` for `/review` (read-only), as long as nothing else in the command names a protected path.

The refusal reaches the agent as a tool error starting with `Blocked by the kit:`.

## `dbt-prod-guard`

Blocks a `dbt` command whose target is `prod`, `production` or `prd` (or the comma-separated list in `AI_KIT_PROD_TARGETS`), written as `--target`, `-t` or `DBT_TARGET`. Without a target, it reads the default target in `profiles.yml` (`--profiles-dir`, `DBT_PROFILES_DIR`, the repo, `~/.dbt`). A target only known at run time (`$VAR`, `$(…)`) is blocked too.

An authorised person exports `AI_KIT_ALLOW_PROD=1` in the shell that starts the CLI. The same variable in a `.env` file the agent could write is ignored.

## `git-guard`

Blocks the git commands that lose work with no way back:

| Refused | Passes |
| --- | --- |
| `git reset --hard` | `git reset`, `git reset --soft` |
| `git clean -f` (`-fd`, `-xdf`, `--force`) | `git clean -n`, `git clean --dry-run` |
| `git checkout .`, `git checkout -- .`, `git checkout -f` | `git checkout <branch>`, `git checkout -- <file>` |
| `git restore .` | `git restore <file>`, `git restore --staged .` |
| `git branch -D`, `git branch --delete --force` | `git branch -d` |
| `git worktree remove --force` (`-f`) | `git worktree remove` (git itself refuses a worktree that is not clean) |
| a forced push, or a branch deletion, on `main` or `master` (`--force`, `-f`, `+main`, `--force-with-lease`, `--delete`, `:main`) | `git push`, a forced push that names another branch |

Add main branches with `AI_KIT_PROTECTED_BRANCHES` (comma-separated, for example `develop,release`). A forced push that names no branch reads the branch checked out (`.git/HEAD`); when it cannot be read, a plain `--force` is refused and `--force-with-lease` passes. There is no permission variable: the refusal tells the agent to let you run the command. The branch protection of your Git host stays the real barrier.

## `bq-cost-guard`

Blocks `bq query` that has neither `--dry_run` nor `--maximum_bytes_billed=<bytes>`. The other `bq` commands pass. A default set in `.bigqueryrc` is not read: write the flag on the command.

## `infra-prod-guard`

Blocks `terraform apply` and `terraform destroy` (also `tofu`, `terragrunt`), and the `kubectl` commands that change a cluster (`delete`, `apply`, `replace`, `patch`, `scale`, `drain`, `edit`, `set`, `create`, `rollout restart|undo|pause|resume`), when something names production: `prod`, `production`, `prd` or the `AI_KIT_PROD_TARGETS` list, as one word of the name (`gke_project_prod_eu`, `envs/prod`, `app-prod`; not `product-api`).

| Program | What is read |
| --- | --- |
| terraform | `-chdir`, `-var-file`, `TF_WORKSPACE`, the workspace selected (`.terraform/environment`), the folder names below the repository root |
| kubectl | `--context`, `--cluster`, `-n`/`--namespace`; without `--context`, the `current-context` of the kubeconfig (`--kubeconfig`, `KUBECONFIG`, `~/.kube/config`); a context only known at run time (`$CTX`) is refused |

`plan`, `get`, `describe`, `logs`, `rollout status` pass. An environment whose name does not say production is not recognised: this guardrail catches the named case, not every production system. `helm`, `gcloud` and the cloud consoles are not covered. The one-off permission is the one of `dbt-prod-guard`: `AI_KIT_ALLOW_PROD=1` exported in the shell that starts the CLI.

## How the shell guardrails read a command

`git-guard`, `bq-cost-guard` and `infra-prod-guard` look at the programs the command runs, not at its text: each command of the line (`;`, `&&`, `|`, new lines), after `sudo`, `env`, `xargs`, inside `sh -c "…"`, `eval`, `$(…)` and backticks. A command that only talks about an action passes: `echo "git reset --hard"`, `grep -r "kubectl delete" docs`, `git commit -m "bq query"`, a heredoc written to a file. A rule that fails on a command lets it through.

## Counting refusals

Each refusal adds one line to `~/.ai-kit/refusals.jsonl`: the date and the guardrail's name, never the command. `ai-kit usage` prints the count over its window (`Guardrail refusals: 3 (protected-paths ×2, git-guard ×1)`) and puts it in its JSON report (`guardrail_refusals`). The file stays on your machine and keeps its last 1000 lines; `ai-kit doctor`'s probes are not counted. The count says how often a guardrail stepped in, not whether it was right: a refusal that was wrong is a friction (`/friction`, category guardrail).

## `whats-new`

At the start of a new or resumed session, tells the agent once, so that it says it in its first reply:

- the `CHANGELOG.md` section of the installed version;
- the entries of the content's `NEWS.md` aimed at everyone or at the active Team (`teams:`), until their `until:` date.
- an offer of `/me`, once, while `~/.ai-kit/context/USER.md` is still the one the installation created (its role line empty): the agent offers it in one line and never starts it on its own.

The changelog and the news are copies the installation writes to `~/.ai-kit/news/`: no network, no remote text. What was announced is recorded in `~/.ai-kit/news.json`. It also runs the local friction upkeep ([frictions](frictions.md)) and never blocks a session.

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
- A repo's protected paths in shell: only a file the command names is seen. A path kept in a variable (`f=poetry.lock; rm $f`), a wildcard (`rm *.lock`), a `cd target` followed by `rm a.sql`, a program outside the list or a script that writes the file all run.
- The shell guardrails do not follow a `cd`: a folder or a branch is read from where the CLI started the command (`git -C` and `terraform -chdir` are read). `$(…)` inside single quotes is read as if it ran.
- A path or a command built at run time (a variable, `base64`, `eval`, a script written then run) is not seen: the hook reads the text it is given, before it runs.
- A tool renamed or added by a CLI release is matched only once the kit's matchers name it; `doctor` probes each guardrail, the weekly drift check reads each CLI's help.
- A guardrail calls a script and a Python under your home folder; a hook that cannot start blocks nothing.
- Real access limits come from rights on the data and systems (IAM), not from the agent's instructions.
