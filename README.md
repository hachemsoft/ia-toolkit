<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/img/logo-dark.svg">
    <img alt="AI Kit: one kit, four coding agents" src="docs/img/logo-light.svg" width="360">
  </picture>
</h1>

[![Tests](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml/badge.svg)](https://github.com/hachemsoft/ia-toolkit/actions/workflows/portability.yml)
[![Version](https://img.shields.io/github/v/tag/hachemsoft/ia-toolkit?label=version)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.11%20%E2%80%93%203.14-blue)](docs/installer.md)
[![Platforms](https://img.shields.io/badge/platforms-Mac%20%7C%20Windows%20%7C%20Linux-informational)](docs/getting-started.md)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

One set of rules, methods and anti-error guardrails for the agent CLIs you choose (**Gemini CLI**, **Antigravity CLI**, **Codex CLI** and **Claude Code**), on Mac and Windows: layered context, a command-based workflow, domain playbooks and review agents. It installs without administrator rights, can be undone, downloads nothing from the release ZIP, and never calls the model on its own. It enforces nothing: for rules that must hold, deploy the policies it generates with your device management ([guardrails](docs/hooks.md#rules-it-can-enforce)).

## Getting started

1. **Install**: clone the repository (your organization's copy if it has one) into a folder you keep, then:
   - **Windows**: double-click `Installer.cmd`.
   - **Mac**: open Terminal, type `sh ` (with a space), drag `scripts/bootstrap.sh` from the cloned folder into the window, press Enter.

   Without git, or without access to a Python package index: download `ai-kit-<version>.zip` from the [Releases](https://github.com/hachemsoft/ia-toolkit/releases) page, extract it and run the same launcher; it installs everything from the ZIP, with no download.

   A short guided screen asks which CLIs you use, lets you adjust the optional resources (or keep the default), shows what will change, then installs.
2. **Use**: open a terminal in your repo, start your CLI and ask in plain words. Type `/me` once: a short interview that tells the agent how to work with you.

   | You say | Shortcut |
   | --- | --- |
   | "Explain how orders are validated in this repo" | `/explain` |
   | "Make the export skip archived customers" | `/build` |
   | "The nightly job fails since Monday with this error: …" | `/diagnose` |
   | "Review my changes before I open the merge request" | `/review` |

   `/guide I need to …` tells you which command fits (`$` instead of `/` in Codex).
3. **When something goes wrong**: run the installer again and choose **Check the installation**, then [Troubleshooting](docs/troubleshooting.md).

You need Python 3.11 or later (AI Kit 2.0; on Python 3.9 or 3.10, stay on AI Kit 0.52) and your CLI, provided by your company; signing in and choosing the model are done in the CLI. With conda, run the installer and `ai-kit` from a conda prompt, on `base` rather than a project environment. Step by step: [getting started](docs/getting-started.md). For IT: [validation on enterprise workstations](docs/validation.md) and [compliance](docs/compliance.md). Windows is covered by CI on administrator runners and by a trial on one virtual machine, not yet on a locked-down company workstation: a policy that blocks programs under the user profile also blocks the kit ([what to ask IT](docs/validation.md#what-it-may-have-to-provide-or-allow)).

**Update**: `ai-kit update` in a terminal (the installer adds the `ai-kit` command to your own PATH, unless you said no: then `Installer.cmd update`, Mac `sh scripts/bootstrap.sh update`, from the cloned folder) fetches the new version, reinstalls and reapplies; your choices and files are kept. Never `pip install` the kit next to it: that makes a second copy `update` does not touch. From a ZIP: extract the new ZIP and run its installer. **Uninstall**: run the installer and choose **Uninstall**; only what the kit installed goes.

## What gets installed

| | For | What |
| --- | --- | --- |
| **Core default** | everyone | the workflow commands, the tools, code review and the general agents |
| **Optional** | turned on by a Team or by you | domain playbooks (SQL and dbt, Java, infrastructure, architecture, Python and JavaScript) and their review agents, more commands |
| **Team** | the members of one team | a Git repository of its own: its optional resources turned on, its own skills and agents, its context ([Teams](docs/core-source.md#teams)) |

The full list: [getting started](docs/getting-started.md#3-work-one-command-per-step). The installer adds or removes a playbook, a command or an agent without editing any file. Since AI Kit 3.0 there are no profiles: an installation made with one keeps everything it had.

## What it is

- **Layered context**: company practices, team practices and your preferences, read before each repo's own `AGENTS.md`; the organization writes its layer in its Core, each team in its Team repository.
- **A workflow**: one command per step (`/intent`, `/spec`, `/build`, `/test`, `/review`, `/ship`, `/diagnose`), with ceremony matched to the stakes; the agent states the level on its first line. See [workflow](docs/workflow.md).
- **Domain playbooks and review agents** that the model can activate when the task calls for them, without guarantee; yours are added the same way ([extending](docs/extending.md)).
- **Anti-error guardrails**, not a security barrier: on by default, a refusal when an agent writes to the configuration of the kit and of the CLIs in a form they recognise, active on Codex once you approve them; off by default, a refusal of dbt commands on production ([guardrails](docs/hooks.md)).
- **A feedback loop**: `/friction`, a local usage review, and per-skill versions so an update says what changed.

## Does it help?

The same tasks, run with and without the kit, judged on the outcome ([evals](docs/evals.md#with-and-without-the-kit)):

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/evals-with-without-dark.svg">
  <img alt="Plain-words tasks passed with and without the kit: asks the deciding question before SQL 4/4 with the kit, 0/4 without; keeps an API key out of the code 3/3 with, 1/4 without; keeps a failing test 3/3 with, 4/4 without." src="docs/img/evals-with-without-light.svg" width="720">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/evals-framing-dark.svg">
  <img alt="Asking the deciding question before writing SQL, run by run: never without the kit or with kit 0.45.3; every run with kit 0.45.4 and 0.45.5, on Claude Code and Codex." src="docs/img/evals-framing-light.svg" width="720">
</picture>

3 or 4 runs per side on 3 of the 21 cases, Claude Code 2.1.316 and Codex CLI 0.164.0, kit 0.45.4 and 0.45.5: regression tests for the kit's prompts, not a study. They do not compare the kit with a short `AGENTS.md` holding the same rules, the rule behind the first result was written after its case, and no run on Gemini CLI or Antigravity CLI is stored. The results are in `evals/results/`; `scripts/eval_charts.py` redraws the charts.

## Supported CLIs

| CLI | Commands |
| --- | --- |
| Gemini CLI | `/guide` |
| Antigravity CLI (`agy`) | `/guide` |
| Codex CLI | `$guide` |
| Claude Code | `/guide` |

Where each file goes and what differs: [CLI matrix](docs/cli/matrice.md).

## Documentation

- **Use**: [getting started](docs/getting-started.md), [workflow](docs/workflow.md), [tools](docs/tools.md), [agents](docs/agents.md), [project layer](docs/project-context.md), [Troubleshooting](docs/troubleshooting.md).
- **Customize**: [customization](docs/customization.md), [extending and `ai-kit new`](docs/extending.md), [guardrails](docs/hooks.md), [MCP](docs/mcp.md), [identity](docs/identity.md).
- **Per CLI**: [matrix](docs/cli/matrice.md), [Gemini CLI](docs/cli/gemini.md), [Antigravity CLI](docs/cli/agy.md), [Codex CLI](docs/cli/codex.md), [Claude Code](docs/cli/claude-code.md), [moving from Gemini to agy](docs/cli/gemini-to-agy.md).
- **Deploy and maintain**: [installer](docs/installer.md), [validation](docs/validation.md), [compliance](docs/compliance.md), [architecture](docs/architecture.md), [contributing](docs/contributing.md), [command format](docs/format.md), [skills reference](docs/skills-reference.md), [evals](docs/evals.md), [eval cases](docs/eval-cases.md), [usage review](docs/usage-review.md), [pilot](docs/pilot.md), [sources](docs/sources.md), [changelog](CHANGELOG.md).

## Credits and inspiration

- **Workflow**: the steps, each closed by an artifact the next one reads, come from Anthropic's ["The AI-native SDLC playbook"](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).
- **Base skills**: taken and adapted from [mattpocock/skills](https://github.com/mattpocock/skills), by Matt Pocock, under the MIT licence.
- **Discipline mechanisms**: rationalization tables and adversarial review by a doubter agent come from [agent-skills](https://github.com/addyosmani/agent-skills), by Addy Osmani.
- **Other sources**: public skill collections and a published comparison of skill packs, the source of the "ceremony matches the stakes" rule. Details in [sources](docs/sources.md).

## Licence

MIT, see [LICENSE](LICENSE). Base skills taken from mattpocock/skills keep their own MIT licence, in `skills/LICENSE-UPSTREAM-MIT`.
