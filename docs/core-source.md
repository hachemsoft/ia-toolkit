# Core source from Git

Since AI Kit 2, the kit's content (skills, agents, commands, practices, profiles) can come from a Core Git repository at a
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

## Commands

| Command | Does | Network |
| --- | --- | --- |
| `ai-kit sync` | installs the highest stable tag `vX.Y.Z` (prereleases `-rc.N` only with `git.allow_prerelease`), never a branch | yes |
| `ai-kit sync --dry-run` | shows what would change, writes nothing | yes |
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
