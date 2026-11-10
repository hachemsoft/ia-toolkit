---
status: accepted
since: 4.0.0
---
# Git sources: stable tags, an anchored origin, tar-free extraction, revocation, optional signatures

`ai-kit sync` fetches only `vX.Y.Z` tags of the Core and the active Team (prereleases only with `allow_prerelease`), never
a branch, and installs the highest. `~/.ai-kit/lock.toml` records the canonical URL, the tag, the tag object, the commit and
a digest of the tree. Trust in the first fetch comes from an explicit anchor: in managed mode, the Core URL and the hosts,
groups and schemes `managed.toml` allows (`enterprise.core`, `git.allowed_hosts`, `git.allowed_groups`,
`git.allowed_schemes`); otherwise a first-use confirmation in a terminal that shows the URL, the tag and the commit. Every
tag seen is remembered; a seen tag that points to another commit blocks (`tag-moved`). Sources are fetched through one helper
(`installer/sources.py`) that runs Git with a neutralized configuration. Trees are read with
`git ls-tree` and `git cat-file`, never through tar: regular files only, no symlink or submodule, every path checked
(traversal, `.git`, Windows reserved names, case collisions). `git.revoked` blocks `sync`, `team use` and `rollback` to a
listed commit. When `managed.toml` lists `git.signers`, a tag must pass `git verify-tag` with an SSH signature from one of
those keys.

**Why**: following a branch with only a few Git settings neutralized let a cache's own configuration rewrite URLs, and
`git archive` plus `tarfile` could write outside the destination. A first install proves nothing without an anchor; managed
mode already has a stronger one.

**Consequences**: outside managed mode, one confirmation the first time a person adds a Core, and no non-interactive first
use. Tag protection on the hosting side is an operating requirement. Signatures cost IT one public-key line per release
manager. No version solver: an integer `schema` and an optional `min_engine` in the source's `aikit.toml`.

**Considered**: trusting the host alone; an initial commit approved by IT (a redeploy per release); mandatory GPG or
Sigstore signatures (a new dependency for no demonstrated gain); `tarfile` with `filter='data'` (missing in early 3.11).
