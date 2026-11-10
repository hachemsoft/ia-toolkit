# Contributed skills

Skills that people in the organization propose to the Core, one folder per skill: `skills/contrib/<name>/SKILL.md`. What is under `skills/internal/` is maintained by the kit maintainers; what is here, by the owner named in the skill's front matter. How to write one: [add or change a component](../../docs/extending.md#add-or-change-a-component).

Rules (checked by the tests):

- front matter `metadata`: `aikit-origin: "contrib"`, `aikit-owner: "<firstname.lastname or team>"`, `aikit-default: "false"` (never installed by default: a Team or a person turns it on with `extra_skills`), and `aikit-version` (`1.0.0` to start);
- a name that does not already exist in the kit;
- an evaluation case in `evals/cases/` that shows the skill in action, or a "Triggers" line in the description that says when it activates;
- the version raised at every change (patch for a wording, minor for a behaviour added, major when what it produces or needs changes), then `python3 scripts/versions.py --update`.

Promotion: a contributed skill the usage review shows widely used moves under `skills/internal/` with `aikit-origin: "internal"`. Removal: one without a reachable owner goes at the next usage review. A skill for one team only belongs in that team's Team repository.
