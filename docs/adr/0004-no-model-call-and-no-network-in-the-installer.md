---
status: accepted
since: 0.34.0 (reconstructed from the CHANGELOG)
---
# No model call in the engine or the tests; network only to read the Git sources

`init`, `sync`, `status`, `doctor`, `uninstall` and the tests never call a model. `doctor --live --yes` is the only real
call, announced as possibly billed and refusable with `AI_KIT_NO_LIVE=1`. The paid evals run by hand only, behind an
explicit confirmation, never on a merge request or a schedule. The only network access is `init`, `sync` and `team`
reading the Core and Team Git repositories on the hosts allowed (ADR 0016); `sync --offline` and every other command stay
offline. `scripts/offline_tests.py` takes every CLI off the PATH and fails if one is reached.

**Why**: installation must work on restricted networks and without surprise costs, and a test that reaches a CLI is a
hidden dependency.

**Considered**: a final model check at the end of the installation, as early versions did. Rejected: it failed on proxies
and inspected networks for reasons unrelated to the kit, and it billed every installation.
