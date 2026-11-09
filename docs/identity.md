# Signed-in person's identity

The kit detects an identity to write a header in `30_USER.md` when it creates the file, and to compare it with the CLI's active account in `doctor`. This identity is declarative and confirmed by the person. It grants no rights and is not authentication.

## Sources, in order

| Order | Source | Read from | Limit |
| --- | --- | --- | --- |
| 1 | Gemini's active Google account | `~/.gemini/google_accounts.json`, `active` field | empty before sign-in or after sign-out; absent in API key or Vertex mode |
| 2 | Global Git | `git config --global user.email` and `user.name` | depends on git and a filled-in configuration |
| 3 | OS session | login name | not an email |

The git name completes the CLI account's email when both exist. OAuth tokens are never read.

## Behavior

- In the guided installer, the email step shows the detected email as the default: Enter confirms it, or type another. `setup --profile general` (deprecated, still accepted) at a terminal without `--user` shows "Detected identity: …" and waits for Enter, or an email.
- In non-interactive mode, `--user your.email@company` saves the identity; without this option nothing is saved and a line says so.
- `update` keeps the saved identity, unless `--user` is given.
- The state (`~/.ai-kit/state.json`) keeps `user.email`, `user.name`, `user.source`.
- The "Person: …" header is written in `30_USER.md` only when the file is created. Fix it by hand afterwards.

## Team

`setup` no longer asks for a profile (since 3.0; `--profile general` is still accepted, any other value is refused with an explanation). A team is a Team repository: `ai-kit team use <name> --url <URL>` activates it ([Teams](core-source.md#teams)). Nothing personal is stored in the kit repository: IT hands each team its ready-made command. An organization's own Core copy that still declares teams (`context/20-<team>.md`, or `teams` in an older `organization.toml`) gets the team question at `setup`, or `--team <team>`.

## Doctor checks

- Saved identity and its source.
- Mismatch between the CLI's active account and the saved email.
- CLI active account outside the domains listed in `allowed_domains`, read from an `organization.toml` in an organization's own Core copy (compatibility). No list: no check.

## Out of scope

The kit does not force the CLI's authentication type, does not block installation based on identity and does not read tokens. Data access stays controlled by IT and the identity provider.
