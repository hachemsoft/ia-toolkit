# Moving from Gemini CLI to Antigravity CLI: what changes, what does not

A page for people moving from Gemini CLI to agy. A two-minute read.

## What does not change

- **Commands**: those of your profile ([profile table](../getting-started.md#3-work-one-command-per-step)) and your `extra_commands` stay the same. Same names, same artifacts (`docs/sdlc/<date>-<slug>/intent.md`, `spec.md`, `plan.md`).
- **Your file**: `~/.gemini/30_USER.md`. Both tools read it.
- **Repositories**: `AGENTS.md`, `GLOSSARY.md`, `REVIEW.md`, `.agents/skills/`. Nothing to migrate.
- **Guardrails and usage review**: same settings in `~/.ai-kit/overrides.json`.

## What changes

- **Launch**: `agy` instead of `gemini`, still from the repository folder.
- **See what is installed**: `/help` in agy lists the commands, which are skills; `agy plugin list` shows the `ai-kit` plugin.
- **A restart** of agy after each kit `update`, so it rediscovers the plugin.
- **Permissions**: agy asks for approval before a shell command or a write. Answer it; "always allow" saves the rule in your agy settings, which the kit never changes. In automatic mode (`agy -p`), denied tools stop the response.

## Troubleshooting

1. `sh scripts/bootstrap.sh doctor --live` (Mac) or `Installer.cmd doctor --live` (Windows): it tells you what to do.
2. The [Troubleshooting](../troubleshooting.md) page.
3. Otherwise, a ticket: it will become a `doctor` check, a line on the page, or an eval case, never a repeated verbal explanation.

## Install or update

From the kit folder: `sh scripts/bootstrap.sh update` (Mac) or `Installer.cmd update` (Windows). The kit detects Gemini and agy and installs for both.
