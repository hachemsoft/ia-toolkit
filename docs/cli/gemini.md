# Gemini CLI

What the kit does for Gemini CLI, and what is specific to this CLI. Behavior verified on Gemini CLI 0.65. Shared concepts are in the [CLI matrix](matrice.md).

## What the kit installs

- **Context**: `00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` and `30_USER.md` in `~/.gemini/`, declared in `context.fileName` of `~/.gemini/settings.json`, followed by `GEMINI.md` and `AGENTS.md` for repositories. Personal names already present in `context.fileName` are kept.
- **Skills** in `~/.gemini/skills/`, **commands** in `~/.gemini/commands/*.toml`, **agents** in `~/.gemini/agents/ai-kit-*.md`.
- **Guardrails** that are enabled: scripts in `~/.ai-kit/hooks/` (shared by all CLIs), declared under `hooks.BeforeTool` in groups named `ai-kit-<name>`. Your own hooks are kept.
- **MCP servers** enabled in `overrides.json`: `ai-kit-<name>` entries under `mcpServers`.
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
- **Legacy block in `GEMINI.md`** (0.0.x installs): copy your additions to `~/.gemini/30_USER.md`, remove the block between the `ai-kit` markers in `~/.gemini/GEMINI.md`, then run `update`.
- **Skill installed outside the kit** (for example `gemini skills install`): remove it, or add it to `disabled_skills`.

Moving to agy: [what changes, what does not](gemini-to-agy.md).
