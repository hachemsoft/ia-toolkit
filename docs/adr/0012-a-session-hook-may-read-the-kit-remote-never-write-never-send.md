---
status: proposed
since: unreleased (spec docs/sdlc/2026-11-01-session-news)
---
# A session-start hook may read the kit's own remote once a day, never write, never send

The kit's only channel to a person was the terminal line of `update`: those who do not run it never hear of a version, and nothing could announce a skill or a training. A `SessionStart` hook, declared by every adapter next to the guardrails, now injects into the agent's context, once, what is new: the installed version's CHANGELOG section, the entries of the repository's `NEWS.md`, and "a newer version is available". For the last two it may run `git fetch` on the kit folder's `origin`, at most once a day, with a short timeout and no credential prompt, reading `VERSION` and `NEWS.md` on `origin/main` without touching the working tree; every failure is silent and only reported by `doctor`. The hook never writes outside `~/.ai-kit/news.json`, never sends anything, and never runs `update`: the agent proposes, the person runs `ai-kit update` in a terminal; a refusal is recorded by `ai-kit news --later` and silences the proposal until the next version. Organization-specific announcements live in the organization's copy of the repository (ADR 0009), and reach workstations through the same remote `update` pulls.

ADR 0004 stays as it is: the installer, `doctor` and the tests still make no network call. This decision bounds the one exception: a read of the kit's own remote, from a hook, under the person's git identity, that the organization can turn off in `defaults` and the person in `overrides.toml`.

**Considered**: announcing only in the terminal at `update` (reaches nobody who does not update); a URL declared in `organization.toml` (a second network access and a second thing to secure, for the same file the remote already holds); the hook running `update` on the person's yes (rewrites the CLIs' settings mid-session and makes Codex and Gemini re-ask trust; against ADR 0006); a `systemMessage` next to the context (rendered differently by each CLI, invisible in some). Rejected for the reasons given.
