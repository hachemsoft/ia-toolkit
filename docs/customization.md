# Customization

The user folder is the Windows or macOS one, not the project folder.

## Context layers

The kit installs short files that the agent loads in all your projects, in this order. They live in `~/.gemini/` if Gemini CLI is installed (it only reads its own folder), otherwise in `~/.ai-kit/context/`. Details per CLI: [matrix](cli/matrice.md#add-a-cli).

| File | Owner | Content |
| --- | --- | --- |
| `00_KIT.md` | kit | profile, priority rule between layers |
| `10_COMPANY.md` | kit | company practices |
| `20_TEAM.md` | kit | team practices |
| `30_USER.md` | you | language, style, level, domains, default workflow |

The kit files are generated output: editing them blocks `update`. Everything specific to you goes in `30_USER.md`. `setup` creates it once and never rewrites it. A change takes effect the next time the CLI starts, without `update`.

Priority rule, written in `00_KIT.md`: practices are mandatory; `30_USER.md` adjusts form and workflow; the project's `AGENTS.md` wins over `30_USER.md` on conflict. The agent reads the files one after another. There is no mechanical override: the wording sets the priority.

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

`~/.ai-kit/overrides.json`: selection of commands, skills, agents and MCP. Keep the JSON valid.

**Commands.** `extra_commands` adds commands to the profile's, with their skills; `disabled_commands` removes some. An analyst who wants `/spec` and `/review`:

```json
{ "extra_commands": ["spec", "review"] }
```

**Skills.** Example: an analyst adds the Python/JS skill (which relies on `codebase-design`, added automatically) and disables the BigQuery cost playbook:

```json
{
  "extra_skills": ["python-js-change"],
  "disabled_skills": ["bigquery-cost-review"],
  "mcp": {}
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
  "disabled_skills": ["research"],
  "extra_agents": ["doubter"],
  "disabled_agents": [],
  "mcp": {},
  "hooks": { "dbt-prod-guard": true },
  "code_assist": { "project": "my-gcp-project" },
  "model": "gemini-2.5-flash",
  "models": { "fast": "gemini-2.5-flash", "deep": "gemini-2.5-pro" },
  "frictions": "propose"
}
```

`frictions` sets what the agent does on the five friction signals: `propose` (default), it suggests `/friction` and you confirm; `auto`, it logs the friction itself without asking and says so in one line; `off`, it says nothing. In all cases the line stays on your workstation. `models` sets a model per agent capability (`fast`, `deep`); see [agents](agents.md#capability-profiles). Then `update`. Every key is optional; a missing key changes nothing. A skill added through `extra_commands` comes with its dependencies; a skill required by another one cannot be disabled on its own, and `update` says so.

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

Two deterministic hooks, off by default, are enabled in `overrides.json` under `hooks`. See [guardrails](hooks.md).

## Identity

See [identity](identity.md): how the kit detects the signed-in person, what it does with that, and what it does not.
