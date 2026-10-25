# Project layer

The kit prepares the workstation; the repo carries its own context. After the global layers, the agent reads the `AGENTS.md` of the repo and of the folders it goes through (and its CLI's own files, see the [matrix](cli/matrice.md)). That is where business rules, commands and preference overrides live.

## Expected files in a repo

| File | Role | Maintained by |
| --- | --- | --- |
| `AGENTS.md` | short table of contents: start, test, data, conventions, where the rest is | `writing-for-agents` |
| `GLOSSARY.md` | one term, one definition, synonyms to avoid | `domain-modeling` |
| `docs/adr/NNNN-slug.md` | decisions that are costly to undo, surprising without context, the result of a real trade-off | `domain-modeling` |
| `REVIEW.md` | review passes, meaning of Important, cap on nits | `init-project-context`, `/review` |
| `docs/sdlc/<date>-<slug>/` | `intent.md`, `spec.md`, `plan.md` of a change; one folder per change; `spec.md` versioned, `intent.md` and `plan.md` local (`.gitignore`) | `/intent`, `/spec`, `/build` |
| `docs/agents/issue-tracker.md` | issue tracker and triage labels, only when `setup-workflow` has been run | `setup-workflow`, `/map`, `/triage` |
| `.agents/skills/<name>/` | repo-specific skills, taking priority over the kit on equal names | the repo team |

A repo that already has a CLI-specific context file keeps it; that file points to `AGENTS.md` to avoid duplication (an `@AGENTS.md` line, for example; see the CLI's page in the [matrix](cli/matrice.md)).

## First setup

In the repo, ask "Initialize the project context". The `init-project-context` skill reads the repo, proposes `AGENTS.md`, `GLOSSARY.md` and `REVIEW.md` from its templates, proposes the `.gitignore` lines for `intent.md` and `plan.md`, waits for a confirmation per file and never replaces an existing file. It does not copy the artifact templates into the repo and does not create an empty ADR: the `docs/adr/` folder appears with the first decision.

## Monorepo: several teams, one repo

A repo shared by several teams (for example a dbt project shared by finance and marketing) is organized in zones: the root carries what is shared, each team folder carries what is its own.

| Where | What | Owner |
| --- | --- | --- |
| root | shared `AGENTS.md` (including "Verifying your work"), `REVIEW.md`, `.ai-kit/protected-paths`, shared `GLOSSARY.md` or `GLOSSARY-MAP.md` | the team that runs the platform |
| `<zone>/` | the zone's `AGENTS.md`, its glossary if it has one, its artifacts in `<zone>/docs/sdlc/` | the zone team |

- **Start the agent from your zone's folder** (`cd finance` then the CLI). It then reads the root `AGENTS.md` and the zone's. Started at the root, it asks which zone you are working in.
- **Checks** follow the general rule: what changed and what depends on it, whatever the team. `/test`, `/review` and `/ship` name the other zones touched (for dbt, the models that depend on the changed models), so their owners review. With a production manifest, `dbt build --select state:modified+ --defer --state <manifest>` rebuilds only what changed and reads the rest from production.
- **The root's protected paths** also apply when the agent starts in a zone; a zone can add its own `.ai-kit/protected-paths`.
- **A shared metric** has a single definition, in the shared glossary, with a named owner; zone glossaries point to it.
- **Repo skills** live in `.agents/skills/` at the root and apply to everyone: prefix them with the zone (`finance-cloture-mensuelle`) and say in their description what they apply to.
- **Too much context**: started at the root, the agent can also read the subfolders' `AGENTS.md` files; each CLI has its own way to limit what it scans (see its page).
- **Who reviews what**: a `CODEOWNERS` file makes GitLab or GitHub enforce it.

```
# CODEOWNERS
/AGENTS.md            @equipe/plateforme
/REVIEW.md            @equipe/plateforme
/.ai-kit/             @equipe/plateforme
/finance/             @equipe/finance
/marketing/           @equipe/marketing
```

## Override preferences

For a project to enforce a rule different from `30_USER.md` (language, level of detail, workflow), write it in `AGENTS.md` under the same heading as in the personal file. `00_KIT.md` tells the agent that the project wins.

## What the kit does not do

It does not write to repos, push anything or create merge requests (MR). Skills write artifacts on request; a commit happens only if the person accepted it in the session (`/build` asks once); nothing is pushed.
