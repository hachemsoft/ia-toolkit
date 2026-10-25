# AI Kit

[![Tests](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml/badge.svg)](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml)
[![Version](https://img.shields.io/github/v/tag/hachemsoft/ia-toolkit?label=version)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.14-blue)](docs/installer.md)
[![Platforms](https://img.shields.io/badge/platforms-Mac%20%7C%20Windows%20%7C%20Linux-informational)](docs/getting-started.md)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A foundation for working with a coding agent as a team, on Mac and Windows. It configures the agent CLIs present on the workstation (**Gemini CLI**, **Antigravity CLI** and **Codex CLI**) with the same content: layered context, a command-based workflow, domain playbooks, review agents and guardrails. Technical and domain context stays in each repo.

## Getting started

1. **Install**: `git clone <repository url> ai-kit` (without git: "Download ZIP" on the repository page, then extract). Open a terminal in that folder, then run `sh scripts/bootstrap.sh` (Mac) or `.\scripts\bootstrap.ps1` (Windows). Confirm your identity, then choose the profile closest to your job; if in doubt, **General**.
2. **Check**: installation ends with a real call to the model. Green means done. Otherwise, the message says what to do.
3. **Use**: open your repo (`cd` into it), start your CLI (`gemini`, `agy` or `codex`), type `/guide I need to …` (`$guide` in Codex): it tells you which command to type. The first time in a repo: "Initialize the project context".
4. **Troubleshooting**: `sh scripts/bootstrap.sh doctor --live` (Mac) or `.\scripts\bootstrap.ps1 doctor --live` (Windows), then the [Troubleshooting](docs/troubleshooting.md) page.

Requirements: Python 3.11 or later recommended; 3.9 minimum, which lets you use the Python shipped with macOS. The kit installs no dependencies. The CLI and its authentication come from your organization's procedure; if it requires a cloud project or a model, that is one line in `~/.ai-kit/overrides.json`. The full step-by-step guide: [getting started](docs/getting-started.md).

Update: `git pull` in the kit folder, then `sh scripts/bootstrap.sh update` (Windows: `.\scripts\bootstrap.ps1 update`).

## Profiles

| Profile | For | Adds to the base |
| --- | --- | --- |
| **General** | any development role | — (workflow, tools, code review) |
| **Java Developer** | Maven or Gradle, Spring, JUnit | `java-change` playbook, security review |
| **DevOps** | Terraform, Kubernetes, Helm, CI/CD | `infra-change` playbook, infrastructure and security reviews |
| **Architect** | architecture decisions, design | `architecture-decision` playbook (ADR), architecture review |
| **Data Analyst** | SQL, dbt, BigQuery, KPIs | SQL, dbt, BigQuery and KPI playbooks, SQL and dbt reviews |
| **Data Developer** | the same, plus Python and JavaScript | the same, plus `python-js-change` and code review |

Commands and agents installed per profile: [getting started](docs/getting-started.md#3-work-one-command-per-step). Everything can be adjusted per person in `~/.ai-kit/overrides.json` (a skill, command or agent from another profile, guardrails, MCP servers): [customization](docs/customization.md).

## What it is

A **framework** first: the kit installs a base on the workstation that decides nothing on the team's behalf. It sets up context layers (company practices, team practices, personal preferences), read before the repo context. It provides profiles, agents, guardrails, an overrides file (overrides.json), a usage review and evals. It is tooling and precedence rules, not a procedure.

Within this framework, a **workflow**: one command per step of the development cycle (`/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`) and a chain of artifacts (`intent.md`, `spec.md`, `plan.md`, review findings, merge request (MR) description). Ceremony matches the stakes: a small fix needs no command, a small feature uses a short `/intent` then `/build`, and only a large change or a production change runs the full sequence. These are prompts and skills the model follows, plus two deterministic guardrails for what must be guaranteed. See [workflow](docs/workflow.md).

Alongside, **tools** (`/guide`, `/learn`, `/explain`, `/retro`, `/friction`) and **domain playbooks** activated when the task calls for them; yours are added the same way. See [tools](docs/tools.md) and [adding a skill](docs/extending.md).

The project's four requirements: simple installation, Mac and Windows, extension without touching kit files, and several CLIs, each with its own adapter.

## Supported CLIs

| CLI | State | Commands |
| --- | --- | --- |
| Gemini CLI | ✅ | `/guide` |
| Antigravity CLI (`agy`) | ✅ | `/guide` |
| Codex CLI | ✅ | `$guide` |

Verified versions, where each file is placed, and what differs between CLIs: [CLI matrix](docs/cli/matrice.md).

## Documentation

- **Use**: [getting started](docs/getting-started.md), [workflow](docs/workflow.md), [tools](docs/tools.md), [agents](docs/agents.md), [project layer](docs/project-context.md), [Troubleshooting](docs/troubleshooting.md).
- **Customize**: [customization](docs/customization.md), [add or replace a skill](docs/extending.md), [guardrails](docs/hooks.md), [MCP](docs/mcp.md), [identity](docs/identity.md).
- **Per CLI**: [matrix](docs/cli/matrice.md), [Gemini CLI](docs/cli/gemini.md), [Antigravity CLI](docs/cli/agy.md), [Codex CLI](docs/cli/codex.md), [moving from Gemini to agy](docs/cli/gemini-to-agy.md).
- **Deploy and maintain**: [the installer](docs/installer.md), [compliance and governance](docs/compliance.md), [contributing](docs/contributing.md), [command format](docs/format.md), [skills reference](docs/skills-reference.md), [evals](docs/evals.md), [usage review](docs/usage-review.md), [pilot](docs/pilot.md), [sources](docs/sources.md), [changelog](CHANGELOG.md).

## Credits and inspiration

- **Workflow**: the six steps, each closed by an artifact that the next one reads, come from Anthropic's ["The AI-native SDLC playbook"](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).
- **Base skills**: taken and adapted from [mattpocock/skills](https://github.com/mattpocock/skills), by Matt Pocock, under the MIT licence: interview before building, glossary and ADRs, small composable skills.
- **Discipline mechanisms**: rationalization tables ("too simple for a test") and adversarial review by a doubter agent come from [agent-skills](https://github.com/addyosmani/agent-skills), by Addy Osmani.
- **Other sources**: [pstack](https://github.com/cursor/plugins/tree/main/pstack), and Switch Dimension's comparison of these skill packs, the source of the "ceremony matches the stakes" rule.

Details in [sources](docs/sources.md).

## Licence

MIT, see [LICENSE](LICENSE). Base skills taken from mattpocock/skills keep their own MIT licence, in `skills/LICENSE-UPSTREAM-MIT`.
