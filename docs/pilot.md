# Pilot: procedure

Goal: fix the kit on real tickets before opening it to the whole team, and check that nobody needs help to get started. A small group is enough, for example two analysts and one developer, for one to two weeks. The choice of people and dates belongs to the organization.

## Day 1, per person (fifteen minutes)

1. Get the kit: download `ai-kit-<version>.zip` from the Releases page and extract it into `Documents`.
2. If the organization requires an authentication mode (Code Assist with a project, Vertex AI) or a model, write the matching key in `~/.ai-kit/overrides.json` before the next step; see [customization › Authentication and model](customization.md#authentication-and-model). Otherwise, nothing to do.
3. Run the installer: double-click `Installer.cmd` (Windows), or in Terminal `sh scripts/bootstrap.sh` from the extracted folder (Mac). Confirm your identity, choose the profile. Installation ends with a real call to the model: if it is not green, follow the remedy shown, do not call for help.
4. Open your usual repo, start your CLI (`gemini`, `agy` or `codex`), type `/guide where do I start?` (`$guide` in Codex).
5. First time in the repo: "Initialize the project context", then `setup-workflow` to declare the team's ticket tracker.

## During the pilot

- Work normally, going through the commands.
- When something goes wrong: `doctor --live`, then the "Troubleshooting" page, then a ticket.
- At the end of each longer session: `/retro`, and note what it proposes.
- In agy, answer permission requests: "always allow" saves the rule in your own agy settings, and the kit does not touch them.

## Support ticket template

```
Command or action:
What I expected:
What happened (copied output):
doctor --live output:
```

Each ticket is handled by the rule: a `doctor` check, a line in "Troubleshooting", or an eval case. Never a repeated verbal explanation.

## End of pilot

1. `python3 -m installer usage --json <workstation>.json` on each workstation; aggregated by the team.
2. The eval cases run on each CLI from a pilot workstation.
3. Ticket review: what was turned into a check, a page or a case.
4. Decision: opening to the whole team confirmed or not, scope of analyst commands confirmed or adjusted, first [usage review](usage-review.md) if the report has enough material.

## What the pilot must answer

- Does an analyst understand `/guide` and `/intent` without reading the docs?
- Is `doctor --live` enough to fix authentication failures without intervention?
- Do command skills trigger without being typed, and is that a problem?
- Do the enabled guardrails get in the way of normal work?
- Are agy permission requests understood and accepted without help?
