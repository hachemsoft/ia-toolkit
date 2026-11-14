# Parallel agents

With this page you know what the `parallel` setting does, when it is worth turning on, what each CLI really does with it, and what it costs. It is off by default. Concepts: [architecture](architecture.md).

## What it is

One setting adds one short rule to the kit context (`00_KIT.md`), which every CLI reads. The rule tells the agent when to give parts of a task to sub-agents at the same time, and how the ones that write files stay out of each other's way. Nothing else is installed: no hook, no script, no new agent.

Without the setting, the agent works as each CLI does by default. One exception: `/review` runs the read-only reviewers of a change at risk at once, whatever the setting ([ADR 0029](adr/0029-risk-based-security-review-by-independent-reviewers.md)); their cost is that of three reviewers, at once or not.

## When it is worth it

| Situation | Parallel agents |
|---|---|
| One task, one thing to change | no: one agent is faster and cheaper |
| Several things to read or check that do not depend on each other (review, investigation, verification) | yes: sub-agents that read cannot collide |
| Several independent changes to write (tickets of one spec) | yes, each writer in its own git worktree |
| Parts that depend on each other's result | no: they run one after the other anyway |

Several agents at once use several times the tokens of one. On a CLI billed by use, that is several times the cost: this is why the setting is off by default and the rule says "otherwise work alone".

## Turning it on

```toml
# ~/.ai-kit/aikit.toml
[agents]
parallel = true
```

Then `ai-kit sync --offline`. A Team turns it on for its members in its own `aikit.toml`:

```toml
[defaults]
parallel_agents = true
```

A member turns it off again with `[agents] parallel = false`. `ai-kit status --verbose` shows where the value comes from. IT cannot impose it in `managed.toml`.

## The rule

This text is added to `00_KIT.md`, word for word:

```text
## Parallel agents
When a task splits into two or more independent parts, each worth an agent of its own, give them to sub-agents at the same time instead of one after the other; otherwise work alone.
- A sub-agent that only reads works in place.
- A sub-agent that writes files works in its own git worktree, on its own branch: create it before you start the sub-agent, give it the absolute path, say so to the person and get their agreement once for the commits on these branches.
- When it is done, bring its work back, then remove the worktree, never with `--force`.
- When a worktree cannot be created (not a git repository, or the sandbox refuses), only one sub-agent writes at a time.
```

The kit's own agents (reviewers, investigator, verifier) only read: they never need a worktree. The rule matters for the sub-agents a CLI provides to write code, and for the optional `implement-spec` skill, which follows it.

## What each CLI does

A worktree is a second working folder of the same repository, on its own branch: two agents that write in two worktrees cannot overwrite each other.

| | Gemini CLI | agy | Codex | Claude Code |
|---|---|---|---|---|
| A sub-agent in its own worktree, built into the CLI | no | no | no | yes: `isolation: worktree` in an agent's definition |
| A sub-agent in a worktree the main agent creates, as the rule asks | works | works | refused: the sandbox does not let the agent write to `.git`, so it cannot run `git worktree add` | works |
| What the rule gives | parallel writers, each in a worktree | parallel writers, each in a worktree | parallel readers; one writer at a time | parallel writers, each in a worktree |
| A whole session in a worktree, started by you | `gemini --worktree` (experimental: `"experimental": {"worktrees": true}` in its settings) | none | `codex --worktree`: its sub-agents share that one worktree | `claude --worktree` |

How this was established, on one macOS workstation, on 2026-11-13:

| CLI | Version | Evidence |
|---|---|---|
| Gemini CLI | 0.65.0 | its agent definition schema has no worktree field (source); one real run: a sub-agent wrote and committed inside the worktree the main agent created, nothing in the main folder |
| agy | 1.4.12 | no worktree option in its help; one real run, same result. In `--print` mode the main agent returned before its sub-agent had finished |
| Codex | 0.167.0 | its sub-agent spawn has no folder or worktree argument (source); `git worktree add` under its `workspace-write` sandbox fails with `Operation not permitted` on `.git`; one real run with `--worktree`: the session and its sub-agent worked in the same managed worktree under `~/.codex/worktrees`, and the commit passed |
| Claude Code | 2.1.323 | its documentation for `isolation: worktree` and `--worktree`; one real run by instruction, same result as Gemini CLI |

Each real run was a single run on a one-file task. It shows the mechanism works, not that an agent keeps to it on a long task.

## What comes with a worktree

- **A fresh checkout.** Dependencies are not installed there, and the files git ignores are absent: `.env`, and the kit's local `intent.md` and `plan.md`.
- **Its own branch.** Bringing the work back is a merge or a cherry-pick; a conflict between two sub-agents shows up then, not before.
- **Commits.** A sub-agent that works on a branch commits there. The kit's rule on commits still holds: the agent asks your agreement, once for these branches.
- **Cleanup.** A worktree left behind keeps its branch checked out. `git worktree list` shows them; `git worktree remove <path>` removes a clean one. The `git-guard` guardrail refuses `git worktree remove --force` ([guardrails](hooks.md#git-guard)).

## Limits

- The rule is text the agent reads. No hook checks that a sub-agent stays inside its worktree; a sub-agent that changes folder writes elsewhere.
- No evaluation covers this rule yet: whether an agent applies it well on a real task is not measured.
- The table above is true for the versions named. A CLI release can change it; the weekly drift check does not cover it.
- On Windows nothing was tried.
