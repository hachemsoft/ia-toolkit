---
status: accepted
since: 4.16.0
---
# One Core context layer, rewritten by a fork; a Team layer that adds to it

The Core repository holds one rule layer, `context/10-core.md`, installed as `10_CORE.md`: the kit's defaults in this
repository, the organization's rules in its fork, which rewrites the file whole. An active Team with a `context/` adds
`20_<TEAM>.md` after it; it never replaces the Core layer. Every agent's prompt carries both. A Team named like a Core
layer is refused. Skills and agents keep their own rule: a Team replaces a same-named one unless the Core protects it.

**Why**: the public Core shipped `10_COMPANY.md` and `20_TEAM.md` headed "proposed baseline, not an approved internal
policy", a line that weakened in every session the rules `00_KIT` says to apply; and a Team's context replaced `20_TEAM.md`,
so a Team of two lines silently dropped the default practices (checks reported as observed, a component's guarantees
stated, never production without an instruction). A rule is a restriction: like the other restrictions (ADR 0015), each
layer's applies and none lifts another's. A skill is a way of working, a value a Team may replace.

**Considered**: keeping `10_COMPANY.md` and dropping `20_TEAM.md` only: less renaming, but the file holds the kit's default
team practices too, and "company" misnames it in a public repository. Folding the practices into `00_KIT.md`: refused, the
kit context is capped under 3 800 characters and is already at it. A Team that may still replace the Core layer: refused, a
Team specializes the rules, it never lifts one.
