# Troubleshooting

With this page you diagnose a problem yourself: what `doctor` and `status` tell you, what each exit code means, and what to do for the messages people meet. Concepts: [architecture](architecture.md).

## First step: `doctor`

```sh
ai-kit doctor          # local checks, no model call, no write
ai-kit doctor --live   # also one real call to the model (may be billed); --yes without a terminal
```

`doctor` prints a summary (what is ready, what to fix, the next step), then one line per check: `[OK]`, `[Check]` (to act on) or `[Info]`. It covers Python, `managed.toml`, the private environment and the `ai-kit` command, Git, the installation and `lock.toml`, where each setting comes from, each CLI's capabilities, the friction tracker, your identity, `USER.md` and `aikit.toml`, every installed file, the guardrails, versions, MCP servers, and skills of the current repo named like kit skills. `--live` names a sign-in, quota, network, proxy or certificate failure and what to ask IT. `AI_KIT_NO_LIVE=1` refuses it.

`ai-kit status` is the short view: the AI Kit version, the active Core and Team (tag, commit), what `rollback` returns to, a newer tag seen at the last sync, the CLIs, whether IT administers the workstation, frictions waiting. `--verbose` adds where each setting comes from, the installed resources, MCP identities and CLI capabilities. No network; the only write is the friction upkeep ([frictions](frictions.md)).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | refused or failed: nothing changed, or everything was put back. Also `doctor` with a `[Check]`, and `validate` with a problem |
| 2 | wrong usage of a command |
| 3 | `managed.toml` cannot be applied: nothing changed, ask IT |
| 130 | interrupted (Ctrl+C) |

The launchers (`Installer.cmd`, `scripts/bootstrap.sh`) add: 2 when Python or the kit folder is unusable, 3 when the kit package did not install, 4 when another installer run is in progress.

## Common messages

| Message | What to do |
| --- | --- |
| `Python 3.11 or newer was not found (commands python3, python).` (or "older than 3.11", "could not be started") | ask IT for Python 3.11+ with `venv` and `pip`, usable by your standard account; do not change company policies |
| `This Python has no venv or pip support …` | ask IT for a complete Python; the kit downloads nothing to work around it |
| `Another run of the kit installer is in progress (process N) …` | wait for the other window; a lock left by a stopped run is taken over |
| `Another ai-kit command is changing files (…). Wait for it to finish, then run again.` | wait; a lock from a dead process is taken over |
| `Kit not installed: run ai-kit init.` | run `ai-kit init` |
| `This AI Kit holds no content and no Core is installed: …` | run the installer from the kit folder, or `ai-kit sync --from-bundle <core bundle>` |
| `No Core source: set [core] repo = "<URL>" in ~/.ai-kit/aikit.toml, or IT sets enterprise.core in managed.toml.` | set `[core] repo`, or ask IT |
| `First use of <URL> needs your confirmation in a terminal: run ai-kit sync there.` | run `ai-kit sync` in a terminal and check the URL, tag and commit shown |
| `git was not found: install Git (IT can provide it), then run the command again.` | ask IT for Git 2.29 or newer |
| `git ls-remote failed (auth): …` (or `network`, `not-found`) | sign in to the Git host with your usual credential helper, check the network or the URL |
| `Git URL refused (…)`, `Host … is not in git.allowed_hosts …`, `This Team is not in teams.allowed (managed.toml): …` | the origin is not allowed; ask IT or use the URL it publishes |
| `No stable tag vX.Y.Z in the source: ask its owner to publish one.` | the repository has no `vX.Y.Z` tag yet |
| `Tag … now points to another commit. Nothing was changed. …` | tell the repository's owner: a published tag must never move |
| `Tag … is not signed by a key IT lists (managed.toml git.signers): nothing was changed.` | the tag owner signs it with an allowed key |
| `… is revoked by IT (managed.toml git.revoked) …` | IT withdrew that version; wait for a new tag |
| `Unknown Team <name>: give its repository URL, ai-kit team use <name> --url <URL> (or run it in a terminal).` | add `--url` |
| `Nothing to roll back to: lock.toml has no previous configuration.` | there is only one configuration so far |
| `… is not in the local cache: run ai-kit sync (network needed).` | run `ai-kit sync` with network |
| `The content … needs AI Kit X.Y.Z or newer; this one is …` | install the newer AI Kit (new ZIP, or `git pull` in a clone) first |
| `<path>: refused because it is not owned by root; …` (any `managed.toml` refusal) | exit code 3; IT fixes the file |
| `MCP server <name> is required … nothing was changed.` | see [MCP](mcp.md); approve it in a terminal, or ask IT |
| `… modified locally: <path>` | a file the kit installed was edited: move your change to `USER.md` or your `aikit.toml`, restore the file, run again |
| `[Check] <file> was modified by hand: restored to the kit version; your copy: …` | normal for a rule layer (`00_KIT.md`, `10_…`, `20_…`): personal preferences go in `USER.md` |
| `Blocked by the kit: …` (in the agent) | a guardrail refused the action ([guardrails](hooks.md)); do it yourself if it is right |
| `doctor --live makes a real call to the model, refused because AI_KIT_NO_LIVE=1 is set.` | unset the variable if you accept the call |
| `uninstall needs a confirmation: add --yes, or --dry-run to see what would be removed.` | add `--yes` |

## Other symptoms

- **`ai-kit` not recognised after `init`**: open a new terminal. On a shell the kit does not recognise, `init` prints the line to add to your startup file.
- **`ai-kit` runs an old version**: another copy comes first on your PATH. `ai-kit --version` says which copy runs; `doctor` lists every copy.
- **A command from the docs is missing**: it is optional. Add it with `extra_commands` in your `aikit.toml`, then `ai-kit sync --offline`. `00_KIT.md` lists what is installed.
- **A kit skill or command is named `ai-kit-<name>`**: one of yours already had the name; yours is kept. Rename yours, then `ai-kit sync --offline`.
- **`USER.md` not applied**: it must be plain UTF-8 text under that exact name; `doctor` says what is wrong.
- **A friction issue was not created**: the friction is kept locally. Install and sign in to `glab` or `gh`, then `ai-kit friction --publish`.
- **The questions show odd characters**: add `--plain`.

## Manual restore

Every run that changes files keeps a dated folder in `~/.ai-kit/backups` with the previous files, at their path relative to your home folder. Close the CLI and copy them back. Prefer `ai-kit rollback` for the Core and Team.

## Team rule

A support ticket is never solved verbally twice: it becomes a `doctor` check, a line on this page, or an eval case.
