# PHP

Standard: PSR-12 (coding style) and the PSR interfaces the framework uses (PSR-4 autoloading, PSR-3 logging, PSR-7/15 HTTP).

Tools: run the ones the repo declares in `composer.json` or CI (PHP-CS-Fixer or PHP_CodeSniffer for style, PHPStan or Psalm for types, PHPUnit or Pest for tests); do not add one.

Classic traps:
- Keep `declare(strict_types=1);` where the neighbouring files have it; type properties, parameters and returns as they do.
- Loose comparison (`==`, `in_array` without `true`) between strings and numbers.
- Dependencies through `composer require` only: it changes `composer.lock`, and a new package is a team decision. Never edit `vendor/`.
- Schema changes go through migrations; never apply `doctrine:schema:update` to a shared or production database.
- A new test suite or test folder must be declared in `phpunit.xml(.dist)`, or its tests silently do not run.
- SQL: bind parameters, never concatenate user input.
