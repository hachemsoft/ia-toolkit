# Getting started

With this page you install AI Kit, start your first session, join a Team, stay up to date, go back to the previous configuration, and uninstall. Concepts: [architecture](architecture.md).

## 1. Install

You need Python 3.11 or newer with its standard `venv` and `pip` modules, usable by your standard account. No administrator rights.

| From | Windows | macOS (and Linux) |
| --- | --- | --- |
| the release ZIP | extract `ai-kit-<version>.zip`, double-click `Installer.cmd` | extract the ZIP, open Terminal, run `sh scripts/bootstrap.sh` from the extracted folder |
| a Git clone | `Installer.cmd` in the clone | `sh scripts/bootstrap.sh` in the clone |

The launcher (`scripts/launcher.py`):

1. checks Python, then creates the kit's private environment, `~/.ai-kit/runtime/venv`;
2. installs the kit there: from the ZIP's `wheels/` folder only (no download), or, from a clone, through the package index pip is already configured for;
3. runs `ai-kit init` when you give no action.

On macOS, `sh scripts/bootstrap.sh` reads the script instead of opening it as an application, so there is no security prompt to bypass.

## What `init` asks and does

| Step | What happens |
| --- | --- |
| Identity | at a terminal: "Detected identity: … Press Enter to confirm, or type your email". Without a terminal, use `--user <email>`. A later `init` proposes the identity already recorded. The identity is declarative: it grants no rights. |
| CLIs | the ones recorded by a previous run, else the ones present on the machine. Choose with `--target` (`auto`, `gemini`, `agy`, `codex`, `claude`, `both`, `all`). A CLI installed later: `ai-kit status` names it, `ai-kit init --target auto` configures the CLIs present. |
| Content | a first install from the ZIP activates the Core it ships (`core/ai-kit-core.bundle`), offline. With a Core repository set (`[core] repo`, or IT's `enterprise.core`), `init` syncs it. From a clone without one, the clone's own content is installed. |
| First use of a Core you set yourself | the URL, tag and commit are shown, and you confirm in a terminal. |
| Files | skills, commands and agents for each CLI; the context layers and your `USER.md` in `~/.ai-kit/context`; guardrail scripts in `~/.ai-kit/hooks`; your `~/.ai-kit/aikit.toml`, created once. |
| `ai-kit` command | added to your own PATH (default yes the first time; `--command-on-path no` to skip). Open a new terminal to use it. |

`init` never calls a model. Every run that changes files keeps a backup in `~/.ai-kit/backups`. Run `init` again at any time: it checks and re-applies. `--dry-run` shows what would change.

## 2. First session

1. Open a terminal in your repository and start your CLI.
2. Type `/guide where do I start?` (`$guide` in the CLI that uses `$` for skills; see [CLI pages](cli/matrice.md)).
3. Tell the agent about you: `ai-kit user edit` opens `~/.ai-kit/context/USER.md` in your text editor, or type `/me` in the CLI (the first session offers it while the file is still the default one). Start a new session afterwards.
4. Check the installation: `ai-kit doctor` (local checks, no model call). `ai-kit doctor --live` makes one real call to the model, which your provider may bill.

## 3. Work one command per step

What is installed: the Core's default selection for everyone; a Team turns on more for its members; you add or remove with `extra_*` and `disabled_*` in your `aikit.toml` ([configuration](configuration.md)).

<!-- selection-table:start -->
| | Commands | Skills | Agents |
| --- | --- | --- | --- |
| **Core default** (installed for everyone) | `/intent` `/spec` `/build` `/test` `/review` `/ship` `/diagnose` `/me` `/guide` `/friction` `/learn` `/explain` `/retro` `/research` | analysis code-review diagnosing-bugs domain-modeling grill-with-docs grilling implement init-project-context investigation mr retrospective routing setup-workflow tdd teach to-spec wait-what writing-for-agents zoom-out | doubter repo-investigator verifier code-reviewer |
| **Optional** (a Team's `[defaults]`, or `extra_*`) | `/design` `/map` `/triage` `/ask` `/handoff` `/wizard` `/audit` | bigquery-cost-review bigquery-query-review dbt-model-change incremental-replay kpi-definition perimeter-brief sql-review architecture-decision codebase-design grill-me handover implement-spec improve-codebase-architecture manual-steps prototype ticket-sorting to-questionnaire to-tickets wayfinder workflow-guide write-a-skill writing-great-skills java-change python-js-change infra-change | dbt-reviewer sql-reviewer architecture-reviewer security-reviewer infra-reviewer |
<!-- selection-table:end -->

`00_KIT.md` in `~/.ai-kit/context` lists what your installation has. The flow: [workflow](commands.md); the tools: [tools](commands.md).

## Run the kit

| You are | Run |
| --- | --- |
| anywhere, after `init` | `ai-kit <action>` |
| in the kit folder, Windows | `Installer.cmd <action>` |
| in the kit folder, macOS | `sh scripts/bootstrap.sh <action>` |

`ai-kit --help` lists the actions; `ai-kit` alone shows the status.

## Join a Team

A Team adds its skills, agents, context and MCP servers on top of the Core ([repositories](repositories.md#team-repository)).

```sh
ai-kit team use reporting --url https://git.example.org/teams/reporting.git   # first time
ai-kit team use reporting                                                     # later, or a known Team
ai-kit team list                                                              # known Teams, * marks the active one
ai-kit team use none                                                          # leave the Team (its cache is kept)
```

## Stay up to date

| Command | Does | Network |
| --- | --- | --- |
| `ai-kit sync` | installs the highest stable tag of your Core and your Team | yes |
| `ai-kit sync --dry-run` | shows what would change, writes nothing | yes |
| `ai-kit sync --offline` | re-applies the locked Core and Team from the cache | no |
| `ai-kit sync --from-bundle <file>` | the Core from a Git bundle file, such as `core/ai-kit-core.bundle` of a newer ZIP | no |
| `ai-kit status` | what is active, and whether a newer tag was seen at the last sync | no |

`sync` needs a Core repository: `[core] repo` in your `aikit.toml`, or `enterprise.core` set by IT. A new engine version comes as a new ZIP (or `git pull` in a clone): run its installer the same way.

## Go back

`ai-kit rollback` returns to the previous configuration recorded in `~/.ai-kit/lock.toml` (Core and Team). A second `rollback` comes back. A commit IT revoked, or an origin it no longer allows, is never reactivated.

## Uninstall

```sh
ai-kit uninstall --dry-run     # what would be removed
ai-kit uninstall               # asks for confirmation (--yes without a terminal)
sh scripts/bootstrap.sh uninstall --remove-runtime --yes   # also removes the private environment
```

Removed: the files the kit installed and did not see changed, its entries in the CLIs' settings, the `ai-kit` command. Kept: `USER.md`, `aikit.toml`, `lock.toml`, the source cache, backups, frictions, `~/.ai-kit/learning`. A file you edited is kept and named.

## Workstation commitments

| Commitment | How |
| --- | --- |
| No administrator rights | everything is written under your home folder: `~/.ai-kit` and the CLIs' folders |
| No system change | only the `ai-kit` command touches your own PATH (a marked block in your shell startup file, or your user PATH on Windows), removed by uninstall |
| Nothing downloaded from the ZIP | pip installs from `wheels/` with `--no-index` |
| No model call | only `doctor --live`, on request; `AI_KIT_NO_LIVE=1` refuses it |
| No false success | a failed or interrupted runtime install is detected and started again; one run at a time |
| Python missing, too old or blocked | the launcher says which, and what to ask IT |

What IT may provide: Python 3.11+ with `venv` and `pip`; the CLI and its sign-in; Git 2.29+ for `sync` and `team use`; network access to the model and to the Git host.
