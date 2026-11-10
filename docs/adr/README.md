# Architecture decisions

One file per decision: the context, the decision as implemented, its consequences, the options rejected. The `status` line
says when a decision was superseded. A change that reverses a decision comes with a new ADR.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-one-pivot-file-per-command.md) | commands are written once, in a CLI-neutral pivot file | accepted |
| [0002](0002-orchestrator-knows-no-cli.md) | the orchestrator names no CLI; one adapter module per CLI | accepted |
| [0003](0003-no-authentication-no-model-in-the-kit.md) | the kit never handles authentication or model choice | accepted |
| [0004](0004-no-model-call-and-no-network-in-the-installer.md) | no model call in the engine or the tests; network only to read Git sources | accepted |
| [0005](0005-one-neutral-context-folder-rule-layers-restored.md) | one neutral context folder; rule layers restored, the personal layer never rewritten | accepted |
| [0006](0006-the-agent-cannot-change-its-own-configuration.md) | a guardrail keeps the agent from changing its own configuration by mistake | accepted |
| [0007](0007-frictions-are-local-lines-written-by-one-script.md) | a friction is one local line written by one script | accepted |
| [0008](0008-organization-file-and-three-source-merge.md) | an organization file merged with personal settings | superseded by 0015 |
| [0009](0009-generic-public-repository-in-english.md) | a generic, public repository, in English | accepted |
| [0010](0010-private-python-environment-two-distributions.md) | a private Python environment, no administrator rights | accepted |
| [0011](0011-broad-core-slimmed-by-measured-usage.md) | ship a broad core, slim it by measured usage | accepted |
| [0012](0012-a-session-hook-may-read-the-kit-remote-never-write-never-send.md) | a session hook may read the kit's remote | superseded by 0025 |
| [0013](0013-evolve-in-place-split-engine-and-content-roots.md) | one engine, a separate content root | accepted |
| [0014](0014-private-venv-with-a-recorded-hook-interpreter.md) | private venv on Python 3.11+; hooks use an absolute interpreter path | accepted |
| [0015](0015-managed-wins-values-resolve-restrictions-all-apply.md) | `managed.toml` wins; values resolve by precedence, restrictions all apply | accepted |
| [0016](0016-git-sources-anchored-origin-tar-free-extraction.md) | Git sources: stable tags, anchored origin, tar-free extraction, optional signatures | accepted |
| [0017](0017-rollback-to-one-of-three-validated-configurations.md) | rollback re-activates the previous configuration, in one transaction | accepted |
| [0018](0018-no-profiles-migrated-choices-kept-as-personal-lines.md) | no profiles: Core default, Team choices, personal choices | accepted |
| [0019](0019-protected-only-guards-the-files-ai-kit-manages.md) | `protected` only guards the files AI Kit manages | accepted |
| [0020](0020-commands-chain-only-model-invocable-skills.md) | commands chain only skills the model can invoke | accepted |
| [0021](0021-workflow-extensions-reuse-the-playbook-section.md) | workflow extensions reuse the playbook section "In the kit commands" | accepted |
| [0022](0022-mcp-exact-identities-approved-upstream-or-locally.md) | MCP: exact identities, approved by IT or on the workstation | accepted |
| [0023](0023-friction-local-housekeeping-and-terminal-approval.md) | frictions: local log, housekeeping at session start, terminal approval | accepted |
| [0024](0024-user-md-and-adaptive-interview.md) | `USER.md` and an adaptive interview | accepted |
| [0025](0025-cli-surface-with-one-offline-reapply.md) | the CLI surface, with one offline re-apply | accepted |
| [0026](0026-analysis-and-research-entry-points.md) | Analysis and Research workflows, entered by `/explain` and `/research` | accepted |
