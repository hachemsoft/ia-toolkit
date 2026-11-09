# Contributed agents

Agents that people in the organization propose to the Core, one file per agent: `agents/contrib/<name>.md`, in the same format as the kit's own agents (front matter with `name`, `description`, `tools`, `max_turns`, `timeout_mins`, then the instructions). How to write one: [add or change a component](../../docs/extending.md#add-or-change-a-component).

Rules (checked by the tests):

- front matter `metadata`: `aikit-origin: "contrib"`, `aikit-owner: "<firstname.lastname or team>"`, `aikit-version` (`1.0.0` to start); never in the default selection: a Team or a person turns it on with `extra_agents`;
- a name that does not already exist in the kit;
- the version raised at every change, then `python3 scripts/versions.py --update`.

Promotion: a contributed agent the usage review shows widely used moves under `agents/internal/<category>/` with `aikit-origin: "internal"`. Removal: one without a reachable owner goes at the next usage review.
