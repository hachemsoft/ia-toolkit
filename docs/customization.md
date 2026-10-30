# Customization

`~` is your home folder (`%USERPROFILE%` on Windows), not the project folder: `~/.ai-kit/overrides.json` is `%USERPROFILE%\.ai-kit\overrides.json` on Windows. Folders starting with a dot are hidden; how to open them: [where your files are](getting-started.md#where-your-files-are).

> `update`, `setup` and `doctor` on this page: run them from the kit folder, as shown in [getting started › Run the kit](getting-started.md#run-the-kit) (`Installer.cmd update` on Windows, `sh scripts/bootstrap.sh update` on Mac).

## Organization, team and person

Settings come in three layers, combined at every `setup` and `update`, each on top of the previous one:

- **`organization.json`**, at the root of the kit repository, belongs to the organization. It is changed by merge request, then each workstation runs `update`. It holds the expected email domains (`allowed_domains`) and the organization defaults (`defaults`, with the same keys as `overrides.json`: authentication, model, guardrails, MCP, skills, commands…).
- **The team's settings**, in the same `organization.json`, under `teams` (see [Teams](#teams)).
- **`~/.ai-kit/overrides.json`** belongs to the person. It is applied on top: lists add up, objects combine, the person's value wins for a single value. It never replaces the organization or team settings wholesale; `doctor` lists the values a person changed.

```json
{
  "allowed_domains": ["company.com"],
  "defaults": { "code_assist": { "project": "my-gcp-project" }, "hooks": { "dbt-prod-guard": true } }
}
```

Both files have a JSON Schema in `schemas/`: an editor that knows the `"$schema"` key (VS Code and most others) completes the keys, shows each key's description and flags a typo or a wrong value as you type. `organization.json` points to its schema; the personal file points to the copy in `~/.ai-kit/schemas/` (`setup` adds or updates that line, and changes nothing else in the file). `doctor` also reports an unknown key (usually a typo), and the CI checks the shipped files against the schemas.

**How a change of `organization.json` reaches you**: with the next version of the kit (a new ZIP, or `git pull` in a clone), then `setup` or `update`. Where your own files are, on Mac and Windows: [getting started](getting-started.md#where-your-files-are).

### Who decides what, and what the kit cannot enforce

| Who | Where | Decides |
| --- | --- | --- |
| the organization | `organization.json` (`allowed_domains`, `defaults`), `practices/10-company.md` | defaults for everyone: authentication, model, guardrails, approved MCP servers, company practices |
| the team | `organization.json` (`teams.<team>`), `practices/20-<team>.md` | its tools and its practices, on top of the organization |
| the profile | `profiles/<profile>.json` | the skills, commands, agents and MCP servers of a job |
| you | `~/.ai-kit/overrides.json`, `30_USER.md` | your additions and exceptions, your preferences |
| the repo | `AGENTS.md`, `.agents/skills/`, `.ai-kit/protected-paths` | how to work in that repo |

The kit configures; it does not lock. Your `overrides.json` has the last word, so you can turn off a guardrail or an MCP server that the organization turned on, and `doctor` shows it ("Your overrides.json changes organization or team defaults"). What must be guaranteed is enforced outside the kit: IAM rights and data access, managed CLI settings pushed by IT, CODEOWNERS on repos. The practices in `10` and `20` are instructions to the agent, followed by default, not a technical barrier.

JSON allows no comments: keys starting with `_` (`_doc`) are documentation and are ignored. A mistake in either file is reported with its line, its column, the line itself and the usual cause (missing comma, comma left before `}`, single quotes, backslash in a Windows path).

## Teams

Profiles describe a job; teams describe who you work with. A person has one profile and, optionally, one team; the two are independent. A team can bring two things, both in the kit repository and both optional.

**Its context: `practices/20-<team>.md`.** The team's rules in plain text: ticket tracker, branch names, review and deployment habits. The kit installs it as `20_<TEAM>.md` instead of the shared `20_TEAM.md`, whatever the profile.

**Its tools: `teams` in `organization.json`.** The same keys and formats as `overrides.json`: skills, commands, agents, guardrails, MCP servers, model.

```json
{
  "defaults": {
    "mcp": { "dbt": { "server": { "command": "dbt-mcp" } } }
  },
  "teams": {
    "data-platform": {
      "extra_skills": ["prototype"],
      "extra_commands": ["ask"],
      "hooks": { "dbt-prod-guard": true },
      "mcp": { "dbt": true }
    }
  }
}
```

Order: organization defaults, then the team, then the person's `overrides.json`, which keeps the last word (`"dbt": false`, `"disabled_skills": ["prototype"]`). For MCP servers, the team uses the person's formats: `true` or `false` for a server the organization defines, `{"server": {...}}` for one of its own ([MCP](mcp.md)).

**Choosing the team.** `setup` lists the teams (those with a practices file or settings) and asks; or `setup --team <team>`. The team is kept for `update`. The usual way: IT gives each team its ready-made command, for example `sh scripts/bootstrap.sh setup --profile java-developer --team data-platform`. To change team, run `setup --team <other>`. `doctor` shows the team and where its content comes from.

**Adding a team** is one merge request on the kit repository: the practices file, the `teams` entry, or both. Protect them with a CODEOWNERS line so that the team reviews its own changes.

## Context layers

The kit installs short files that the agent loads in all your projects, in this order. They live in `~/.gemini/` if Gemini CLI is installed (it only reads its own folder), otherwise in `~/.ai-kit/context/`. Details per CLI: [matrix](cli/matrice.md#add-a-cli).

| File | Owner | Content |
| --- | --- | --- |
| `00_KIT.md` | kit | profile, priority rule between layers |
| `10_COMPANY.md` | kit | company practices |
| `20_TEAM.md`, or `20_<TEAM>.md` for a team with its own practices | kit (the team's file in the kit repository) | team practices |
| `30_USER.md` | you | language, style, level, domains, default workflow |

The kit files are generated output: editing them blocks `update`. Everything specific to you goes in `30_USER.md`. `setup` creates it once and never rewrites it. A change takes effect the next time the CLI starts; a CLI that keeps a copy needs `update` first ([matrix](cli/matrice.md)), so the simple rule is: edit, `update`, new session.

Priority rule, written in `00_KIT.md`: company and team practices apply by default; `30_USER.md` adjusts form and workflow; the repo's `AGENTS.md` and an explicit request win over `30_USER.md`, never over the practices. The full table, with repo skills: [project layer](project-context.md#how-the-repo-combines-with-your-layers). The agent reads the files one after another; there is no mechanical override: the wording sets the priority.

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

Override a kit command in the repo, in the form the CLI reads ([matrix](cli/matrice.md)). The project wins.

Each repo provides its own `AGENTS.md`, read after the global layers. To redefine a preference there, reuse the same heading as in `30_USER.md` ("Language and style", "My default workflow") and write the project rule.

## Commands, skills, agents and MCP

`~/.ai-kit/overrides.json`: selection of commands, skills, agents and MCP servers (the MCP rule, organization, profile and person, is on its own page: [MCP](mcp.md)). Keep the JSON valid.

**Commands.** `extra_commands` adds commands to the profile's, with their skills; `disabled_commands` removes some. An analyst who wants `/spec` and `/review`:

```json
{ "extra_commands": ["spec", "review"] }
```

**Skills.** Example: an analyst adds the Python/JS skill (which relies on `codebase-design`, added automatically) and disables the BigQuery cost playbook:

```json
{
  "extra_skills": ["python-js-change"],
  "disabled_skills": ["bigquery-cost-review"]
}
```

Added skills must exist in `skills/catalog.json`. A skill required by another one (`requires`) cannot be disabled on its own; `update` reports it. An old name (`clarify-request`, `debug-systematically`, `verify-change`) redirects to its replacement. Apply with `update` from the kit folder. See [workflow](workflow.md) for the role of each skill.

CLI-specific settings stay editable in the CLI's own files; the kit keeps existing keys. To change a default value already installed, change the value in the CLI settings.

A project skill with the same name can override the global skill; use explicit names. The three ways to add or replace a skill (for yourself, for a repo, for the organization) are in [add or replace a skill](extending.md). If a managed skill is modified locally, update stops: save your variant outside the managed directory, then restore the distributed file before running it again. For a permanent variant, use another name and manage it at the right level.

## Full `overrides.json` example

A developer who wants `/ask` and `/handoff`, prototyping, no delegated research, the doubter agent added, the dbt guardrail on, an enterprise Code Assist project and a fixed model:

```json
{
  "extra_commands": ["ask", "handoff"],
  "disabled_commands": [],
  "extra_skills": ["prototype"],
  "disabled_skills": ["investigation"],
  "extra_agents": ["doubter"],
  "disabled_agents": [],
  "mcp": { "github": true },
  "hooks": { "dbt-prod-guard": true },
  "code_assist": { "project": "my-gcp-project" },
  "model": "gemini-2.5-flash",
  "models": { "fast": "gemini-2.5-flash", "deep": "gemini-2.5-pro" },
  "frictions": "propose"
}
```

`frictions` sets what the agent does on the six friction signals: `propose` (default), it suggests `/friction` and you confirm; `auto`, it logs the friction itself without asking and says so in one line; `off`, it says nothing. In all cases the line stays on your workstation. `models` sets a model per agent capability (`fast`, `deep`); see [agents](agents.md#capability-profiles). `model` and `models` take effect only in the CLIs that support them ([matrix](cli/matrice.md)); elsewhere they are ignored. Then `update`. Every key is optional; a missing key changes nothing. A skill added through `extra_commands` comes with its dependencies; a skill required by another one cannot be disabled on its own, and `update` says so.

## Authentication and model

The kit chooses neither the authentication mode nor the model: each organization has its own. Without a declaration in `overrides.json`, the kit touches no authentication or model setting; you configure the CLI as usual. The keys below apply to CLIs that go through Google Cloud; their exact effect per CLI is on its page ([Gemini CLI](cli/gemini.md#authentication-and-model)). `doctor --live` recognizes the failures of each mode and gives the key to write.

| Your situation | In `overrides.json` | What `update` does |
| --- | --- | --- |
| Google sign-in, individual account (free Gemini Code Assist) | nothing | nothing |
| Google sign-in, Code Assist Standard or Enterprise license ("This account requires setting the GOOGLE_CLOUD_PROJECT…") | `"code_assist": {"project": "<gcp-project>"}` | `selectedType` set to `oauth-personal`, `GOOGLE_CLOUD_PROJECT` in `~/.gemini/.env` |
| Vertex AI with application default credentials (`gcloud auth application-default login`) | `"vertex": {"project": "<gcp-project>", "location": "<region>"}` | `selectedType` set to `vertex-ai`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` in `~/.gemini/.env` |
| AI Studio API key | nothing | nothing: `GEMINI_API_KEY` stays yours |
| The default model loops ("Model fallback activated") or is not available on your access | `"model": "<model name>"` | `model.name` in `~/.gemini/settings.json` |

For agy, the Vertex equivalent is the environment variable `AGY_ADC_AUTH=1` (see [agy](cli/agy.md#authentication-google-account-or-google-cloud-project)); the kit does not set it. `vertex` and `code_assist` are mutually exclusive. The Vertex region defaults to `us-central1` if omitted. In `~/.gemini/.env`, your lines are kept; the kit's lines are marked with a `# ai-kit :` comment and removed if you delete the key from `overrides.json` (`selectedType` then stays as is; change it with `/auth` if needed). Credentials themselves (Google sign-in, `gcloud`, key) never go through the kit.

## Guardrails

Two deterministic hooks, set in `overrides.json` under `hooks`: `protected-paths` is on by default (it protects the configuration of the kit and of the CLIs; `"protected-paths": false` turns it off), `dbt-prod-guard` is off by default. See [guardrails](hooks.md).

## Identity

See [identity](identity.md): how the kit detects the signed-in person, what it does with that, and what it does not.
