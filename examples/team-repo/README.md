# Team repository (example)

What a team adds on top of the AI Kit Core: its own skills (`skills/<name>/SKILL.md`), agents (`agents/<name>.md`), the
Core optional resources it turns on (`[defaults]` in `aikit.toml`) and its context (`context/*.md`, the team layer). A Team
never brings commands, policies or hooks, and cannot replace a protected Core resource. Check it with
`ai-kit validate --path .`, then tag a release `vX.Y.Z`. See docs/repositories.md in the kit.
