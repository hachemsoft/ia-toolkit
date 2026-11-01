---
status: accepted
since: 0.14.0 (reconstructed from the CHANGELOG)
---
# Commands are written once, in a CLI-neutral pivot file

Each supported CLI has its own command format (a TOML file, a command skill, a skill with an "on command only" flag, a slash command). We write every kit command once, as `commands/<name>.md` (front matter: name, description, category, stage, skills, artifact, order; body: the prompt), and each adapter derives its own form from it. One source of truth keeps the four CLIs from drifting apart, a test can check that commands stay free of any CLI or domain vocabulary, and a new CLI is one adapter, not one more copy of every command.

**Considered**: one command folder per CLI (what existed before, under the Gemini adapter). Rejected: every fix had to be made as many times as there were CLIs, and the copies diverged.
