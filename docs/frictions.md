# Frictions and usage review

With this page you log what gets in the way, choose how the agent captures it, send it to your team's tracker, and run the usage review that slims the kit down on facts. Concepts: [architecture](architecture.md).

## Log a friction

A friction is one sentence about something that slowed you down: a command that did not do what it says, a skill that fired for nothing, a guardrail in the way, a wrong page.

| Where | How |
| --- | --- |
| in the agent | `/friction <what happened>` |
| in a terminal | `ai-kit friction --category <category> --text "<one sentence>"` |

Categories: `command`, `skill`, `guardrail`, `rule` (the agent went against a written rule), `docs`, `tool`, `auth`, `other`. The text is 1 to 300 characters.

## Capture modes

`[frictions] capture` in your `aikit.toml` (IT's `managed.toml` can impose it):

| Mode | The agent |
| --- | --- |
| `propose` (default) | offers in one line to log a friction when you correct it, a check is red after "done", you give up or repeat a request, it works around a skill or a guardrail, the ceremony was out of proportion, or it broke a written rule |
| `auto` | logs it itself in those cases (`--source agent`), says so in one line, and resumes |
| `off` | never offers |

## The local file

Guardrail refusals are counted apart, by the guardrails themselves ([guardrails](hooks.md#counting-refusals)). Frictions go to `~/.ai-kit/frictions.jsonl`, one line each, readable by you only. Each line carries the date, category, command, CLI, the kit version, team and system. Before a friction is stored, secrets, emails, home paths and internal host names are redacted. The same friction told twice has the same fingerprint.

| Command | Shows |
| --- | --- |
| `ai-kit friction --list [N]` | the last N frictions (10), and the issue URL of those sent |
| `ai-kit friction --analyze` | the frictions grouped, the most frequent first |

**Upkeep.** At session start and at `ai-kit status`, frictions older than the retention are purged: 30 days, or IT's `frictions.retention_days`.

## Publish to the tracker

Nothing leaves the workstation unless IT sets a tracker in `managed.toml`:

```toml
[frictions.tracker]
kind = "gitlab"                # or github
project = "group/project"
host = "gitlab.example.org"
labels = ["friction"]          # default
sources = ["agent"]            # default: only what the agent logged on its own; add "person"
```

Each friction becomes one issue, created by your own `glab` or `gh`, signed in by you. The kit holds no token. A failure keeps the friction local.

| `publication` | Set by | Effect |
| --- | --- | --- |
| `approval` (default) | IT | frictions wait; you send them with `ai-kit friction --publish` in a terminal |
| `auto` | IT only | sent as soon as logged |
| `disabled` | IT, or you in your `aikit.toml` | stays local |

The agent may not publish: `friction --publish` is refused to it ([guardrails](hooks.md)). At session start it says how many frictions wait for your approval; `doctor` shows the tracker's state.

## Usage report

```sh
ai-kit usage                         # last 42 days
ai-kit usage --since 90 --json report.json
ai-kit usage --min-sessions 5 --min-prompts 20
```

The report reads, locally, the session logs each CLI already writes, and counts: commands typed, skills activated, agents called, errors where the CLI logs them, frictions by category, and the share of sessions where the kit did something. By difference, it lists what was never used. It holds no prompt text, file name or identity; the JSON can be shared as is. Nothing is sent.

- A skill or agent is called unused only when every session comes from a CLI whose logs show it; otherwise it is "not observable".
- Logs that exist but are not recognised are reported (`[Check]`), not counted as zero.
- Below 10 sessions and 50 prompts, nothing is recommended. Above, the candidates are installed skills of the Core default selection, of category `workflow` or `tool`, never activated and required by nothing used (a typed command or an activated skill).

## Usage review

The team's procedure to keep the kit small. Every installed skill costs context in every prompt, and every component is a possible support ticket.

1. Each person runs `ai-kit usage --json <file>` and shares it, if they want to.
2. The team aggregates: `python3 scripts/usage-aggregate.py <files>` (Markdown ready to paste); `--draft-issues` prints one ticket draft per group of frictions. Nothing is created automatically.
3. Each group of frictions becomes one fix: a `doctor` check, a [troubleshooting](troubleshooting.md) line, an eval case, or a prompt change.
4. Each candidate: take it out of the default selection (set `aikit-default: "false"`), or write in one line why it stays.
5. Each command never typed: check that `/guide` suggests it and that its description is clear; fix the router or the description, not the command.
6. A written rule that `rule` frictions show broken again becomes a check (an eval case, a guardrail, a `doctor` check).
7. Release, and name the friction ids a fix answers in the `CHANGELOG`.

| The review can | The review never |
| --- | --- |
| make a default skill optional | deletes a skill without a team decision |
| replace a base skill with a short in-house version, same name | renames a command or changes an artifact |
| fix `/guide` or a description | touches the guardrails |
| shorten the kit's context | acts automatically: the report proposes, people decide |

Domain playbooks and reference skills are never proposed for removal: they fire on the nature of the task, not its frequency. The report measures use, not quality: that is why the review stays human.
