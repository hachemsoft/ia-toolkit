# AI Kit

[![Tests](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml/badge.svg)](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml)
[![Version](https://img.shields.io/github/v/tag/hachemsoft/ia-toolkit?label=version)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.14-blue)](docs/installer.md)
[![Platforms](https://img.shields.io/badge/platforms-Mac%20%7C%20Windows%20%7C%20Linux-informational)](docs/getting-started.md)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A foundation for working with a coding agent as a team, on Mac and Windows. It configures the agent CLIs you choose (**Gemini CLI**, **Antigravity CLI**, **Codex CLI** and **Claude Code**) with the same content: layered context, a command-based workflow, domain playbooks, review agents and guardrails. Technical and domain context stays in each repo.

## Getting started

1. **Install**: download `ai-kit-<version>.zip` from the [Releases](https://github.com/hachemsoft/ia-toolkit/releases) page and extract it, for example into Documents.
   - **Windows**: double-click `Installer.cmd`.
   - **Mac**: open Terminal, type `sh ` (with a space), drag the `scripts/bootstrap.sh` file of the extracted folder into the window, press Enter.

   The installer first sets up its own private Python environment in your home folder (`.ai-kit/runtime`), from the files of the ZIP: no download, no administrator rights, nothing to activate. Then a short guided screen: the CLIs you use (found or not on this workstation), the profile closest to your job (if in doubt, **General**), optional adjustments, and a summary of what will change before **Install**. Arrow keys and Space choose; Ctrl+C leaves without changing your configuration.
2. **Check**: installation ends with a summary: what is ready, which CLI is found or missing, which data connections are configured, and your next step. Installation never calls the model, so the summary says "connection not verified"; `doctor --live` checks the connection on request, with a real call your provider may bill.
3. **Use**: open your repo (`cd` into it), start your CLI (`gemini`, `agy`, `codex` or `claude`) and ask in plain words. Four everyday uses:

   | You say | Shortcut |
   | --- | --- |
   | "Explain how orders are validated in this repo" | `/explain` |
   | "Make the export skip archived customers" | `/build` |
   | "The nightly job fails since Monday with this error: …" | `/diagnose` |
   | "Review my changes before I open the merge request" (committed or not) | `/review` |

   Commands are shortcuts to the same steps; `/guide I need to …` tells you which one fits (`$` instead of `/` in Codex). Nothing to set up before a first task; the agent offers to prepare the repo's context (`AGENTS.md`) when it becomes useful. More: [getting started › Work](docs/getting-started.md#3-work-one-command-per-step).
4. **Troubleshooting** ([how to open a terminal in the kit folder](docs/getting-started.md#run-the-kit)): run the installer again and choose **Check the installation**, or `sh scripts/bootstrap.sh doctor` (Mac) / `Installer.cmd doctor` (Windows) from the kit folder. Add `--live` only to check the connection to the model: it makes a real call, which your provider may bill. Then the [Troubleshooting](docs/troubleshooting.md) page.

Requirements: Python 3.9 or later (3.11 recommended) with its standard `venv` and `pip` modules, and your CLI, provided or approved by your company. The kit installs its own libraries (the terminal interface) in its private environment only: your Python, PATH, shell and security settings are not changed, and no network is needed except to talk to the model. If something is missing or blocked, the message says what to ask IT. The CLI, its authentication and the model come from your organization's procedure and are set in the CLI; the kit does not configure them. The full step-by-step guide: [getting started](docs/getting-started.md). For IT and pilots: [validation on enterprise workstations](docs/validation.md).

**Update**: download and extract the new ZIP, then run its installer the same way. It keeps your CLIs, profile, team, choices, `overrides.json` and `30_USER.md`; the old folder can be deleted, nothing points back to it. Running the installer again also offers **Update**, **Change my choices**, **Check**, **Open my personal context** and **Uninstall**. In a git clone, `update` fetches the new version (`git pull --ff-only`, never over local changes), reinstalls the package, then applies the configuration, and says which step did not work if one fails.

**Uninstall**: run the installer and choose **Uninstall**, or `uninstall --dry-run` to see the list first, `uninstall --yes` for automation, `--remove-runtime` to also remove the private environment. Only what the kit installed goes; your personal context, `overrides.json`, backups and the CLIs' own settings stay.

## Profiles

| Profile | For | Adds to the base |
| --- | --- | --- |
| **General** | any development role | — (workflow, tools, code review) |
| **Java Developer** | Maven or Gradle, Spring, JUnit | `java-change` playbook, security review |
| **DevOps** | Terraform, Kubernetes, Helm, CI/CD | `infra-change` playbook, infrastructure and security reviews |
| **Architect** | architecture decisions, design | `architecture-decision` playbook (ADR), architecture review |
| **Data Analyst** | SQL, dbt, BigQuery, KPIs | SQL, dbt, BigQuery and KPI playbooks, SQL and dbt reviews |
| **Data Developer** | the same, plus Python and JavaScript | the same, plus `python-js-change` and code review |

A profile is a starting point: the installer lets you add or remove a playbook, a command or an agent without editing any file. For example, in the **Data Analyst** profile:

| You say | What happens |
| --- | --- |
| "My number differs from the business figure" | `/diagnose`: proven cause, fix, regression test |
| "I need to change a dbt model" | `/build`, with `/intent` first when the need is fuzzy |
| "Check this query and its joins" | no command needed: the SQL playbook applies |
| "Review my changes before the merge request" | `/review` |

Commands and agents installed per profile: [getting started](docs/getting-started.md#3-work-one-command-per-step). Everything can be adjusted per person in `~/.ai-kit/overrides.json` (a skill, command or agent from another profile, guardrails, MCP servers): [customization](docs/customization.md).

## What it is

A **framework** first: the kit installs a base on the workstation that decides nothing on the team's behalf. It sets up context layers (company practices, team practices, personal preferences), read before the repo context. It provides profiles, agents, guardrails, an overrides file (overrides.json), a usage review and evals. It is tooling and precedence rules, not a procedure.

Within this framework, a **workflow**: one command per step of the development cycle (`/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`) and a chain of artifacts (`intent.md`, `spec.md`, `plan.md`, review findings, merge request (MR) description). Ceremony matches the stakes, in three levels the agent states on the first line of its reply (`Level: quick`, `standard` or `full`): a small local change is done and checked with no document, a small feature gets a short alignment then test-first, and only a large, fuzzy or production change runs intent, spec, plan and your acceptance before code. These are prompts and skills the model follows, plus two deterministic guardrails for what must be guaranteed. See [workflow](docs/workflow.md).

Alongside, **tools** (`/guide`, `/learn`, `/explain`, `/retro`, `/friction`) and **domain playbooks** activated when the task calls for them; yours are added the same way. See [tools](docs/tools.md) and [adding a skill](docs/extending.md).

The project's four requirements: simple installation, Mac and Windows, extension without touching kit files, and several CLIs, each with its own adapter.

## Supported CLIs

| CLI | State | Commands |
| --- | --- | --- |
| Gemini CLI | ✅ | `/guide` |
| Antigravity CLI (`agy`) | ✅ | `/guide` |
| Codex CLI | ✅ | `$guide` |
| Claude Code | ✅ | `/guide` |

Verified versions, where each file is placed, and what differs between CLIs: [CLI matrix](docs/cli/matrice.md).

## Documentation

- **Use**: [getting started](docs/getting-started.md), [workflow](docs/workflow.md), [tools](docs/tools.md), [agents](docs/agents.md), [project layer](docs/project-context.md), [Troubleshooting](docs/troubleshooting.md).
- **Customize**: [customization](docs/customization.md), [add or replace a skill](docs/extending.md), [guardrails](docs/hooks.md), [MCP](docs/mcp.md), [identity](docs/identity.md).
- **Per CLI**: [matrix](docs/cli/matrice.md), [Gemini CLI](docs/cli/gemini.md), [Antigravity CLI](docs/cli/agy.md), [Codex CLI](docs/cli/codex.md), [Claude Code](docs/cli/claude-code.md), [moving from Gemini to agy](docs/cli/gemini-to-agy.md).
- **Deploy and maintain**: [the installer](docs/installer.md), [validation on enterprise workstations](docs/validation.md), [compliance and governance](docs/compliance.md), [contributing](docs/contributing.md), [command format](docs/format.md), [skills reference](docs/skills-reference.md), [evals](docs/evals.md), [usage review](docs/usage-review.md), [pilot](docs/pilot.md), [sources](docs/sources.md), [changelog](CHANGELOG.md).

## Credits and inspiration

- **Workflow**: the six steps, each closed by an artifact that the next one reads, come from Anthropic's ["The AI-native SDLC playbook"](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).
- **Base skills**: taken and adapted from [mattpocock/skills](https://github.com/mattpocock/skills), by Matt Pocock, under the MIT licence: interview before building, glossary and ADRs, small composable skills.
- **Discipline mechanisms**: rationalization tables ("too simple for a test") and adversarial review by a doubter agent come from [agent-skills](https://github.com/addyosmani/agent-skills), by Addy Osmani.
- **Other sources**: [pstack](https://github.com/cursor/plugins/tree/main/pstack), and Switch Dimension's comparison of these skill packs, the source of the "ceremony matches the stakes" rule.

Details in [sources](docs/sources.md).

## Licence

MIT, see [LICENSE](LICENSE). Base skills taken from mattpocock/skills keep their own MIT licence, in `skills/LICENSE-UPSTREAM-MIT`.
