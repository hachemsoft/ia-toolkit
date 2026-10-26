# Antigravity CLI (agy)

The kit targets Gemini CLI and Antigravity CLI from a single source. When `agy` is present on the workstation (or the `~/.gemini/config/` folder exists), `setup` and `update` also install the Antigravity output. `--target gemini` prevents it, `--target both` forces it alongside Gemini, and `--target agy` installs it alone (the layers then go to `~/.ai-kit/context/`).

## What is shared with no extra work

- **Skills**: agy reads `~/.gemini/skills/`, so the kit skills, domain playbooks and repository skills (`.agents/skills/`) are visible on both sides.
- **Repository context**: `AGENTS.md`, `GEMINI.md`, `GLOSSARY.md`, `REVIEW.md`, the `.agents/rules/`.
- **`30_USER.md`** and the kit layers, through the plugin below.

## What the kit adds for agy

A plugin `~/.gemini/config/plugins/ai-kit/`, validated by `agy plugin validate` in `doctor`:

| File | Role |
| --- | --- |
| `plugin.json` | name, description, kit version |
| `rules/AGENTS.md` | always-on rules that include the four layers by path (`@[00_kit](~/.gemini/00_KIT.md)`, …, `@[30_user](~/.gemini/30_USER.md)`, or `~/.ai-kit/context/` without Gemini): a single source, no copy |
| `agents/ai-kit-*.md` | the same agents as Gemini (verifier, adversarial review, SQL review, dbt, code); visible in agy |
| `hooks.json` | the two guardrails, `enabled` following `overrides.json`; the scripts understand the agy payload (`toolCall.args.CommandLine`) |
| `mcp_config.json` | the MCP servers enabled in `overrides.json`, when there are any |

And **command skills** in `~/.gemini/skills/`: agy has no command files, but every skill is a `/<name>` command. For each profile command without a skill of the same name (`intent`, `spec`, `build`, `test`, `review`, `ship`, `diagnose`, `design`, `map`, `learn`, `explain`, `ask`, `audit`), the kit generates a skill of the same name whose body is the command prompt. `/guide`, `/retro`, `/triage`, `/research`, `/handoff`, `/wizard` already exist as skills. In Gemini, these command skills are also visible: their description says to activate only on the command or an explicit request.

After installation, restart agy: it discovers a new plugin only at startup.

## Verified on 25 October 2026 on agy 1.4.7

- `agy plugin validate` passes; `agy plugin list` shows `ai-kit` with the profile agents (6 for a developer, 4 for an analyst), 1 rule, 2 hooks.
- In print mode, agy quotes word for word the "Priority between layers" section of `00_KIT.md`: path includes work.
- agy lists the profile's `ai-kit-*` agents.
- `/guide` and `/intent` work through the command skills; `/guide` routes to `/diagnose` for a dbt model that duplicates rows.

## Protected configuration

The `protected-paths` guardrail always blocks agent writes to the `ai-kit` plugin folder `~/.gemini/config/plugins/ai-kit/`.

## Known limits

- **Print mode and permissions**: agy drops the whole response as soon as a tool asks for a permission it cannot request. Commands that read the repository (`/intent`, `/explain`, `/test`) therefore fail in `agy -p` until the person has approved read rules in their own agy settings. In interactive mode, agy asks for permission and everything works. The evals runner classifies this case as an infrastructure error, not a behavior failure.
- **Write tool**: the `protected-paths` guardrail recognizes tools whose name contains `write`, `replace` or `edit` and looks for the path in `TargetFile`, `AbsolutePath`, `file_path` or `path`. To be confirmed on a real agy write call.
- **Agent `tools` field**: accepted by the validator; its exact effect in agy is not documented.
- **Logs**: `usage` reads `~/.gemini/antigravity-cli/history.jsonl` (prompts and typed commands); skill activations are not visible in this file.

## Authentication: Google account or Google Cloud project

By default agy signs in with the person's Google account and uses their individual quota. When it runs out, agy answers "Individual quota reached" (HTTP 429) until the reset. An organization can instead have agy sign in with Google Cloud application default credentials and bill a project: set the environment variable `AGY_ADC_AUTH=1` in the shell, create the credentials with `gcloud auth application-default login`, and set the quota project of these credentials (`gcloud auth application-default set-quota-project <project>`) with the Agent Platform API (`aiplatform.googleapis.com`) enabled. The quota project of the credentials is what counts, not `GOOGLE_CLOUD_PROJECT`. Example, on a workstation that has already run `gcloud auth application-default login`:

```sh
gcloud auth application-default set-quota-project my-gcp-project
export AGY_ADC_AUTH=1   # in your shell profile to make it permanent
agy
```

A 403 "Agent Platform API has not been used in project …" means the API is not enabled on this quota project: `gcloud services enable aiplatform.googleapis.com --project my-gcp-project`. The models offered by `/model` then depend on what the project can use. The kit does not set this variable: it belongs to the workstation and the organization, as with Vertex on the Gemini CLI side (`vertex` in `overrides.json`).

## Permissions: up to each person, never the kit

agy asks for approval before a shell command or a write, and offers to remember the answer. These rules (`permissions.allow` in `~/.gemini/antigravity-cli/settings.json`) belong to the workstation and the person: they reflect what the person accepts the agent doing on their machine. The kit does not write them, does not read them to change them and never touches this file; `update` leaves it intact (checked by a test). An organization that wants a baseline set of rules does it through its own settings distribution, outside the kit, so that each person's choices are not overwritten.

## Troubleshooting

`doctor` validates the plugin and reports kit skills hidden by copies in `~/.agents/skills`. Command skills can collide with older personal skills of the same name (`review`, `diagnose`, `test`…): move or rename them; `update` refuses to overwrite what it does not manage.
