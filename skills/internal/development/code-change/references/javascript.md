# JavaScript and TypeScript

Standard: the repo's ESLint and Prettier configuration; for TypeScript, its `tsconfig.json` (keep `strict` as it is).

Tools: the package manager of the repo's lock file only (`package-lock.json` npm, `pnpm-lock.yaml` pnpm, `yarn.lock` yarn), never another; the repo's scripts (`lint`, `typecheck`, `test`) and test runner (Jest, Vitest, Mocha); the Node version it declares (`.nvmrc`, `engines`).

Classic traps:
- `==` instead of `===`; truthiness checks that treat `0` or `""` as missing.
- A promise not awaited, or a rejection not handled.
- ES modules and CommonJS mixed (`import` vs `require`, `"type"` in `package.json`).
- TypeScript loosened to pass: `any`, `as unknown as`, a non-null `!`, `// @ts-ignore`, or `strict` turned down.
- A test left focused or skipped (`it.only`, `it.skip`, `xit`).
- A dependency added to `dependencies` when it is only needed for development or tests.
