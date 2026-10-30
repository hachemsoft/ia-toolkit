# Signed-in person's identity

The kit detects an identity for two uses: writing a header in `30_USER.md` when it is created, and proposing a default profile. This identity is declarative and confirmed by the person. It grants no rights and is not authentication.

## Sources, in order

| Order | Source | Read from | Limit |
| --- | --- | --- | --- |
| 1 | Gemini's active Google account | `~/.gemini/google_accounts.json`, `active` field | empty before sign-in or after sign-out; absent in API key or Vertex mode |
| 2 | Global Git | `git config --global user.email` and `user.name` | depends on git and a filled-in configuration |
| 3 | OS session | login name | not an email |

The git name completes the CLI account's email when both exist. OAuth tokens are never read.

## Behavior

- In interactive mode, `setup` shows "Detected identity: …" and waits for Enter to confirm, or an email to correct it.
- In non-interactive mode, `--user your.email@company` saves the identity; without this option nothing is saved and a line says so.
- `update` keeps the saved identity, unless `--user` is given.
- The state (`~/.ai-kit/state.json`) keeps `user.email`, `user.name`, `user.source`.
- The "Person: …" header is written in `30_USER.md` only when the file is created. Fix it by hand afterwards.

## Profile and team

`setup` asks for the profile, and for the team when the kit has teams (a practices file `practices/20-<team>.md` or settings in `organization.json` `teams`), unless `--profile` and `--team` are given. Nothing personal is stored in the kit repository: IT hands each team its ready-made command, for example `sh scripts/bootstrap.sh setup --profile data-analyst --team finance`.

## Doctor checks

- Saved identity and its source.
- Mismatch between the CLI's active account and the saved email.
- CLI active account outside the domains listed in `organization.json` (`allowed_domains`). Empty list: no check.

## Out of scope

The kit does not force the CLI's authentication type, does not block installation based on identity and does not read tokens. Data access stays controlled by IT and Google Workspace.
