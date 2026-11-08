# Guardrails

A skill is an advisory control: it makes a violation rare. A guardrail is a script the CLI runs before some of its tool calls: it prevents certain mistakes, only in the forms and tools it recognises, and it is not a sandbox. The kit ships two, plus one hook that is not a guardrail: [`whats-new`](#whats-new), which runs at session start and tells the agent what is new. `protected-paths` is on by default: it keeps the agent from changing the configuration of the kit and of the CLIs. `dbt-prod-guard` is off by default. Both are set in `~/.ai-kit/overrides.toml` (`false` turns one off):

```toml
[hooks]
dbt-prod-guard = true
protected-paths = true
```

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

Then `update`. The scripts are installed once, in `~/.ai-kit/hooks/`, and declared to each CLI in the form it reads ([matrix](cli/matrice.md)); your own hooks are kept. The same scripts understand the tool call of each supported CLI. `doctor` shows the active guardrails. Hooks run with the kit's own Python (the private environment `~/.ai-kit/runtime/venv` when installed through the installer), isolated with `-I`: they keep working if the kit folder is deleted, though the `ai-kit` command does not.

## `dbt-prod-guard`

Blocks any `dbt` shell command (also `./dbt`, `/path/dbt`, `dbt.exe`, any case, and inside `sh -c "…"`) whose target is `prod`, `production` or `prd`, written `--target prod`, `--target=prod`, `-t prod`, `-tprod`, with or without quotes, or `DBT_TARGET=prod`. Change the list with the `AI_KIT_PROD_TARGETS` variable, comma-separated. A target the shell only resolves when the command runs (`--target $T`, `$(…)`, backticks, glued quotes such as `pr""od`) is blocked too: the kit cannot tell whether it is production, so the agent must write the target in plain text. An authorized person can export `AI_KIT_ALLOW_PROD=1` in the shell that starts the CLI; the hook then lets the command through and says so. The variable is ignored when it comes from a `.env` file the CLI loads (a `.env` in the repo or its parents, or the CLI's own `.env`), since the agent could write it.

The refusal goes back to the agent as a tool error with the kit's message, which redirects it to the development target declared in `AGENTS.md`.

Without `--target` or `DBT_TARGET`, it reads the default target in `profiles.yml` (`--profiles-dir`, then `DBT_PROFILES_DIR`, then the repo, then `~/.dbt`) and blocks if it is production, saying so. Minimal parsing without PyYAML: indented `target:` lines under a profile. With several profiles in the file, the hook may block too much; `AI_KIT_ALLOW_PROD=1` stays the escape hatch.

## `protected-paths`

Blocks an agent's write tool from writing a file under the patterns listed in `<repo>/.ai-kit/protected-paths`, one glob pattern per line, comments with `#`. These patterns do not apply to shell commands yet: `rm target/a.sql` is not refused.

```
# Generated output and frozen contracts
target/**
models/legacy/**
dbt_project.yml
*.lock
```

Without this file, only the configuration below is protected. The old location `<repo>/.gemini/protected-paths` is still read as well; `.ai-kit/` is neutral and valid for all CLIs. Version the file with the repo; it is where the paths that `AGENTS.md` declares under "Things the agent gets wrong: never edit …" belong. The guardrail reads the file in the folder where the agent starts and in each parent folder up to the repo root, each relative to its own folder: in a monorepo, the root's protected paths also apply from a zone. Matching ignores case (`TARGET/x.sql` is protected by `target/**`) and respects folder boundaries (`targets/x.sql` is not). On Windows, a file on a different drive from the repo is outside the patterns, so it is allowed.

Whatever the repo declares, the guardrail blocks the agent's usual writes to the configuration of the kit and of the CLIs, to make it harder for an honest mistake to switch off a guardrail. Write tools are checked on the file they write; on Claude Code, MCP tools too (`mcp__…`, since 0.51.1: before, a server's write tool went around the guardrail). A shell command (Bash, PowerShell) that names a protected file in plain text is allowed only when every program it runs only reads: `cat`, `grep`, `head`, `ls`, `diff`, `jq`, `sed`, `awk`, `sort`, `uniq`, `xxd`, `tree` and `yq` without the options that make them write a file (in-place editing, a simple `w` command), `git` in read-only subcommands without `--output`, `find` without `-delete`, `-exec` or `-fprint…`, `cp` with the protected file as the source and no configuration folder as the destination, and their PowerShell equivalents (`Get-Content`, `Select-String`…). Anything else naming a protected file in plain text is refused (`python -c`, `perl -pi`, `node -e`, `eval`, a redirection, a variable holding the whole path), and so is a `cd` into a configuration folder or a wildcard inside one. [What it does not catch](#limits) is listed below. Paths are compared as the shell resolves them (quotes, `//`, `/./`, case). The text of a heredoc given to a program that is not a shell (`python3 - <<EOF`) is data, not commands. The protected files: `~/.ai-kit/overrides.toml`, `state.json`, `hooks/`, `bin/`, `backups/`, `runtime/` (the kit's private Python environment) and the kit layers `00`, `10` and `20` in `~/.ai-kit/context/`, and their copies where a CLI gets one (see the [matrix](cli/matrice.md)); the settings, `.env`, plugin and configuration files the kit manages for each CLI (listed on each CLI's page, see the [matrix](cli/matrice.md)); every file the kit installed (skills, commands, agents: an instruction slipped into one would load in every repo); in each repo, its `.ai-kit/protected-paths` and the settings that could turn hooks off (`.claude/settings.json`, `.claude/settings.local.json`, `.gemini/settings.json`, `.gemini/.env`, `.codex/config.toml`), and a `.env` that would set the kit's variables or `DBT_TARGET`. Since 0.51.1, also: the kit folder the installation came from (`state.json` `kit_dir`, the source of the next `update` and of the session hook's remote read): its `.git/config` and `.git/hooks` always, including `git config` and `git remote add|set-url|…` aimed at it, and the rest of it when the session starts outside that folder (a maintainer still works on the kit with an agent started inside it); and git's own configuration, `~/.gitconfig` and `~/.config/git/config`, with `git config --global|--system|--file` refused for the keys that redirect a fetch or run a program (`url.*`, `credential.*`, `core.*`, `include*`), `user.*` left free. Before 0.51.1 none of these was protected. Since 0.52.0 the agent also may not run the kit's subcommands that change the installation or bill a model call (`ai-kit setup`, `update`, `uninstall`, `new`, `doctor --live`, `friction --mode <value>`, also through `python -m ai_kit` or the launchers): it tells the person the command instead; reading subcommands (`doctor`, `usage`, `news`, friction logging, `--version`) stay allowed. Like every rule on the text of a command, an alias or a wrapper script defeats it. The repo is found from the file written, not only from the folder the CLI started in. Your `30_USER.md` and `~/.ai-kit/learning/` stay writable. Symbolic links are resolved: a link to a protected folder is that folder.

## `whats-new`

Not a guardrail: a hook on the start of a session (`SessionStart`, new session or resume) that puts in the agent's context, once, what is new, so that the agent says it in its first reply, one line per item, details on request:

- the CHANGELOG section of the version just installed (the kit folder's `CHANGELOG.md`);
- the entries of the kit repository's [`NEWS.md`](../NEWS.md) aimed at this profile and team (a new skill, a training, a tip; an organization writes its own in its copy of the repository);
- a newer kit version on the repository's `origin/main`. The agent proposes it; on a yes it tells you to run `ai-kit update` in a terminal and says what will change; on a no it runs `ai-kit news --later` and the version is not proposed again (the next one will be). The hook never runs the update, nor does the agent ([ADR 0012](adr/0012-a-session-hook-may-read-the-kit-remote-never-write-never-send.md)).

**The remote text reaches the agent's context with no human action.** In a clone, what is pushed to that branch can be read the next day, unreviewed: the same trust as your repository's write access, and `update` is not needed for it. Since 0.51.1 the remote `VERSION` is accepted only as `X.Y.Z`, and git runs in the clone without its `core.fsmonitor` or hooks; `NEWS.md` is still read as it is. Set `check_remote = false` if that is not acceptable. A release ZIP has no remote read.

The remote read happens at most once a day, only when the kit folder (`state.json` `kit_dir`, recorded by `update`) is a git clone with an `origin`: `git fetch` of origin's default branch (else the branch the clone tracks, else `main`) with a 5 s timeout, the process tree killed at the timeout and no prompt from git, ssh or a credential helper, then `VERSION` and `NEWS.md` read on that remote branch; the working tree is never touched (the fetch writes only `.git/FETCH_HEAD` and the remote-tracking ref), nothing is sent, and every failure is silent, recorded as a category only (`network`, `auth`, `no ref`, `timeout`), never as git's message, which could name the remote (`doctor` shows the last read, its result and what waits for the next session). Two sessions starting the same minute can both read once: the marker is written atomically, so neither sees a half-written file. Installed from a ZIP, the hook announces the installed version and the shipped `NEWS.md` only. It always answers `{}` or a JSON context in the form of the CLI that asked (`additionalContext`, or agy's `injectSteps`), exit 0: a session is never blocked. What it writes: `~/.ai-kit/news.json` (versions and entries announced, declined version, last read), nothing else.

Settings, in `overrides.toml` or the organization's `defaults`: `[hooks] whats-new = false` turns the hook off; `[news] check_remote = false` keeps it local (no fetch, no version proposed). In a terminal: `ai-kit news --list` (what was announced, last read), `ai-kit news --check` (read the remote now, the same read as the hook's; the agent may run it when you ask), `ai-kit news --later`. Codex asks to trust the hook as it does for the guardrails, and asks again when its command changes after an update; Gemini CLI warns once about a changed hook: answer once, never bypass it. Each CLI's page says where the hook is declared and in which form the script answers it ([matrix](cli/matrice.md)).

Writing an announcement: one section of `NEWS.md`, `## <YYYY-MM-DD> <id> : <title>`, optional `profiles:`, `teams:`, `until:` lines, then the text; `python3 scripts/check_news.py` refuses a malformed file and the CI runs it. An entry is shown once per person; `until` keeps it from people who install later.

## Checking that guardrails run

Five different facts, never merged: the guardrail is **present** (its Python and script exist), **configured** (declared in the CLI's settings), passes a **synthetic test** (run directly on a case it must block, `dbt run --target prod` or a write to `~/.ai-kit/overrides.toml`; `[Check]` if it does not block), is **approved** where the CLI asks for it, and is **invoked** by the CLI; `doctor` reports the first four. A synthetic test proves the script works, not that the CLI calls it; invocation by the CLI is only seen in a real session. For a CLI that runs hooks only after approval, `doctor` reports `[Check]` when no approval is recorded at all, and "approval not verifiable automatically" otherwise: the CLI records approvals with a hash the kit cannot check, possibly for other hooks, so a record is never reported as `[OK]` (details on the CLI's page).

## Limits

- **An anti-error default, not a sandbox.** The guardrails decide on the text of one tool call, before it runs. They catch the usual forms of an honest mistake. They are not a barrier against a person or against an agent following an injected instruction: where a rule must hold, use the [settings IT deploys](#rules-it-can-enforce), the CLI's sandbox and the rights of the account.
- **Not caught today**, though the call is in plain text: a configuration folder named alone, with the file built from a variable or an expansion (`p=$HOME/.ai-kit; … "$p/…"`); `find` with `-delete` or `-exec`, or `sort -o`, on a configuration folder; a path through `..`; some `sed` and `awk` scripts that write.
- **Outside the guarantee by design:** a name that must be reassembled (pieces, base64, `eval`, `$(…)`), a variable set outside the call, a script or heredoc given to another language, a project script (`make deploy`), a program started outside the agent, a tool the CLI renames.
- **The kit's own commands are allowed:** `ai-kit uninstall --yes` removes the guardrails, as a person may. So is writing to `30_USER.md`, which `/me` needs and every session loads: an instruction written there stays across repos.
- **Files not protected:** a repo's `.git/hooks`, `.mcp.json`, `.claude/hooks/`; skills and commands of your own in the CLIs' folders; your shell startup files.
- They protect one workstation. An organization's non-negotiable rules belong to policies administered on the platform side, not to the kit.
- **A hook that cannot run decides nothing.** The documentation of at least two of the CLIs says that a hook failing to start, or exiting with any code but 2, does not block the action. This happens when the Python of the private environment is gone (a conda environment removed, a Python upgrade) until the next run of the installer, when a policy blocks it, and on invalid input: the scripts answer `{}`.

## Rules IT can enforce

The kit installs per person, so a person (and an agent with shell access) can change what it wrote: nothing the kit installs is a lock. For rules that must hold whatever happens, IT deploys the managed settings of each CLI (MDM, Group Policy or the vendor's admin console); the CLI applies them above the person's settings. `organization.toml` `locked_hooks` keeps a guardrail on against a team's or a person's settings: it is a default, and a person who edits the kit folder lifts it.

| What the generated files hold | Does it hold on the workstation? |
| --- | --- |
| Keys the CLI enforces: sandbox and approvals on Codex, YOLO mode off on Gemini CLI, the MCP allowlist, Claude Code's `Edit` deny on write tools | Yes once deployed, as far as the vendor enforces them; `Edit` deny does not cover shell commands |
| The guardrails as managed hooks | **Not as a lock.** They call a script and a Python under `$HOME`, which the person and a shell-capable agent can change, and a hook that cannot start blocks nothing. **On Windows the generated command points to `venv/bin/python`, which does not exist there: do not deploy these hooks on Windows** |

The kit writes these files for you, from `organization.toml`: `managed-settings --out <empty folder>`, with a `README.txt` saying where each one goes. The guardrails are those of `locked_hooks`, or the ones on by default when it is empty. Nothing is installed: IT reviews and deploys them.

| File written | What it holds |
| --- | --- |
| `claude-code/managed-settings.json` | edits to the kit's and Claude Code's configuration denied; the guardrails as managed hooks; with `--managed-hooks-only`, hooks from any other source ignored; with `--managed-mcp-only`, only the MCP servers `organization.toml` defines (`allowedMcpServers` and `allowManagedMcpServersOnly`) |
| `gemini-cli/settings.json` (system settings) | the guardrails; YOLO mode off |
| `codex/requirements.toml` | sandbox and approvals kept on: the agent writes only inside its repo; with `--managed-mcp-only`, an `mcp_servers` allowlist of the same servers, by name and identity |

| CLI | Where IT deploys it | What to set |
| --- | --- | --- |
| Claude Code | `managed-settings.json` (macOS `/Library/Application Support/ClaudeCode/`, Linux `/etc/claude-code/`, Windows `C:\Program Files\ClaudeCode\`), or the admin console | `permissions.deny` on `Edit(~/.ai-kit/**)`, `Edit(~/.claude/settings.json)` and the other protected paths; the kit's hooks declared there with `allowManagedHooksOnly`; the sandbox for shell commands |
| Codex CLI | `requirements.toml` (`/etc/codex/`, Windows `%ProgramData%\OpenAI\Codex\`) or the admin console | sandbox `workspace-write` and an approval policy (`ai-kit managed-settings` writes both); it writes no managed hook for Codex: declaring the kit's hooks there is left to IT and not verified by the kit |
| Gemini CLI | system settings (`/etc/gemini-cli/settings.json`, Windows `C:\ProgramData\gemini-cli\`) | the kit's hooks, `tools.core` allowlist, `security.disableYoloMode` |
| Antigravity CLI | no central policy documented by the vendor | the kit's guardrails and each person's permissions |

Check the exact keys against your CLI's version: they change with each release.

**Lock the MCP servers.** `managed-settings --out <empty folder> --managed-mcp-only` allows only the servers `organization.toml` defines, in its defaults and its teams: a remote server by its URL, a local one by its exact command and arguments, never by its name alone. A person's own server (`[mcp.mine]`) is then refused. If `organization.toml` defines none, every MCP server is blocked, and the command says so. A server whose URL or arguments use `${VARIABLE}` may not match once expanded: try one workstation first.

| CLI | What the MCP lock writes |
| --- | --- |
| Claude Code | `allowedMcpServers` (`serverUrl` or `serverCommand` entries) with `allowManagedMcpServersOnly`, so a person cannot widen the list |
| Codex CLI | `mcp_servers` in `requirements.toml`: the name the kit installs (`ai-kit-<name>`) and its identity (URL, or executable and each argument exactly) |
| Gemini CLI | nothing: `mcp.allowed`, `mcp.excluded` and `admin.mcp.config` exist, but their docs do not say what an entry holds; the README asks IT to set them by hand |
| Antigravity CLI | nothing: no central policy documented |

## Add a guardrail

A Python script in `runtime/hooks/` (shared by all CLIs), an entry in `hooks.json` (event in the manifest's names, `BeforeTool` for a guardrail or `SessionStart`, matcher, script, description; each adapter translates them), tests in `tests/test_hooks.py` that feed it the input JSON of each supported CLI, and a section here. Only a `BeforeTool` hook is a guardrail: `locked_hooks` and `managed-settings` take no other.
