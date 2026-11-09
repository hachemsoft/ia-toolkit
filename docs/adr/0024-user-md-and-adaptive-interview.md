---
status: accepted, amended: USER.md lives in `~/.ai-kit/context/`, stays writable by the agent for `/me`, and the interview reads no commit history
since: 4.0.0
---
# USER.md and an adaptive interview with bounded local hints

The person's context is `~/.ai-kit/context/USER.md`, next to the rule layers, at most twenty lines of instructions on how
to answer this person. The interview is the `/me` command in the CLI: the agent first reads a few local facts, never asked
(the current file, `git config user.name`, OS and shell, the CLIs on the PATH, the repo's languages, the team in the kit
context), then asks short questions with options and a recommendation, shows the difference, and writes the file only after
the person's yes. `ai-kit user edit` opens the file in the person's own editor; the engine never writes it. `init` works
without an interview.

**Why**: personal preferences change how the agent answers, not what is installed, so they belong in a file the agent reads.
A dedicated engine command for the hints would duplicate `/me`.

**Consequences**: `protected-paths` keeps `USER.md` writable (the agent writes it for `/me`, with the person's agreement)
while protecting the rule layers beside it. A `USER.md` that seems to hold a secret, or is not plain UTF-8, is never copied
into a CLI.
