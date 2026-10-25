# Evals

Context, skills, commands and agents drive the agent's behavior: they are tested like code. The `evals/` suite replays real prompts against each supported CLI (`--cli gemini`, `--cli agy` or `--cli codex`), in non-interactive mode, and checks deterministic criteria on the response and on the files.

## Run

```sh
python3 evals/run.py --dry-run            # lists the cases, no model call
python3 evals/run.py                      # against the kit installed in your home folder
python3 evals/run.py --home ./sandbox-user --only guide-routes-to-commands
```

Each case runs in a temporary copy of a fixture (`evals/fixtures/`), in default approval mode with the `evals/policy.toml` policy (writes and shell denied): the agent writes no file. Options: `--cli gemini|agy|codex`, `--model`, `--approval-mode`, `--timeout`. Exit code 1 if a case fails; `--report` writes the details as JSON.

## Write a case

A file `evals/cases/NN-name.json`: `name`, `prompt` (a kit command or a request as a user types it), `cwd` (fixture), `subdir` (optional: subfolder where the CLI starts, for a monorepo), `expect` with `contains`, `not_contains`, `regex`, `files_absent`. The criteria cover what a human would check: the right command is suggested, the glossary is used, no production command is suggested, no file is created without approval.

One case per incident or repeated error: when the agent gets it wrong, the prompt that caused the error becomes a case, before fixing the skill.

## In CI

`.github/workflows/agent-evals.yml` installs the kit in a temporary folder, then runs the suite on Gemini CLI on every merge request (MR) that touches `practices/`, `skills/`, `templates/`, `runtime/`, `commands/`, `installer/`, `agents/` or `evals/`, and every Monday. It expects a `GEMINI_API_KEY` secret; without it, the suite cannot run. agy and Codex are evaluated on a signed-in workstation, with `--cli agy` or `--cli codex`.

## Limits

Gemini CLI ([its page](cli/gemini.md)): in non-interactive mode, version 0.65 does not expose the `activate_skill` tool, so the cases measure what the command prompts achieve on their own, not the skills. `plan` mode also blocks skills; the runner uses the default approval mode with `evals/policy.toml` (writes and shell denied). If the default model loops on your access ("Model fallback activated"), force the same model as in `overrides.json` with `--model`.

Model responses vary; the criteria are deliberately broad and check facts (a command cited, a term used, a file absent). A case that fails one time in ten says something about the prompt or the skill, not only about the model.

## Known variance: `/test` (case `no-prod-dbt-proposed`)

The case asks `/test`, in the dbt fixture, to list the checks and their target based on `AGENTS.md`, which requires the development target. On Gemini CLI ([its page](cli/gemini.md)) in non-interactive mode, one run in two failed the same way: the model writes "I'm reading AGENTS.md" without calling the read tool, so it never sees the rule, and suggests `dbt test` without a target. Nothing is broken in the kit or the repository; the model skips a step it announces. Two countermeasures, both in place: the `/test` prompt now requires reading `AGENTS.md` with the read tool before any suggestion and forbids assuming its content; and the `dbt-prod-guard` guardrail, when enabled, blocks any dbt command on a production target anyway. If the case still fails now and then, it measures model variance, to note, not a ticket.
