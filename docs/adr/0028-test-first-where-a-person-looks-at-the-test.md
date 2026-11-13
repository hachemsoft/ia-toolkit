---
status: accepted
since: 4.4.0
---
# Test-first where a person looks at the test

`/build` asked for a red test before every slice, at every level. The kit now asks for test-first where a person looks at
the test. Quick: no test written first; the existing checks that cover the change prove it. Standard and full: before any
code, the agent writes the acceptance tests of the change (one per acceptance criterion of `spec.md` that can be
automated, a named manual or read-only check for the others; three at most, else it proposes to split the change), shows
them failing on their assertion with why, says what each asserts, and waits for the person's approval. A go-ahead given
before the tests were shown does not cover them; only an explicit "do not stop for the tests" does, noted in the reply (the
person may depart from a practice in the conversation). Without a test runner, the acceptance is the check the matching
playbook names (an assertion query, a `terraform plan` or a diff, a reproduction script). Once approved, the
implementation is free: the tdd skill's red-green loop is optional below those tests, which stay as approved and are never
committed while they fail. A docs-only change or a pure refactor needs no new test.

**Why**: the sources agree on an acceptance expectation a person validates, independent of the agent that implements it:
a human review checkpoint on the red test, a red being proof only once someone checked why (Böckeler, F55, F59 of
`docs/sdlc/2026-11-13-spec-anchored-tests/research.md`), an acceptance check the implementing agent cannot rewrite (Jain,
F72-F75), executable specifications (Farley, F106-F109). They dispute the agent's own test-first loop at every step: a
small experiment found no clear difference for at least three times the tokens, judged by a model and with cached reads
overstating the cost (Böckeler, F56, F62), while practitioners keep it with agents (Beck F33-F34, Willison F96). Beck
commits only when all tests pass (F35), hence no red commit; an instruction in an Anthropic harness article forbids
removing or editing tests (F92), hence the tests stay as approved. The review's test check (ADR 0027) stays the safety net.

**Consequences**: one stop for the person per change at standard and full levels; the kit context, `/build`, `/test`, the
tdd skill (with its stated exception) and the dbt, Java, Python and JavaScript, and infrastructure playbooks say it. The
general rule "a go-ahead already given stands" does not extend to a test the person has not seen. `/diagnose` keeps its
own loop: the failing reproduction is its evidence and the person asked for the fix. A standard change made without
`/build` reads only the kit context, which does not repeat the docs and refactor exemption: accepted, `/build` says it.
The extra stop shows in frictions if it costs more than it saves.

**Considered**: keeping the red test before every slice (the contested part, paid at every step); dropping test-first
altogether (nothing then proves the test checks what the person wanted); one criterion at a time, each test shown and
approved before its code, as the research note proposes (one stop per criterion: the limit of three tests per change keeps
the single approval close to it); full level only, standard on request, as the research note proposes (standard is where
most changes land, and the approval costs one look); committing the failing tests before the code (a red commit, against
Beck F35) or marked skip or xfail to keep the suite green (against the kit's "never skip").
