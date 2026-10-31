---
name: java-change
description: "Develop or review a Java feature in an existing repo (Maven or Gradle, Spring or other). Triggers: add an endpoint, modify a Java service, fix a Spring bug, migrate a dependency, review this Java code. Not for: the build pipeline or deployment files."
---

# java-change

Read the repo instructions, the `pom.xml` or `build.gradle`, the Java and framework versions, and two neighbouring classes that already do something similar. Follow their patterns: layering, dependency injection, exception handling, DTO mapping, logging. Do not introduce a new library, annotation or style (Lombok, reactive, records) if the repo does not already use it. Preserve public contracts: API signatures, JSON schemas, database migrations already applied, configuration properties. Develop with the tdd skill: a red JUnit test at the lowest level that proves the behaviour, minimal code, refactor; add an integration test only when the behaviour crosses a boundary (database, HTTP, message queue). Run the repo's verification command (`./mvnw verify`, `./gradlew check` or the one in `AGENTS.md`) and report its output. Secrets stay in external configuration, never in code or tests. Describe the delivery with the mr skill.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "The build is too long, I won't run it" | Run at least the touched module (`-pl`, or the subproject's Gradle task) and say what was not run. |
| "I'll add Lombok, it will be shorter" | A new dependency is a team decision; follow the repo's style. |
| "I'll mock everything, it's faster" | One mock per external boundary; test business logic with real objects. |
| "I'll rename this JSON field while I'm at it" | That is a contract change; decide and version it separately. |

## In the kit commands
- `/build`: a Java change follows this playbook.
