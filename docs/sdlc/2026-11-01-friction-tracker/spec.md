# Spec: friction tracker

## Settings
- `organization.toml`, top level, `[friction_tracker]`: `kind` (`gitlab` or `github`), `project` (`group/project`),
  `host` (optional: a self-hosted GitLab or GitHub Enterprise), `labels` (default `["friction"]`), `sources`
  (which frictions are sent: `agent` by default; `person`, `doctor` possible). No token, no URL with credentials.
- `overrides.toml`: `share_frictions = false` turns the sending off for this person, whatever the organization set.
- `update` resolves both into `state.json` (`friction_tracker`), which the script reads: the script stays standard
  library only and never parses TOML.

## Behaviour
- `/friction` run by the agent on its own (auto mode) passes `--source agent`; a person's `/friction` or `ai-kit friction`
  records `person`; `doctor --live` records `doctor`.
- After the local line is written, if a tracker is set and the source is in `sources`: one issue is created through the
  person's CLI (`glab issue create` or `gh issue create`), in a subprocess without a shell, with `--flag=value` forms,
  title `[friction] <category> on /<command>`, body = the sentence, the context (CLI, OS, kit, profile), the id to cite in
  the CHANGELOG. The URL is kept in `~/.ai-kit/frictions-sent.json` (never twice the same friction) and printed.
- Any failure (CLI absent, not signed in, network, timeout 30 s) keeps the friction local, prints one line, exit 0;
  `ai-kit friction --sync` (or `friction.py --sync`) sends what was not sent. `--list` shows the issue URL.
- `doctor`: `[OK]`/`[Check]` on the CLI's presence and `auth status` when a tracker is set; `[Info]` on unsent frictions.
- The guardrail `protected-paths` is unchanged: the script writes under `~/.ai-kit`, allowed by its named exception.

## Contract and compliance
- "Nothing is sent" becomes "nothing is sent unless the organization set a tracker; then the frictions of the chosen
  sources are created as issues by the person's own CLI and account, and `share_frictions = false` stops it".
- The agent still says in one line what it logged, so a sentence sent in auto mode is seen by the person.

## Risks
- A sentence written by the agent may name a client or a file: the rule says not to, the compliance page says it, and
  `sources = ["agent"]` is an organization decision. A sensitive-words check is a later step.
- CLI flags differ between versions: the ones used are the documented long forms; doctor's `auth status` check and the
  sync command make a broken flag visible without losing anything.

## Acceptance (tests)
- Script with a fake `glab`/`gh` on the PATH: issue created with the title, body, labels and repo; URL stored; a second
  run of `--sync` sends nothing; a CLI that fails keeps the friction and `--sync` sends it later; a source not in
  `sources` is never sent; `share_frictions = false` sends nothing.
- `update` writes `friction_tracker` in state.json from the organization file (and removes it when the person opted out).
- doctor lines; schema validation of organization.toml; the command text carries `--source agent` for auto mode.
