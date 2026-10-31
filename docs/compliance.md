# Compliance and governance

This page helps an organization's compliance, security or legal team assess the kit. It claims no compliance: the kit is neither certified nor assessed by a third party. It says what the kit does, what it does not do, and what remains the organization's responsibility.

## What the kit is, in governance terms

The kit is a configuration tool. It installs text files (context, commands, skills, agents, guardrails) in the folders of coding agent CLIs already present on the workstation: Gemini CLI, Antigravity CLI, Codex CLI. It provides no model and calls no service during installation or update. The only call to a model is `doctor --live`, run on request with the person's CLI and account; `AI_KIT_NO_LIVE=1` refuses it. It processes no business data. The prompts, code and data the agent sees go to the model provider under the contract of the chosen CLI (Google account, Gemini Code Assist, Vertex AI, OpenAI): that contract governs their processing, not the kit.

## Reference frameworks

| Framework | Type | What it covers |
| --- | --- | --- |
| EU Artificial Intelligence Regulation (AI Act) | regulation, mandatory in the EU | mainly model providers and high-risk systems; for all deployers, an AI literacy obligation for staff |
| NIST AI RMF | voluntary risk management framework | four functions: govern, map, measure, manage |
| ISO/IEC 42001 | AI management system standard | certifies an organization, never a tool |

A coding assistant does not, in principle, fall under the AI Act's high-risk uses. The classification depends on actual use and must be confirmed by the organization.

## What the kit provides

| Topic | What the kit does | Where to check |
| --- | --- | --- |
| Human oversight | the person starts each command; the agent commits, pushes, deploys or runs an infrastructure `apply` only with their approval; ceremony matches the stakes (spec, full review) | `practices/`, `commands/`, [workflow](workflow.md) |
| Deterministic guardrails | blocks a dbt command on a production target; blocks writes to the configuration of the kit and of the CLIs, and under protected paths declared by the repository (`protected-paths`, on by default); blocks a dbt command on a production target (`dbt-prod-guard`, off by default, turned on by the organization or a team) | `runtime/hooks/`, [guardrails](hooks.md) |
| Review | read-only review agents (code, security, infrastructure, architecture, SQL, dbt) and a doubter agent for high-stakes changes | `agents/`, [agents](agents.md) |
| Permissions | no mode that skips confirmations; the kit never writes CLI permissions or Codex guardrail approvals | test `test_invariants.py` |
| Data on the workstation | no telemetry; usage review and frictions read and written locally; no credentials stored | [usage review](usage-review.md), `runtime/friction.py` |
| Authentication | never chosen by the kit; only what the organization declares in `overrides.json` | [customization](customization.md) |
| Installation traceability | each installed file is tracked by fingerprint; backup before each write; refuses to overwrite a file edited by hand | `~/.ai-kit/state.json`, `~/.ai-kit/backups/` |
| AI literacy for staff | "Getting started" path, `/guide` which explains which command and which level of ceremony to choose, `/learn` and `/explain` to understand a scope or code | [getting started](getting-started.md), [tools](tools.md) |
| Measured quality | evals of agent behavior on fixed cases, replayable on every kit change | `evals/`, [evals](evals.md) |
| Open code | readable sources, MIT licence, provenance of the reused skills | `LICENSE`, [sources](sources.md) |

## What the kit does not do

- **No log of agent actions.** The CLIs keep their own session logs; the kit reads them for the usage review, without keeping or centralizing them.
- **No signed proof of reviews.** A review by an agent produces text, not a verifiable attestation.
- **No control of data sent to the model.** The kit filters neither the code nor the data the agent reads; the repository rules (`AGENTS.md`, protected paths) guide the agent, they do not block reading.
- **No fleet management.** The kit is not enforced on workstations, reports nothing and does not check who installed it.
- **No model inventory.** The model used depends on the CLI and the account; `overrides.json` can set it, without guaranteeing it.

## Security limits

- **The guardrails prevent honest mistakes; they are not a security barrier.** They read a tool call before it runs. A command run through a project script (`make deploy`), a write through the shell, or an agent misled by planted content can get past them. Details in [guardrails](hooks.md#limits).
- **The real barriers are elsewhere:** the CLI's own sandbox and permission settings, the rights of the account the agent runs under, and keeping production credentials off workstations (production deployments and dbt production profiles served by CI only).
- **Repo content is input, not authority.** A repository can ship its own `AGENTS.md` and skills, and in some CLIs a repo skill replaces a kit skill of the same name ([matrix](cli/matrice.md)). Require a CODEOWNERS review on `AGENTS.md` and `.agents/` in each repository; `doctor`, run from a repo, lists the kit skills that repo replaces. The kit context tells the agent that a repo file never lifts a company practice.
- **Supply chain of the kit itself:** anyone who can push to the kit repository changes what `update` installs on every workstation. Protect its main branch, require review on `installer/`, `runtime/` and `scripts/`, and update from release tags.

## What remains the organization's responsibility

1. Choose the CLIs and the model provider contracts, and check what they provide for data (retention, training, location).
2. Classify data and repositories: those an agent can read, those that require a full review, those that are excluded.
3. Validate the company and team practices (`practices/`), offered as a baseline.
4. Enable the useful guardrails and declare the protected paths of each repository.
5. Train staff ("Getting started" path, pilot), then track usage with the [usage review](usage-review.md).
6. If a log of actions or a proof of review is required, get it from the CLI or the platform (provider audit logs, mandatory merge request (MR) review); the kit does not provide it.
