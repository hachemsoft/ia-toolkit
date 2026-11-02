# Gemini CLI

What the kit does for Gemini CLI, and what is specific to this CLI. Behavior verified on Gemini CLI 0.65. Shared concepts are in the [CLI matrix](matrice.md).

## What the kit installs

- **Context**: copies of `00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` and `30_USER.md` from `~/.ai-kit/context/` in `~/.gemini/` (Gemini imports only files located there), refreshed at each `update` and declared in `context.fileName` of `~/.gemini/settings.json`, followed by `GEMINI.md` and `AGENTS.md` for repositories. Edit `~/.ai-kit/context/30_USER.md`, then run `update`; an edit made to the copy is taken into the file when the file did not change since the copy. Personal names already present in `context.fileName` are kept.
- **Skills** in `~/.gemini/skills/`, **commands** in `~/.gemini/commands/*.toml`, **agents** in `~/.gemini/agents/ai-kit-*.md`.
- **Guardrails** that are enabled: scripts in `~/.ai-kit/hooks/` (shared by all CLIs), declared under `hooks.BeforeTool` in groups named `ai-kit-<name>`. Your own hooks are kept. The `session-news` hook: a group under `hooks.SessionStart` without matcher (Gemini takes an exact string there; the script reads `source` itself); it answers in JSON only, since a plain text would be shown to you instead of the model. Gemini warns once about a hook whose command changed: expected after an update.
- **MCP servers** enabled in `overrides.toml`: `ai-kit-<name>` entries under `mcpServers`.
- **Default setting**: `skills.enabled`, only if it is missing.

## Authentication and model

The kit does not set them: use `/auth` and `/model` in Gemini, or `~/.gemini/settings.json` and `~/.gemini/.env` as your IT procedure says (for example `GOOGLE_CLOUD_PROJECT` for a Code Assist Standard or Enterprise licence, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` with `selectedType: vertex-ai` for Vertex AI). What a version before 0.36 wrote there stays, now yours; see [customization](../customization.md#authentication-and-model). `doctor --live` names the missing setting when the call fails.

## Check in Gemini

`/memory show` (the four layers before the repository context), `/commands list`, `/skills list`, `/agents list` (after `/agents reload`), `/mcp`.

## Protected configuration

The `protected-paths` guardrail always blocks agent writes to `~/.gemini/settings.json` and `~/.gemini/.env`, and `dbt-prod-guard` ignores `AI_KIT_ALLOW_PROD` when it is set in `~/.gemini/.env` or a repo `.env`, which Gemini loads into its environment.

## Specifics

- Gemini CLI 0.65 turns every skill of `~/.gemini/skills/` into a `/<skill>` command. Two commands with the same name are both renamed (`/user.guide`, `/guide1`), so no kit skill shares a command's name, and agy's command skills live in its plugin, where Gemini does not look.
- **`~/.agents/skills` alias**: Gemini reads it too, and it wins over `~/.gemini/skills` when names match ("Skill conflict detected" at startup). `doctor` lists the kit skills hidden this way.
- **Subfolder context**: when launched at the root of a repository, Gemini also reads the `AGENTS.md` and `GEMINI.md` of subfolders; a `.geminiignore` limits what it walks.
- **Non-interactive mode (`gemini -p`)**: the skill activation tool is not exposed; the kit commands say what to do without it. `plan` mode also blocks skills.
- **Subagents**: enabled by default since 0.65. An `experimental.enableAgents` set to `false` disables them; the kit respects it and `doctor` reports it. The kit's agents carry no `model:` header: they inherit the session model.
- **Identity**: the active Google account is read from `~/.gemini/google_accounts.json` (`active` field), never the tokens.

## Gemini troubleshooting

- **Gemini missing**: the kit prepares the files but does not install Gemini. Use the IT procedure, then sign in.
- **Context not loaded**: run `/memory show` in a repository. If layers are missing, check `context.fileName` and any managed policy.
- **Vertex variables ignored**: `selectedType` is still `gemini-api-key`. Choose Vertex AI with `/auth`, or set `security.auth.selectedType` to `vertex-ai` in `~/.gemini/settings.json`.
- **"Your prepayment credits are depleted", HTTP 402**: the AI Studio key has no balance left; top up, or switch to Google sign-in or Vertex AI with `/auth`, as your IT procedure says.
- **"API Keys are Disallowed"**: a Google Cloud policy forbids keys; `gcloud auth application-default login`, Vertex AI with `/auth`, and remove `GEMINI_API_KEY` from the environment.
- **"aiplatform.googleapis.com has not been used", HTTP 403**: the Vertex API is not enabled on the project; `gcloud services enable aiplatform.googleapis.com --project <project>`.
- **"Model fallback activated" in a loop**: the default model is not available on your access; choose one with `/model`, or `model.name` in `~/.gemini/settings.json`.
- **"This account requires setting the GOOGLE_CLOUD_PROJECT…"**: a Code Assist Standard or Enterprise licence with no project declared; `GOOGLE_CLOUD_PROJECT=<project>` in `~/.gemini/.env` or your environment.
- **"When using Vertex AI, you must specify…"**: project and region missing; `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` in `~/.gemini/.env` or your environment.
- **I edited `~/.gemini/30_USER.md`**: it is Gemini's copy since 0.39; at `update`, your edit goes into `~/.ai-kit/context/30_USER.md` when that file did not change since the copy, otherwise the file wins and your edit is in the update's backup.
- **Legacy block in `GEMINI.md`** (0.0.x installs): copy your additions to `~/.ai-kit/context/30_USER.md`, remove the block between the `ai-kit` markers in `~/.gemini/GEMINI.md`, then run `update`.
- **Name already taken**: when one of your skills in `~/.gemini/skills/` or commands in `~/.gemini/commands/` has the name of a kit skill or command, yours is kept and the kit's is installed as `ai-kit-<name>` (`skill_prefix`); a skill of yours named like a kit command counts too, since Gemini makes a command of every skill. The installer says which, and the next `update` takes the plain name back once yours is gone.

Moving to agy: [what changes, what does not](gemini-to-agy.md).
