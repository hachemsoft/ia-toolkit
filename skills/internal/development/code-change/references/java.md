# Java

Standard: the repo's own style first; otherwise the conventions of the team's chosen style guide (Google Java Style or Sun/Oracle conventions).

Tools: build with the repo's wrapper (`./mvnw verify`, `./gradlew check`). Run the checks the build already declares (Checkstyle, SpotBugs, PMD, Error Prone, Spotless); do not add one.

Classic traps:
- Do not add a library or a style the repo does not use (Lombok, a reactive stack, records).
- A database migration already applied (Flyway, Liquibase) is never edited: add a new one.
- `equals` without `hashCode`, mutable objects used as map keys, `Optional` used for fields or parameters.
- Catching `Exception` and swallowing it; resources not closed (use try-with-resources).
- Serialized names (Jackson annotations, DTO fields) are a public contract, even when the Java name looks free to rename.
- Follow the JUnit version the repo uses (4 or 5); do not mix them in one module.
