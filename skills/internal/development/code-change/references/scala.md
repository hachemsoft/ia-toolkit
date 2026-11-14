# Scala

Standard: the Scala Style Guide (docs.scala-lang.org) and the repo's `.scalafmt.conf`.

Tools: the repo's build tool (`sbt test`, Mill or Gradle as declared), `scalafmt`, and `scalafix` when configured; a cross-built project (2.13 and 3) must compile on every listed version.

Classic traps:
- Scala 2 vs 3 syntax (`implicit` vs `given`/`using`, braces vs indentation): follow the files around, do not convert while changing them.
- An effect library (Cats Effect, ZIO) or an actor framework the repo does not already use.
- Blocking on a `Future` (`Await.result`) outside tests; a different `ExecutionContext` than the repo's.
- A new implicit or given instance in scope silently changes behaviour elsewhere (codecs, ordering).
- `null` or exceptions where the repo uses `Option`, `Either` or its effect type.
- Case class field names are often a serialized contract (derived JSON codecs).
