# Core and Team sources from Git

Since AI Kit 2, the kit's content (skills, agents, commands, context) can come from a Core Git repository at a
stable tag instead of the copy shipped with the kit. Without a Core source, nothing changes.

## Setting the source

- IT: `managed.toml` `[enterprise] core = "https://gitlab.example.org/ai-toolkit/ai-core.git"` ([managed](managed.md)); no
  question is asked, the managed file is the trust anchor.
- The person: `~/.ai-kit/aikit.toml` `[core] repo = "<URL>"` ([customization](customization.md)); the first `sync` shows the
  canonical URL, the tag and the commit, and asks for confirmation in a terminal.

The repository holds the content folders at its root and a manifest `aikit.toml`:

```toml
schema = 1
name = "core"
kind = "core"
min_engine = "2.0.0"   # optional: an older AI Kit refuses this content
```

## Creating the Core repository

`python3 scripts/export_core.py <empty folder> --git` (in a clone of the kit) writes the kit's content in the Core layout
(`skills/<name>/`, `agents/<name>.md`, commands, `context/`, the manifest) as a Git repository with one commit and the tag
`v<version>`. Nothing is pushed: add the remote your organization chose, push `main` and the tag, protect the tags, then
set `enterprise.core` (IT) or `[core] repo` to its URL. `ai-kit validate --path <folder>` checks a Core or a Team
repository before each tag; a starting point for a Team is in `examples/team-repo/`.

## Commands

| Command | Does | Network |
| --- | --- | --- |
| `ai-kit sync` | installs the highest stable tag `vX.Y.Z` (prereleases `-rc.N` only with `git.allow_prerelease`), never a branch | yes |
| `ai-kit sync --dry-run` | shows what would change, writes nothing | yes |
| `ai-kit sync --from-bundle <file>` | the same, from a `git bundle` of the Core (offline); recorded under the configured URL | no |
| `ai-kit rollback` | back to the previous Core; a second rollback comes back | no |
| `ai-kit update` | re-applies the locked Core | no |

`~/.ai-kit/lock.toml` records the active Core (URL, tag, tag object, commit, tree digest) and the previous one. It is written
in the same transaction as the installed files; `doctor` says when it was edited.

## Safety

- Only `https` (and `ssh` unless `git.allowed_schemes` removes it); no credentials in the URL, no `file://`, `git://` or
  `ext::`. IT can restrict hosts (`git.allowed_hosts`, exact) and groups (`git.allowed_groups`, full prefixes such as
  `ai-toolkit/`).
- Git runs without your global and system configuration (no `insteadOf`, no hooks, no redirects); your credential helper is
  kept only when it is one of `manager`, `manager-core`, `osxkeychain`, `libsecret`, `wincred`.
- A tag seen once must never move: if it does, `sync` stops (`tag-moved`) and changes nothing. Protecting tags on the Git
  server is an operating requirement.
- `git.revoked` (in `managed.toml`) lists commits never activated, even by `rollback`.
- Trees are read file by file: symbolic links, submodules, `.git` folders, Windows reserved names and paths that differ only
  by case are refused.
- A failure before the writes changes nothing; Ctrl+C during the writes puts everything back; a power cut is repaired at the
  next start.

## Teams

A Team repository adds to the Core what one team needs: its own skills and agents, the optional Core resources it turns on,
and its context. One Team is active at a time, for every CLI.

```toml
# aikit.toml at the root of a Team repository
schema = 1
name = "data"
kind = "team"

[defaults]
extra_skills = ["sql-review", "data-check"]   # Core optional resources, or the Team's own
extra_agents = ["sql-reviewer"]
```

Its `skills/<name>/SKILL.md` and `agents/<name>.md` follow the Core's conventions; `context/*.md` becomes the team layer of the
context. A Team never brings commands, policies, hooks or profiles, and cannot replace a Core resource marked
`aikit-protected: "true"`: the activation is refused and nothing changes.

| Command | Does | Network |
| --- | --- | --- |
| `ai-kit team list` | known Teams, the active one, the version in cache | no |
| `ai-kit team use <name> --url <URL>` | adds a Team and activates it (its highest stable tag) | yes |
| `ai-kit team use <name>` | activates a known Team; from the cache when it was downloaded | only the first time |
| `ai-kit team use none` | no Team; its cache stays | no |
| `ai-kit sync` | also updates the active Team to its highest stable tag | yes |
| `ai-kit rollback` | back to the previous Core and Team | no |

IT can restrict Teams in `managed.toml`: `[teams] allowed = ["https://gitlab.example.org/ai-toolkit/"]` (URL prefixes) and
`allow_unknown = false` (only the Teams already known). `ai-kit status` (`--verbose` for details) shows the active Core and
Team without network; `ai-kit init` installs the kit and runs the first `sync` when a Core source is set.
