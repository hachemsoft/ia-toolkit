# Evolving the kit

1. Edit the general practices in practices/. The numeric prefix of the file (`10-company.md`) sets its position in the agent context. Keep business facts in the projects.
2. Add a skill with a unique name, a short SKILL.md and its entry in skills/catalog.json: under `skills/contrib/` with a named owner when it is a team proposal, under `skills/internal/` when the kit maintainers take it on. The full procedure (catalog, profiles, command, eval case) is in [add or replace a skill](extending.md).
3. Select the skills in the profiles. Do not install the whole catalog by default.
4. For skills taken from an upstream repository, copy the folders as is into skills/internal/common/, remove files specific to other tools, keep the licence text (skills/LICENSE-UPSTREAM-MIT) and run the tests again; no automatic download.
5. Add an MCP server only after validating the server, the transport, the authentication and its Windows/Mac prerequisites. Do not commit secrets.
6. Run the tests, do a trial with --home in a temporary folder, then replay the evals (`python3 evals/run.py`) when a skill, a command or a practice changes. When the agent gets it wrong, add the failing prompt as an eval case before fixing the skill.
7. Then validate on a real Mac and a standard Windows workstation without admin rights, then in each supported CLI, signed in.
8. Release: the version is in `VERSION` and in `pyproject.toml` (a test checks that they match); commit, tag `v<version>`, push. CI builds the release ZIP (`scripts/package.sh`, from the committed files, without the `export-ignore` paths of `.gitattributes`), tests it on the three systems, then attaches it to the GitHub release with the CHANGELOG section. People download it, extract it and run the installer again; a git clone runs `update`, which pulls first. Before a release that changes the launchers or the installer, go through the manual checks of [validation](validation.md). For developers who prefer `pipx`: `pipx install git+<repository url>` provides the `ai-kit` command (same as the launcher); it is not the documented path for the team. `python3 -m build` builds the package, which bundles the content under `ai_kit/kit/`. A new content folder read by the installer goes into `[tool.hatch.build.targets.wheel.force-include]`; otherwise the package test fails. `update` applies the extracted or installed version.

Commands are written once in `commands/<name>.md` ([pivot format](format.md)). The content depends on no CLI: templates in `templates/` (including `kit-context.md`, which becomes `00_KIT.md`), agents and their default settings in `agents/`, profiles and the organization directory (allowed domains, profile by email) in `profiles/`, scripts installed and run on the workstation (guardrails, frictions) in `runtime/`. Only data specific to one CLI lives with its code (`installer/adapters/gemini_defaults.json`). The code follows the same split: `installer/core.py` for the shared building blocks, `installer/cli.py` for orchestration (a neutral plan of what to install), and one module per CLI in `installer/adapters/` (`gemini.py`, `agy.py`, `codex.py`), all with the same interface, described in `installer/interface.py`: the neutral plan (`Plan`), the `doctor` context and the adapter contract (`Adapter`, plus two optional capabilities, `ContextHost` and `LiveCheck`). `cli.py` names no CLI: it talks only to this interface, and a test checks that each adapter follows it. The snapshot test (`tests/snapshot.py`) guarantees that a code change alters no installed file unless the reference is rewritten on purpose; the [CLI matrix](cli/matrice.md) says what each one produces; the Antigravity output (plugin, command skills) is part of it. One more CLI is one more adapter module: see [add a CLI](#add-a-cli).

Acceptance criteria: installation without mandatory editing, `30_USER.md` preserved, profile change, non-destructive conflicts, skill discovery and connection of configured MCP servers.

When a version fixes reported frictions, the `CHANGELOG` says so in one line, with the number of reports.

Support rule: a ticket is never resolved verbally twice. Each ticket becomes a `doctor` check (with its fix), a line in `docs/troubleshooting.md`, or an eval case in `evals/cases/`. The kit is fixed based on real tickets, not assumptions.

Before a merge request (MR): `python3 -m unittest discover -s tests` and `ruff check .` (installed by `pip install -e '.[dev]'`, or without installing with `uvx ruff check .`). CI runs both.

## Add a team

1. `practices/20-<team>.md`: the team's practices, short and checkable.
2. Give the team its setup command (`setup --profile <profile> --team <team>`), or let `setup` ask.
3. Nothing to change in the profiles: a team adds its layer to any profile.

## Add a profile

1. `profiles/<id>.json`: `practices`, `skills` (start from `general.json`, then add the domain playbook), `agents`, `mcp.recommended`, and `commands` only to restrict the list (otherwise all those whose skills are installed).
2. The domain playbook, if there is one: [add a skill](extending.md#for-the-organization-in-the-kit), category `domain`; wire it into `commands/build.md` or `commands/diagnose.md` "if installed".
3. In the same file, `label` (shown in the `setup` menu) and `order` (its position): the menu is built from the `profiles/` folder, no code to change.
4. The tests: nothing to declare, a new profile is picked up by the tests and the snapshot automatically; run `python3 tests/snapshot.py --update`, and refresh the profile table: `python3 scripts/profile_table.py --write`.
5. The profile in the README (profile table).

## Add a CLI

See [add a CLI](cli/matrice.md#add-a-cli): a module in `installer/adapters/`, its entry in `ADAPTERS`, its column in the matrix, its page in `docs/cli/`.
