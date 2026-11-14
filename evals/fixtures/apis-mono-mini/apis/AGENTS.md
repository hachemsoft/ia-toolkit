# apis

Extends ../AGENTS.md. Overrides: none.

## Commands
- Versions: PHP 8.3, Composer, PHPUnit 11

## Verifying your work
Run the "Changed" command for the app touched; "Full" when `composer.lock` changed. Paste the real output.

| Stack | Changed | Full |
| --- | --- | --- |
| PHP | `vendor/bin/phpunit <tests of the changed classes>` | `vendor/bin/phpunit` |
