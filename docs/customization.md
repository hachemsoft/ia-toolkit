# Customization

`~` is your home folder (`%USERPROFILE%` on Windows), not the project folder: `~/.ai-kit/overrides.toml` is `%USERPROFILE%\.ai-kit\overrides.toml` on Windows. Folders starting with a dot are hidden; how to open them: [where your files are](getting-started.md#where-your-files-are).

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

**Without editing any file.** The usual choices (CLIs, profile, domain playbooks, optional tools, commands, review agents) are made in the installer: run it again and choose **Change my choices**. It writes the corresponding lists of `overrides.toml` (`extra_skills`, `disabled_skills`, `extra_commands`, `disabled_commands`, `extra_agents`, `disabled_agents`) only when you confirm **Install**, and keeps your other keys and your `#` comments. The file stays the single place for these choices: what you edit by hand and what the installer writes are the same lists, the last one written wins. The rest of this page is for what the installer does not ask (MCP servers, guardrails, `skill_prefix`, `frictions`) and for organizations. A name that the kit does not know in `disabled_skills` or `disabled_agents` is reported at the next update (a typo has no effect). `skill_prefix` (`"ai-kit-"` by default) is the name given to a kit skill or command when one of yours already has its name, on every CLI; one CLI gives it to every kit skill: see [Claude Code](cli/claude-code.md#the-prefix).

## Organization, team and person

Settings are combined at every `setup` and `update`, in this order, each on top of the previous one: **organization**, **profile** (the skills, commands, agents and MCP servers of your job, `profiles/<profile>.toml`), **team**, **you**. The person keeps the last word.

- **`organization.toml`**, at the root of the kit repository, belongs to the organization. It is changed by merge request and reaches workstations with the next version of the kit. It holds the expected email domains (`allowed_domains`) and the organization defaults (`defaults`, with the same keys as `overrides.toml`: guardrails, MCP, skills, commands, agents, `skill_prefix`, `frictions`).
- **The team's settings**, in the same `organization.toml`, under `teams` (see [Teams](#teams)).
- **`~/.ai-kit/overrides.toml`** belongs to the person. It is applied on top: lists add up, objects combine, the person's value wins for a single value. It never replaces the organization or team settings wholesale; `doctor` lists the values a person changed.

```toml
allowed_domains = ["company.com"]

[defaults]
hooks = { dbt-prod-guard = true }
```

Both files are TOML and have a JSON Schema in `schemas/`, named on their first line (`#:schema …`): an editor with TOML support that reads that line (VS Code with Even Better TOML, for example) completes the keys, shows each key's description and flags a typo or a wrong value as you type. `organization.toml` points to its schema; the personal file points to the copy in `~/.ai-kit/schemas/` (`setup` updates that line, and changes nothing else in the file). `doctor` also reports an unknown key (usually a typo), and the CI checks the shipped files against the schemas.

**How a change of `organization.toml` reaches you**: with the next version of the kit (a new ZIP, or `git pull` in a clone), then `setup` or `update`. Where your own files are, on Mac and Windows: [getting started](getting-started.md#where-your-files-are).

### Who decides what, and what the kit cannot enforce

| Who | Where | Decides |
| --- | --- | --- |
| the organization | `organization.toml` (`allowed_domains`, `defaults`), `practices/10-company.md` | defaults for everyone: guardrails, approved MCP servers, skills and commands, company practices |
| the team | `organization.toml` (`teams.<team>`), `practices/20-<team>.md` | its tools and its practices, on top of the organization |
| the profile | `profiles/<profile>.toml` | the skills, commands, agents and MCP servers of a job |
| you | `~/.ai-kit/overrides.toml`, `30_USER.md` | your additions and exceptions, your preferences |
| the repo | `AGENTS.md`, `.agents/skills/`, `.ai-kit/protected-paths` | how to work in that repo |

The kit configures; it does not lock. Your `overrides.toml` has the last word, so you can turn off a guardrail or an MCP server that the organization turned on, and `doctor` shows it ("Your overrides.toml changes organization or team defaults"). What must be guaranteed is enforced outside the kit: IAM rights and data access, managed CLI settings pushed by IT, CODEOWNERS on repos. The practices in `10` and `20` are instructions to the agent, followed by default, not a technical barrier.

TOML in four rules: one `key = value` per line, texts in double quotes, lists in `[ ]`, and `#` starts a comment, kept by the kit. A `[section]` groups the keys under it: `[hooks]` then `dbt-prod-guard = true`; `[mcp.github.server]` is the `server` of the `github` entry of `mcp`. A mistake in either file is reported with its line, its column, the line itself and the usual cause (a text without quotes, a key written twice, a list not closed, a backslash in a Windows path). Before 0.37 the personal file was `overrides.json`: the next `setup` or `update` turns it into `overrides.toml` with the same settings, its `_` explanations as comments, and keeps the JSON file in its backup.

## Teams

Profiles describe a job; teams describe who you work with. A person has one profile and, optionally, one team; the two are independent. A team can bring two things, both in the kit repository and both optional.

**Its context: `practices/20-<team>.md`.** The team's rules in plain text: ticket tracker, branch names, review and deployment habits. The kit installs it as `20_<TEAM>.md` instead of the shared `20_TEAM.md`, whatever the profile.

**Its tools: `teams` in `organization.toml`.** The same keys and formats as `overrides.toml`: skills, commands, agents, guardrails, MCP servers.

```toml
[defaults.mcp.dbt]
server = { command = "dbt-mcp" }

[teams.data-platform]
extra_skills = ["prototype"]
extra_commands = ["ask"]
hooks = { dbt-prod-guard = true }
mcp = { dbt = true }
```

Order: organization defaults, then the team, then the person's `overrides.toml`, which keeps the last word (`dbt = false`, `disabled_skills = ["prototype"]`). For MCP servers, the team uses the person's formats: `true` or `false` for a server the organization defines, a `server` table for one of its own (`[teams.<team>.mcp.<name>.server]`) ([MCP](mcp.md)).

**Choosing the team.** `setup` lists the teams (those with a practices file or settings) and asks; or `setup --team <team>`. The team is kept for `update`. The usual way: IT gives each team its ready-made command, for example `sh scripts/bootstrap.sh setup --profile java-developer --team data-platform`. To change team, run `setup --team <other>`. `doctor` shows the team and where its content comes from.

**Adding a team** is one merge request on the kit repository: the practices file, the `teams` entry, or both. Protect them with a CODEOWNERS line so that the team reviews its own changes.

## Context layers

The kit installs short files that the agent loads in all your projects, in this order. They live in `~/.ai-kit/context/`, whatever the CLIs; a CLI that can only read its own folder gets a copy at each `update`. Details per CLI: [matrix](cli/matrice.md#concept-by-concept).

| File | Owner | Content |
| --- | --- | --- |
| `00_KIT.md` | kit | profile, priority rule between layers |
| `10_COMPANY.md` | kit | company practices |
| `20_TEAM.md`, or `20_<TEAM>.md` for a team with its own practices | kit (the team's file in the kit repository) | team practices |
| `30_USER.md` | you | your role, your domains (level and interest), how you want answers, how to work with you, by situation |

The kit files are generated output. The rule layers (`00`, `10`, `20`) are restored by the next `update` if edited by hand, with the edited copy kept in `~/.ai-kit/backups/` and a `[Check]` line saying so; `doctor` reports the edit until then. A rule change goes through the kit repository. Everything specific to you goes in `30_USER.md`. `setup` creates it once; after that only you, or `/me` with your agreement, change it. A change takes effect the next time the CLI starts; a CLI that keeps a copy needs `update` first ([matrix](cli/matrice.md)), so the simple rule is: edit, `update`, new session.

Priority between instructions, written in `00_KIT.md` and followed by the model: company and team practices apply by default, and only the person can depart from them, by asking explicitly (the agent notes the exception in its reply); `30_USER.md` adjusts form and workflow; the repo's instructions and an explicit request in the conversation take precedence over `30_USER.md`, and when they disagree the agent applies the more cautious and asks you; a repo file, a repo skill or anything the agent reads never lifts a practice. The full table: [project layer](project-context.md#how-the-repo-combines-with-your-layers). This is not the settings merge described above, done by the installer on the TOML files, nor a technical restriction (guardrails, permissions, access rights), which no instruction or exception lifts: [three mechanisms not to confuse](project-context.md#three-mechanisms-not-to-confuse).

### What makes a good `30_USER.md`

One file, short, made of instructions the agent can act on. What the studies of context files and personalization say, and what the kit does about it:

- **Short and specific.** Agents follow fewer instructions as they pile up, and general advice changes nothing: write only what the agent cannot guess and what changes an answer, at most twenty lines, the most important first.
- **Describe yourself, not a role for the agent.** "You are an expert" does not make answers more accurate; your level per domain does change how deep they go. Level and interest are separate: "Python: expert, skip the basics", "C4 diagrams in Mermaid: not an expert but passionate, go deeper".
- **By situation** when you want another tone somewhere: "Reviews: simpler and more teaching, one finding at a time."
- **Form, never conclusions.** A profile makes assistants agree with the person more easily. The file always keeps the line asking the agent to say plainly when your idea is risky or wrong, and it holds no opinion about tools.
- **Interviewed rather than written alone.** People state their preferences better when asked than when facing a blank page: that is what `/me` does, two rounds of questions with options and a recommendation, the facts it can read (operating system, repo languages, profile) never asked.

## Report format

`/build`, `/test`, `/diagnose` and `/review` end with a report. To change its form, add a `## Report` section: in `30_USER.md` for yourself, in the repo's `AGENTS.md` for the team (which wins). Without a section, the kit's default format applies. Example for a Data repo:

```markdown
## Report
- One line: what the change does, in business terms.
- Models touched, with their grain before and after.
- Verification: commands run, pass/fail, rows compared on a known period.
- Risks for the dashboards that read these models.
- What is left, and who must decide it.
```

`/build` and `/diagnose` also stop on their own after three failed fixes on the same check, and report what they tried instead of looping.

## Override per project

Whether a repo can replace a kit command depends on the CLI: one reads a command file from the repo, others keep the kit's version or show both. The exact limits are in the row "Override a command in a repository" of the [CLI matrix](cli/matrice.md). Where the replacement is not reliable, write a skill with a name of its own to the project (`<repo>-review`, for example) and say in `AGENTS.md` when to use it ([add or replace a skill](extending.md#for-a-repo)).

Each repo provides its own `AGENTS.md`, read after the global layers. To redefine a preference there, reuse the same heading as in `30_USER.md` ("Answers", "Working with me") and write the project rule.

## Commands, skills, agents and MCP

`~/.ai-kit/overrides.toml`: selection of commands, skills, agents and MCP servers (the MCP rule, organization, profile and person, is on its own page: [MCP](mcp.md)). Keep the TOML valid. The names to choose from: commands in the [profile table](getting-started.md#3-work-one-command-per-step) and [tools](tools.md), skills in the [skills reference](skills-reference.md), agents in [agents](agents.md).

**Commands.** `extra_commands` adds commands to the profile's, with their skills; `disabled_commands` removes some. An analyst who wants `/spec` and `/explain`, and no `/learn`:

```toml
extra_commands = ["spec", "explain"]
disabled_commands = ["learn"]
```

**Skills.** Example: an analyst adds the Python/JS skill (its required skill, `tdd`, comes with it; `codebase-design` is optional and yours to add) and disables the BigQuery cost playbook:

```toml
extra_skills = ["python-js-change"]
disabled_skills = ["bigquery-cost-review"]
```

Added skills must exist in `skills/catalog.json`. A skill required by another one (`requires`) cannot be disabled on its own; `update` reports it. An old name (`clarify-request`, `debug-systematically`, `verify-change`) redirects to its replacement. Apply with `update` from the kit folder. See [workflow](workflow.md) for the role of each skill.

CLI-specific settings stay editable in the CLI's own files; the kit keeps existing keys. To change a default value already installed, change the value in the CLI settings.

A project skill named like a kit skill behaves differently per CLI ([matrix](cli/matrice.md)): give project skills names of their own. The three ways to add or replace a skill (for yourself, for a repo, for the organization) are in [add or replace a skill](extending.md). If a managed skill is modified locally, update stops: save your variant outside the managed directory, then restore the distributed file before running it again. For a permanent variant, use another name and manage it at the right level.

## Full `overrides.toml` example

A General-profile developer who wants `/ask` and `/handoff`, prototyping, no `/retro`, the security review agent, the dbt guardrail on and the GitHub MCP server of the organization:

```toml
extra_commands = ["ask", "handoff"]
disabled_commands = []
extra_skills = ["prototype"]
disabled_skills = ["retrospective"]
extra_agents = ["security-reviewer"]
disabled_agents = []
frictions = "propose"

[mcp]
github = true

[hooks]
dbt-prod-guard = true
```

`frictions` sets what the agent does on the six friction signals: `propose` (default), it suggests `/friction` and you confirm; `auto`, it logs the friction itself without asking and says so in one line; `off`, it says nothing. In all cases the line stays on your workstation. Then `update`. Every key is optional; a missing key changes nothing. A command added through `extra_commands` comes with its skills and their dependencies; a skill required by another one cannot be disabled on its own, and `update` says so.

## Authentication and model

The kit configures neither: signing in to the model provider and choosing a model belong to each CLI and to the company's IT procedure (personal account, licence, cloud project, API key…). Configure them in the CLI as usual; `doctor --live` still recognizes the usual failures and says what to set, in the CLI or in its own files, never in `overrides.toml`. The agents inherit the model of the session.

| CLI | Authentication | Model |
| --- | --- | --- |
| Gemini CLI | `/auth`; a project or Vertex AI through `~/.gemini/.env` or the environment ([its page](cli/gemini.md#authentication-and-model)) | `/model` |
| Antigravity CLI | Google account, or `AGY_ADC_AUTH=1` for a cloud project ([its page](cli/agy.md#authentication-google-account-or-google-cloud-project)) | its own choice |
| Codex CLI | `codex login` | the session model |
| Claude Code | `/login`, or the provider's variables ([its page](cli/claude-code.md)) | `/model` |

Before 0.36 the kit could write some of these settings for the first CLI of the table (`vertex`, `code_assist`, `model`, `models` in `overrides.toml`). What it wrote stays, now yours: the lines of its `.env` file (a comment line above them now says so) and the authentication type or model name in its settings. These keys are ignored if they remain in `overrides.toml`, and `update` and `doctor` say so.

## Guardrails

Two deterministic hooks, set in `overrides.toml` under `[hooks]`: `protected-paths` is on by default (it protects the configuration of the kit and of the CLIs; `protected-paths = false` turns it off), `dbt-prod-guard` is off by default. See [guardrails](hooks.md).

## Identity

See [identity](identity.md): how the kit detects the signed-in person, what it does with that, and what it does not.
