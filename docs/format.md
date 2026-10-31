# Command pivot format

A kit command is written once, in `commands/<name>.md`, and each adapter derives its CLI's form from it (table below and [matrix](cli/matrice.md)). One more CLI means one more adapter ([add a CLI](cli/matrice.md#add-a-cli)); the source files do not change. Skills (`SKILL.md`) and agents (`agents/internal/<category>/*.json`) already follow this principle.

## The file

```markdown
---
name: intent
description: "Plan: capture an idea, ticket or incident as intent.md"
category: workflow
stage: Plan
skills: [grill-with-docs]
artifact: intent.md
order: 10
---

Activate the grill-with-docs skill ...

Input: {{args}}
...
```

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | same as the file name; becomes `/<name>` (Gemini, agy, Claude Code) or `$<name>` (Codex); `<prefix><name>` (`skill_prefix`, `ai-kit-` by default) when one of your own skills or commands already has the name |
| `description` | yes | one line in English, shown by `/help`; for a step, start with its name (`Plan:`, `Build:`) |
| `category` | yes | `workflow` (a step of the cycle, listed under "Steps" in `00_KIT.md`) or `tool` (listed under "Tools") |
| `stage` | for `workflow` | Plan, Design, Build, Test, Deploy or Maintain |
| `skills` | yes, list | the skills the prompt activates; the command is installed only if all of them are; `[]` for a standalone command |
| `artifact` | no | what the command produces, for documentation |
| `order` | no | position in lists (`00_KIT.md`, `/guide`); 1000 by default |

The body is the prompt. `{{args}}` receives what the person types after the command. No triple quotes in the body. Rules for all kit prompts: name the activated skill and say what to do if the activation tool is missing; state the ceremony level in one line (a command that makes a change, like `/build` and `/intent`, makes it the fixed first line `Level: quick|standard|full` with its reason, even when it then asks, stops or is blocked); answer in the person's language; mention a domain playbook only "if installed".

## What each adapter does with it

| Target | Output | Details |
| --- | --- | --- |
| Gemini CLI | `~/.gemini/commands/<name>.toml` | `description` and `prompt`, `{{args}}` kept; `<prefix><name>.toml` when the name is taken |
| Antigravity CLI | `~/.gemini/config/plugins/ai-kit/skills/<name>/SKILL.md` (in the plugin, where Gemini CLI does not look) | description prefixed with "Kit command /<name>", `{{args}}` replaced by a sentence, activation reserved for the command |
| Codex CLI | `~/.codex/skills/<name>/SKILL.md` and `agents/openai.yaml`, unless a kit skill already has that name | same text as for agy; `openai.yaml` reserves activation for `$<name>`; under `<prefix><name>` when one of your skills has the name |
| Claude Code | `~/.claude/commands/<name>.md` | `description` header, `{{args}}` replaced by `$ARGUMENTS`; under `<prefix><name>` when one of your own skills or commands has the name |

The header is parsed without dependencies: one key per line, a simple value, a JSON-quoted string or a list `[a, b]`. `python3 -m unittest tests.test_commands tests.test_consistency` checks each file: name, description, category, existing skills, `{{args}}` present, valid generated TOML.

## Override in a repo

Possible only where the CLI supports it, in the form it reads: see the row "Override a command in a repository" of the [CLI matrix](cli/matrice.md). Elsewhere, a repo file with the command's name does not reliably replace the kit's: write a skill with a name of its own to the project and say in `AGENTS.md` when to use it ([add or replace a skill](extending.md#for-a-repo)).
