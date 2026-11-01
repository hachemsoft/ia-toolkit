# Contributed agents

This is where the agents that people in the organization propose to the kit go, one file per agent: `agents/contrib/<name>.md`, in the same format as the kit's own agents (a front matter with `name`, `description`, `tools`, `max_turns`, `timeout_mins`, then the instructions). What is under `agents/internal/` is shipped and maintained by the kit maintainers; what is here is maintained by the person named in the catalog.

Rules, checked by the tests:

- an entry in `agents/catalog.json` with `"origin": "contrib"`, `"owner": "<firstname.lastname or team>"` and a `"version"` (`1.0.0` to start): a contributed agent is in no profile; each person enables it with one line (`extra_agents` in `~/.ai-kit/overrides.toml`);
- a name that does not already exist in the kit;
- a version raised at every change (patch for a wording, minor for a behaviour added, major when what it reports or needs changes), then `python3 scripts/versions.py --update`.

Promotion: when the usage review shows that a contributed agent is widely used, it moves under `agents/internal/<category>/` with `"origin": "internal"`, and joins a profile. Removal: a contributed agent without a reachable owner is removed at the next usage review.
