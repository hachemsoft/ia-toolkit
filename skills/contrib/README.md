# Contributed skills

This is where the skills that people in the organization propose to the kit go, one folder per skill: `skills/contrib/<name>/SKILL.md`. What is under `skills/internal/` is shipped and maintained by the kit maintainers; what is here is maintained by the person named in the catalog.

Rules, checked by the tests:

- an entry in `skills/catalog.json` with `"origin": "contrib"`, `"owner": "<firstname.lastname or team>"`, and `"tier": "optional"`: a contributed skill is never installed by default, each person enables it with one line (`extra_skills` in `~/.ai-kit/overrides.json`);
- a name that does not already exist in the kit; to replace a shipped skill, see [docs/extending.md](../../docs/extending.md);
- an evaluation case in `evals/cases/` that shows the skill in action, or a "Triggers" line in the description that says when it activates.

Promotion: when the usage review shows that a contributed skill is widely used, it moves under `skills/internal/` with `"origin": "internal"`, and joins a profile. Removal: a contributed skill without a reachable owner is removed at the next usage review.
