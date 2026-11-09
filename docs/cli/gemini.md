# Gemini CLI

What the kit does for Gemini CLI. Behaviour verified on Gemini CLI 0.65. Shared concepts: [CLI matrix](matrice.md).

## What the kit installs

- **Context**: copies of `00_KIT.md`, `10_COMPANY.md`, `20_TEAM.md` and `USER.md` from `~/.ai-kit/context/` in `~/.gemini/`
  (Gemini imports only files located there), declared in `context.fileName` of `~/.gemini/settings.json` before `GEMINI.md`
  and `AGENTS.md`. Your own names in `context.fileName` are kept. Edit `~/.ai-kit/context/USER.md`, then run
  `ai-kit sync --offline`; an edit made to the copy goes into the file when the file did not change since the copy.
- **Skills** in `~/.gemini/skills/`, **commands** in `~/.gemini/commands/*.toml`, **agents** in `~/.gemini/agents/ai-kit-*.md`.
- **Guardrails** that are on: scripts in `~/.ai-kit/hooks/`, declared under `hooks.BeforeTool` in groups named
  `ai-kit-<name>`; your own hooks are kept. The `whats-new` hook is a group under `hooks.SessionStart` without matcher; it
  answers in JSON only. Gemini warns once about a hook whose command changed: expected after an activation.
- **MCP servers** that are on: `ai-kit-<name>` entries under `mcpServers`.
- **Default setting**: `skills.enabled`, only if missing.

## Authentication and model

Never set by the kit: use `/auth` and `/model`, or `~/.gemini/settings.json` and `~/.gemini/.env` as your IT procedure says
(for example `GOOGLE_CLOUD_PROJECT` for a Code Assist Standard or Enterprise licence; `GOOGLE_GENAI_USE_VERTEXAI`,
`GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` with `selectedType: vertex-ai` for Vertex AI). `doctor --live` names the
missing setting when the call fails.

## Check in Gemini CLI

`/memory show` (the four files before the repository context), `/commands list`, `/skills list`, `/agents list` (after
`/agents reload`), `/mcp`.

## Protected configuration

`protected-paths` always blocks agent writes to `~/.gemini/settings.json` and `~/.gemini/.env`, and `dbt-prod-guard`
ignores `AI_KIT_ALLOW_PROD` when it is set in `~/.gemini/.env` or a repo `.env`, which Gemini loads into its environment.

## Specifics

- Gemini CLI turns every skill of `~/.gemini/skills/` into a `/<skill>` command, and renames both when two share a name: no
  kit skill shares a command's name, and agy's command skills live in its plugin, where Gemini does not look.
- **`~/.agents/skills`**: Gemini reads it too, and it wins over `~/.gemini/skills` on equal names ("Skill conflict
  detected"). `doctor` lists the kit skills hidden this way.
- **Subfolder context**: launched at a repo root, Gemini also reads the subfolders' `AGENTS.md` and `GEMINI.md`; a
  `.geminiignore` limits what it walks.
- **Non-interactive mode (`gemini -p`)**: the skill activation tool is not exposed; `plan` mode also blocks skills.
- **Sub-agents**: on by default; `experimental.enableAgents = false` disables them, which the kit respects and `doctor`
  reports.
- **User-only skills**: Gemini has no such field; they may activate on their own.
- **Identity**: the active Google account is read from `~/.gemini/google_accounts.json` (`active`), never the tokens.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Gemini missing | the kit prepares the files but does not install Gemini: follow the IT procedure, then sign in |
| context not loaded | `/memory show` in a repo; check `context.fileName` and any managed policy |
| Vertex variables ignored | `selectedType` is still `gemini-api-key`: choose Vertex AI with `/auth`, or set `security.auth.selectedType` to `vertex-ai` |
| HTTP 402 "prepayment credits are depleted" | the AI Studio key has no balance: top up, or switch to Google sign-in or Vertex AI |
| "API Keys are Disallowed" | `gcloud auth application-default login`, Vertex AI with `/auth`, and remove `GEMINI_API_KEY` from the environment |
| HTTP 403 "aiplatform.googleapis.com has not been used" | `gcloud services enable aiplatform.googleapis.com --project <project>` |
| "Model fallback activated" in a loop | choose a model with `/model`, or `model.name` in `~/.gemini/settings.json` |
| "requires setting the GOOGLE_CLOUD_PROJECT" | `GOOGLE_CLOUD_PROJECT=<project>` in `~/.gemini/.env` or your environment |
| "When using Vertex AI, you must specify…" | `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` in `~/.gemini/.env` or your environment |
| a kit skill or command appears as `ai-kit-<name>` | one of your skills or commands had the name; yours is kept, and the plain name comes back once yours is gone |
