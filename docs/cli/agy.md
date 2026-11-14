# Antigravity CLI (agy)

What the kit does for agy. Verified on agy 1.4.7, agent tools and logs again on 1.4.12. Shared concepts:
[CLI matrix](matrice.md).

## Install

`ai-kit init` installs the agy output when `agy` is present or `~/.gemini/config/` exists (`--target auto`); later
activations keep the CLIs chosen. `--target agy` installs agy alone, `--target both` Gemini CLI and agy, `--target all`
every supported CLI; a `--target` replaces the previous choice and removes what the kit had put in the other CLIs.
Restart agy after an activation: it discovers a plugin only at startup.

## What is shared with Gemini CLI

agy reads `~/.gemini/skills/`, so kit skills, playbooks and repo skills (`.agents/skills/`) are visible on both sides, as
are `AGENTS.md`, `GEMINI.md` and `.agents/rules/`. Moving from Gemini CLI to agy changes the launch command (`agy` instead
of `gemini`), the way to list commands (`/help`; `agy plugin list` shows the `ai-kit` plugin) and the permission prompts;
commands, artifacts, `USER.md`, repositories and `~/.ai-kit/aikit.toml` stay the same.

## What the kit adds: a plugin

`~/.gemini/config/plugins/ai-kit/`, validated by `agy plugin validate` in `doctor`:

| File | Role |
| --- | --- |
| `plugin.json` | name, description, kit version |
| `rules/AGENTS.md` | always-on rules that include the layers and `USER.md` by path (`@[00_kit](~/.ai-kit/context/00_KIT.md)`, …): no copy |
| `agents/ai-kit-*.md` | the installed agents, with agy's tool names (`view_file`, `grep_search`, `list_dir`, `run_command`) |
| `hooks.json` | the guardrails and the `whats-new` hook; the scripts read agy's payload (`toolCall.args.CommandLine`) and always answer with a `decision`, which agy requires (an answer without one is refused, with no reason shown): `deny` to refuse, `ask` to let the call through, which hands it to agy's own permission flow (`allow` would approve it without your rules or prompt: seen with agy 1.5.8, fixed in 4.7.1); `SessionStart` answers in agy's own contract, `{"injectSteps": [{"systemMessage": {"systemMessage": "…"}}]}`, recognised by the input's `conversationId` |
| `mcp_config.json` | the MCP servers that are on |
| `skills/<name>/` | one command skill per installed command: agy has no command files, but every skill is a `/<name>` command; they live in the plugin because Gemini CLI would show each kit command twice |

`protected-paths` always blocks agent writes to the plugin folder.

## Authentication: Google account or Google Cloud project

By default agy signs in with the person's Google account and its individual quota ("Individual quota reached", HTTP 429,
until the reset). To bill a Google Cloud project instead: `AGY_ADC_AUTH=1` in the shell, credentials from
`gcloud auth application-default login`, and a quota project with the Agent Platform API enabled. The quota project of the
credentials counts, not `GOOGLE_CLOUD_PROJECT`.

```sh
gcloud auth application-default set-quota-project my-gcp-project
export AGY_ADC_AUTH=1   # in your shell profile to make it permanent
agy
```

A 403 "Agent Platform API has not been used in project …": `gcloud services enable aiplatform.googleapis.com --project my-gcp-project`.
The kit does not set this variable.

## Permissions: each person's, never the kit's

agy asks before a shell command or a write and offers to remember the answer in `permissions.allow` of
`~/.gemini/antigravity-cli/settings.json`. The kit never reads, writes or changes this file (checked by a test), and
its `protected-paths` guardrail refuses an agent's write to it: the answers stay yours. An organization that wants a
baseline distributes it outside the kit.

## Known limits

- **Parallel agents**: with the `parallel` setting, a sub-agent that writes works in a worktree the main agent creates; agy has no worktree option of its own. In `agy -p` the main agent can return before its sub-agent has finished: the answer does not say the work is done ([parallel agents](../parallel-agents.md)).
- **Print mode**: agy drops the whole answer when a tool asks for a permission it cannot request, so commands that read
  the repo fail in `agy -p` until the person has approved read rules. Interactive mode works.
- **Write tool**: `protected-paths` recognises tools whose name contains `write`, `replace` or `edit` and looks for the
  path in the arguments (`TargetFile`, `AbsolutePath`, `FilePath`, `file_path`, `path`…); to be confirmed on a real write.
- **User-only skills**: agy has no such field; they may activate on their own.
- **Logs**: `usage` reads `~/.gemini/antigravity-cli/history.jsonl` and, read-only, `conversations/*.db` (skill files read,
  `ai-kit-*` agents invoked); an unreadable conversation is skipped; no error events.
- **`doctor --live`**: one real call with `agy -p`, which may be billed; a failure is explained (sign-in, quota, API,
  network, proxy, certificate).
- When one of your skills has the name of a kit skill or command skill, yours is kept and the kit's is installed as
  `ai-kit-<name>`; with Gemini CLI also installed, `doctor` reports kit skills hidden by `~/.agents/skills`.
