# billing

Extends ../AGENTS.md. Overrides: test command `vendor/bin/phpunit` → `make test-billing` (it starts the payment provider stub first).

## Things the agent gets wrong
- Never call the real payment provider in a test (since 2026-10: a test charged a sandbox card).
