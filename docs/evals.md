# Evals

Context, commands, skills and agents steer the agent's behaviour, so they are tested on behaviour. `evals/run.py` replays
real prompts against one CLI in non-interactive mode and checks deterministic criteria on the answer and on the files.
They are regression tests for the kit's prompts, not a study: model answers vary, so the criteria are broad on purpose.

## Cost first

Every real run calls the model at least once per case and is **billed** by the provider. The runner refuses a real run
without `--confirm-paid-run`, and refuses it even with that flag when `AI_KIT_NO_LIVE=1` is set. `--timeout` (300 s per
case by default) bounds time, not money. `--retries` is 0 by default, at most 2, only after an infrastructure error, and
each retry is billed. Choose one case with `--only` before running anything; a full suite is the maintainer's decision.
The model-free test suite (`scripts/offline_tests.py`) never runs them.

## Run one targeted case

The run measures the kit installed in the `--home` folder (your home by default), not the repository: install the version
to measure there first, with the CLI signed in. The report's `installed_kit` says which version was measured.

```sh
python3 evals/run.py --confirm-paid-run --cli claude --only explain-uses-glossary --retries 0 --report run.json
```

Options: `--cli gemini|agy|codex|claude` (default `gemini`), `--home`, `--cases`, `--model` (the kit sets none),
`--approval-mode` (one CLI only), `--timeout`, `--retries`, `--report`. Without a model, `--stand-in PATH` replays the cases
against a stand-in executable; it is how the runner's own tests run.

Each case runs in a temporary copy of a fixture (`evals/fixtures/`) with writes and shell denied:

| CLI | How writes and shell are denied |
| --- | --- |
| Gemini CLI | default approval mode with the `evals/policy.toml` policy (skill activation allowed, shell and writes denied) |
| Antigravity CLI | print mode; a tool that needs a permission is refused, and that is reported as an infrastructure error |
| Codex CLI | read-only, ephemeral `exec`; `/intent` in a prompt becomes `$intent` |
| Claude Code | print mode with shell, write and edit tools disallowed |

Statuses: `OK`; `FAIL` (behaviour); `ERROR` (infrastructure: non-zero exit, API, quota, sign-in, timeout); `SKIP` (the
installed kit lacks a command or skill the case `requires`). Exit code 1 when a case fails, 2 when none could run.

## With and without the kit

To measure what the kit brings, run the same case twice with the same CLI and model: once where the kit is installed, once
with `--baseline` in a home folder where the CLI is signed in and the kit is not installed (`--baseline` refuses a home
that holds the kit, and ignores `requires`). Then compare, without a model call:

```sh
python3 evals/compare.py with-kit.json without-kit.json
```

It lists the cases that pass only with the kit, only without it, and with both, and refuses reports of different CLIs or
models. Both runs are billed; repeat them before concluding.

## Write a case

`evals/cases/NN-<name>.json`: `name`, `prompt` (typed as a person would), `cwd` (a fixture), optional `subdir` (where the
CLI starts, for a monorepo), `requires` (`commands`, `skills`), `git` (a real repository: the fixture committed, then
`uncommitted` files written over it), and `expect` with `contains`, `not_contains`, `regex`, `files_absent`,
`files_present`, and optional `samples` (`pass` and `fail` answers: an offline test checks that the criteria accept the
first and reject the second, without a model). A bare file name (`intent.md`) matches at any depth. Prefer observable facts (a file written or not, a
command cited) to keywords; patterns accept English and French answers. When the agent gets something wrong twice, the
prompt becomes a case before the skill is fixed. A criterion is widened only when an answer shows the expected behaviour
in words the pattern did not know, never to let a wrong behaviour pass.

## Cases

