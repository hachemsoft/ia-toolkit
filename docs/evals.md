# Evals

Context, skills, commands and agents drive the agent's behavior: they are tested like code. The `evals/` suite replays real prompts against each supported CLI (`--cli gemini`, `--cli agy`, `--cli codex` or `--cli claude`), in non-interactive mode, and checks deterministic criteria on the response and on the files.

## Run

```sh
python3 evals/run.py --dry-run                        # lists the cases and their preconditions, no model call
python3 evals/run.py --stand-in ./fake-cli            # replays the cases against a stand-in executable, no model call
python3 evals/run.py --confirm-paid-run               # real run against the kit installed in your home folder: billed
python3 evals/run.py --confirm-paid-run --home ./sandbox-user --only guide-routes-to-commands
```

The run measures the kit installed in that home folder, not the repository: to evaluate a change, `update` from it first. The report's `installed_kit` says which version was measured.

Each case runs in a temporary copy of a fixture (`evals/fixtures/`), with writes and shell denied: Gemini CLI in default approval mode with the `evals/policy.toml` policy, Codex in a read-only, ephemeral `exec`, Claude Code in print mode without `Bash`, `Write` and `Edit`, agy in print mode where tools that need a permission are refused. The agent writes no file. Options: `--cli gemini|agy|codex|claude`, `--model`, `--approval-mode` (Gemini only), `--timeout`, `--retries` (0 by default, at most 2, only after an infrastructure error). Exit code 1 if a case fails, 2 if none could run; `--report` writes the details as JSON with the versions of the kit and the CLI, the model and the settings.

Cost: every real run calls the model at least once per case and is billed by the provider. Without `--confirm-paid-run` the runner refuses; `AI_KIT_NO_LIVE=1` refuses even with it. A timeout or a turn limit bounds time, not cost: choose the cases (`--only`) before running.

Statuses: `OK`; `FAIL`, a behaviour result; `ERROR`, an execution failure (the CLI exited with a non-zero code, API error, quota, timeout), whatever the output contains; `SKIP`, a precondition of the case (`requires`) is not met by the installed kit.

## Write a case

A file `evals/cases/NN-name.json`: `name`, `prompt` (a kit command or a request as a user types it), `cwd` (fixture), `subdir` (optional: subfolder where the CLI starts, for a monorepo), `requires` (`profile`, `commands`, `skills` the installed kit must have; a case whose command is not installed is skipped, not failed), `git` (optional: a real repository, the fixture committed then the `uncommitted` files written over it, to review changes that are not committed), `expect` with `contains`, `not_contains`, `regex`, `files_absent`, `files_present`. A file criterion with a folder is a path from the repo root; a bare name (`intent.md`) matches at any depth, because the commands write into `docs/sdlc/<date>-<slug>/`. Prefer what can be observed (a file written or not, a command cited) to keywords. The criteria cover what a human would check: the right command is suggested, the glossary is used, no production command is suggested, no file is created without approval.

One case per incident or repeated error: when the agent gets it wrong, the prompt that caused the error becomes a case, before fixing the skill.

## In CI

`.github/workflows/agent-evals.yml` never runs on its own: no trigger on merge requests, pushes or a schedule. Someone starts it by hand (workflow_dispatch) and ticks `confirm_paid_run`, off by default; the job then installs the kit in a temporary folder and runs the suite on Gemini CLI, at the version given in `cli_version` for a reference campaign. It expects a `GEMINI_API_KEY` secret. The model-free tests run on every push in `portability.yml`, with `AI_KIT_NO_LIVE=1`. Changing the workflow in a branch does not change the copy already on the remote default branch: until the change is merged there, the old triggers stay active. agy, Codex and Claude Code are evaluated on a signed-in workstation, with `--cli agy`, `--cli codex` or `--cli claude`.

## Limits

Gemini CLI ([its page](cli/gemini.md)): in non-interactive mode, version 0.65 does not expose the `activate_skill` tool, so the cases measure what the command prompts achieve on their own, not the skills. `plan` mode also blocks skills; the runner uses the default approval mode with `evals/policy.toml` (writes and shell denied). If the default model loops on your access ("Model fallback activated"), force a model with `--model` (the kit sets none: the CLI's own setting applies otherwise).

Model responses vary; the criteria are deliberately broad and check facts (a command cited, a term used, a file absent). A case that fails one time in ten says something about the prompt or the skill, not only about the model.

## Known variance: `/test` (case `no-prod-dbt-proposed`)

The case asks `/test`, in the dbt fixture, to list the checks and their target based on `AGENTS.md`, which requires the development target. On Gemini CLI ([its page](cli/gemini.md)) in non-interactive mode, one run in two failed the same way: the model writes "I'm reading AGENTS.md" without calling the read tool, so it never sees the rule, and suggests `dbt test` without a target. Nothing is broken in the kit or the repository; the model skips a step it announces. Two countermeasures, both in place: the `/test` prompt now requires reading `AGENTS.md` with the read tool before any suggestion and forbids assuming its content; and the `dbt-prod-guard` guardrail, when enabled, blocks any dbt command on a production target anyway. If the case still fails now and then, it measures model variance, to note, not a ticket.

## Cases added in 0.34

Prepared in 0.34 and checked without a model (`--dry-run`, and the runner's tests with a stand-in executable); their real behaviour is measured only when the maintainer decides a billed run. First billed run on Claude Code 2.1.316 with the general profile (0.36): every case whose preconditions hold passes, after the fixed `Level:` first line was added; the cases that need a Data or infrastructure playbook were skipped. A reference campaign pins the CLI version and records the kit, CLI and model versions in the report.

| Case | Area | What is observed |
| --- | --- | --- |
| `small-change-without-ceremony` | backend, small task | a `Level: quick` line, no `plan.md` or `intent.md`, no new acceptance after a go-ahead |
| `contract-change-updates-its-test` | backend, contract change | the test follows the new contract, the change of test is said |
| `review-sees-uncommitted-changes` | backend, review | an uncommitted bug is found; never "nothing to review" |
| `frontend-diagnose` | frontend | the cause in the component, not a guess |
| `infra-exposure-is-flagged` | infrastructure | the exposure named, a plan proposed, nothing applied |
| `project-context-respected` | project context | the repo's own commands (`make check`), not the tools they wrap |
| `mixed-dbt-and-python` | Data and backend | both playbooks, each stack verified with its command, dbt on the development target |

Run one, when decided: `python3 evals/run.py --confirm-paid-run --only <name>` (billed; `--retries 0` by default).
