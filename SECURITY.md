# Security

## Reporting a vulnerability

Use GitHub's private reporting: **Security > Report a vulnerability** on this repository. Please do not open a public issue.

An organization that runs its own copy of the kit should report to its own security contact first.

## What to expect

One maintainer handles this on a best-effort basis. There is no guaranteed response time and no warranty (see [LICENSE](LICENSE)).

Only the latest release is supported. A fix ships in a new release, noted in the [CHANGELOG](CHANGELOG.md).

## Scope

In scope: the installer, the launchers, the release ZIP (including the Core bundle it ships), the hooks in `runtime/`, and what the kit writes on a workstation. Since AI Kit 2 also: how the engine reads `managed.toml` (path, ownership, closed schema), fetches and extracts Core and Team sources from Git (canonical URLs, neutralized Git, tag checks, extraction), and validates MCP servers (closed keys, identities, IT allowlists).

The guardrails are anti-error defaults, not a security barrier. A way around them is a security report only if it breaks what [their limits](docs/hooks.md#limits) say holds. See also [compliance](docs/compliance.md).

Out of scope: the agent CLIs and the models themselves (report those to their vendors), and the content of a Core or Team repository an organization publishes: its owners review and protect it (tag protection is an operating requirement, see [Core and Team sources](docs/repositories.md)).