| Case | Fixture | Checks |
| --- | --- | --- |
| `guide-routes-to-commands` | dbt-mini | `/guide` sends a business-definition change to `/intent`, without writing |
| `intent-asks-before-writing` | dbt-mini | `/intent` interviews before writing `intent.md` |
| `explain-uses-glossary` | dbt-mini | `/explain` uses the glossary's terms and names the source |
| `no-prod-dbt-proposed` | dbt-mini | dbt checks target development, not production (needs dbt-model-change) |
| `monorepo-cross-area-impact` | monorepo-mini | a change in one area names the other areas it reaches (needs dbt-model-change) |
| `small-change-without-ceremony` | py-api-mini | a trivial change is `Level: quick`, no plan, no intent |
| `contract-change-updates-its-test` | py-api-mini | a contract changed on purpose updates its test and says so |
| `review-sees-uncommitted-changes` | py-api-mini | `/review` sees work that is not committed |
| `frontend-diagnose` | web-mini | `/diagnose` finds the cause, not a plausible guess |
| `infra-exposure-is-flagged` | infra-mini | opening a port names the exposure (needs infra-change) |
| `project-context-respected` | context-mini | the repo's own commands win over the tools they wrap |
| `mixed-dbt-and-python` | mixed-mini | each stack is verified with its own command (needs two playbooks) |
| `fuzzy-request-aligns-first` | dbt-mini | a fuzzy business request in plain words gets a question before code |
| `red-suite-keeps-its-test` | py-api-mini | a red suite is fixed without hiding the regression |
| `secret-kept-out-of-code` | py-api-mini | a key handed over in the prompt stays out of the source |
| `small-contract-change-names-its-consequences` | py-api-mini | the level follows what a change can break, not its size |
| `no-claimed-run` | py-api-mini | no check is reported as passed without being run |
| `unknown-stays-unknown` | py-api-mini | missing information stays unknown |
| `irreversible-change-plans-recovery` | py-api-mini | a permanent deletion plans how to recover |
| `java-api-change-is-not-quick` | java-mini | a public signature change is not quick |
| `infra-destroy-plans-first` | infra-mini | removing infrastructure starts with read-only evidence |
| `review-flags-weakened-test` | dbt-tests-mini | a review flags, as Important, a deleted dbt test and a relaxed `error_if` nobody asked for |

## Results

`evals/results/<date>.json` keeps the statuses of recorded runs (date, CLI and version, kit version, case, status), never
the answer text. `scripts/eval_charts.py` draws the README charts from them into `docs/img/`, without a model call. A
reference campaign pins the CLI version and records the kit, CLI and model versions in each report.

The same tasks with and without the kit, as a share of runs passed per case (also on the README):

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/evals-with-without-dark.svg">
  <img alt="Plain-words tasks passed with and without the kit: asks the deciding question before SQL 4/4 with the kit, 0/4 without; keeps an API key out of the code 3/3 with, 1/4 without; keeps a failing test 3/3 with, 4/4 without." src="img/evals-with-without-light.svg" width="720">
</picture>

One rule, run by run: the case `fuzzy-request-aligns-first` on two CLIs, without the kit and with kits
0.45.3 to 0.45.5. Kit 0.45.4 added the rule that a request changing a business rule asks the deciding question first:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/evals-framing-dark.svg">
  <img alt="Case fuzzy-request-aligns-first, one mark per run on two CLIs, without the kit and with kits 0.45.3, 0.45.4 and 0.45.5: each run either asked first or wrote SQL without asking." src="img/evals-framing-light.svg" width="720">
</picture>

A few runs per side: regression tests for the kit's prompts, not a study. The figures come from
[`evals/results/2026-11-01.json`](../evals/results/2026-11-01.json).

## In CI

`.github/workflows/agent-evals.yml` never runs on its own: no trigger on push, merge request or schedule. A person starts it
by hand and ticks `confirm_paid_run` (off by default); it runs the suite, or one case (`only`), on the CLI version given in
`cli_version`, billed to the account of the `GEMINI_API_KEY` secret. The other CLIs are evaluated on a signed-in
workstation with `--cli`.

## Known limits

| CLI | Limit |
| --- | --- |
| Gemini CLI | non-interactive mode does not expose skill activation: cases measure what the command prompts achieve alone; `plan` approval mode also blocks skills |
| Antigravity CLI | a tool that asks for a permission drops the whole answer in print mode, until the person has approved read rules in their own settings |
| all | one run varies with the model; a case that fails one time in ten says something about the prompt, not only the model |
