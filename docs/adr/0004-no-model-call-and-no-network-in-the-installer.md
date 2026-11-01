---
status: accepted
since: 0.34.0 (reconstructed from the CHANGELOG)
---
# No model call and no network in setup, update, doctor, uninstall and the tests

`setup` and `update` never call a model; their summary says "connection not verified". `doctor --live` is the only real call, announced as possibly billed and refusable with `AI_KIT_NO_LIVE=1`. The paid evals run by hand only, behind an explicit confirmation, never on a merge request or a schedule. Installation must work on restricted networks and without surprise costs, and a test that reaches a CLI is a hidden dependency: `scripts/offline_tests.py` takes every CLI off the PATH and fails if one is reached.

**Considered**: a final model check at the end of setup, as earlier versions did. Rejected: it failed on proxies and inspected networks for reasons unrelated to the kit, and it billed every installation.
