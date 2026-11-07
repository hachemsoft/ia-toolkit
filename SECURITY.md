# Security

## Reporting a vulnerability

Use GitHub's private reporting: **Security > Report a vulnerability** on this repository. Please do not open a public issue.

An organization that runs its own copy of the kit should report to its own security contact first.

## What to expect

One maintainer handles this on a best-effort basis. There is no guaranteed response time and no warranty (see [LICENSE](LICENSE)).

Only the latest release is supported. A fix ships in a new release, noted in the [CHANGELOG](CHANGELOG.md).

## Scope

In scope: the installer, the launchers, the release ZIP, the hooks in `runtime/`, and what the kit writes on a workstation.

The guardrails are anti-error defaults, not a security barrier. A way around them is a security report only if it breaks what [their limits](docs/hooks.md#limits) say holds. See also [compliance](docs/compliance.md).

Out of scope: the agent CLIs and the models themselves. Report those to their vendors.
