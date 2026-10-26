# Command pivot format

A kit command is written once, in `commands/<name>.md`, and each adapter derives its CLI's form from it (table below and [matrix](cli/matrice.md)). One more CLI means one more adapter ([add a CLI](cli/matrice.md#add-a-cli)); the source files do not change. Skills (`SKILL.md`) and agents (`agents/internal/*.json`) already follow this principle.

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
| `name` | yes | same as the file name; becomes `/<name>` (Gemini, agy) or `$<name>` (Codex) |
| `description` | yes | one line in English, shown by `/help`; for a step, start with its name (`Plan:`, `Build:`) |
| `category` | yes | `workflow` (a step of the cycle, listed under "Steps" in `00_KIT.md`) or `tool` (listed under "Tools") |
| `stage` | for `workflow` | Plan, Design, Build, Test, Deploy or Maintain |
| `skills` | yes, list | the skills the prompt activates; the command is installed only if all of them are; `[]` for a standalone command |
| `artifact` | no | what the command produces, for documentation |
| `order` | no | position in lists (`00_KIT.md`, `/guide`); 1000 by default |

The body is the prompt. `{{args}}` receives what the person types after the command. No triple quotes in the body. Rules for all kit prompts: name the activated skill and say what to do if the activation tool is missing; state the ceremony level in one line; answer in the person's language; mention a domain playbook only "if installed".

## What each adapter does with it

| Target | Output | Details |
| --- | --- | --- |
| Gemini CLI | `~/.gemini/commands/<name>.toml` | `description` and `prompt`, `{{args}}` kept |
| Antigravity CLI | `~/.gemini/config/plugins/ai-kit/skills/<name>/SKILL.md` (in the plugin, where Gemini CLI does not look) | description prefixed with "Kit command /<name>", `{{args}}` replaced by a sentence, activation reserved for the command |
| Codex CLI | `~/.codex/skills/<name>/SKILL.md` and `agents/openai.yaml` when no skill already has that name | same text as for agy; `openai.yaml` reserves activation for `$<name>` |

The header is parsed without dependencies: one key per line, a simple value, a JSON-quoted string or a list `[a, b]`. `python3 -m unittest tests.test_commands tests.test_consistency` checks each file: name, description, category, existing skills, `{{args}}` present, valid generated TOML.

## Override in a repo

In the form the CLI reads, in the repo ([matrix](cli/matrice.md)). The repo wins over the kit. See [add or replace a skill](extending.md).
