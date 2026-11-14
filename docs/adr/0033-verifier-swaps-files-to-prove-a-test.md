---
status: accepted
since: 4.12.0
---
# The verifier may swap files for a moment to prove a test

An acceptance test the person approved can pass even without the code it is meant to cover; nothing showed it. The
verifier now proves it: `prove_test.py`, a kit script installed next to `weakened_tests.py`, puts each code file of the
change back to its base version (a new file is set aside, a deleted one put back), keeps the tests at their new version,
runs the repo's focused test command and restores everything. The test must fail without the code. `/build` runs it on the
approved acceptance tests at the standard and full levels; a test that still passes stops `/build` and the person decides.
The same script reruns a red check on the base version, to tell a failure the change brought from one already there, and
lists the existing tests the change modifies.

So the verifier's rule "modify nothing" becomes "modify nothing, except the temporary swap made by this script". Before
any write, the script copies each file it touches, byte for byte, into `<repo>/.ai-kit-proof/` (a folder that ignores
itself in git) with a manifest of SHA-256 digests; it restores on every exit (normal end, error, interruption, termination
signal), checks every digest, and deletes the backup only once all match. A backup found at start means an earlier run was
cut short: the script refuses anything but `recover`.

**Why**: the work is not committed during `/build`, so the proof has to run on the person's working tree as it is. It must
not touch `.git` (Codex refuses writes there, so no `stash`, `worktree` or `checkout`), and copying the repo elsewhere is
slow and breaks tests that rely on ignored folders (`.venv`, `node_modules`). A backup in the working tree survives a
reboot, which a temporary folder does not.

**Consequences**: the verifier's version moves; one more kit script in `~/.ai-kit/bin/`; a hard stop (`kill -9`, power
loss) during a proof leaves the code swapped until `recover` runs; tools that watch files (an IDE, hot reload) see the
swap; a warehouse test (dbt) runs only on the development target the repo declares, with the cost announced and one
agreement for the base run and the rebuild. A test that fails without the code for another reason (a configuration file
of the change set aside) is a false proof: the literal output is shown and `--keep` leaves such a file in place.

**Considered**: a copy of the repo in a temporary folder (slow, breaks ignored folders, needs links that Windows restricts
without admin rights); `git stash` or a worktree (writes to `.git`); requiring a commit before the proof (it must come
before the final approval); judging only assertion failures (parsing each tool's output; a non-zero exit with the output
shown is enough for the person to judge).
