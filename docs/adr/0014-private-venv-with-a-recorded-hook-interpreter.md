---
status: accepted, amended: the hook interpreter is recorded in each hook command, not in a `runtime.python` field of state.json
since: 4.0.0
---
# The engine runs from its private venv on Python 3.11 or later; hooks use an absolute interpreter path

However the kit arrives (release ZIP with `wheels/`, `Installer.cmd`, `scripts/bootstrap.sh`, or a git clone), the launcher
(`scripts/launcher.py`) creates or reuses `~/.ai-kit/runtime/venv`, installs the engine there and runs it; `ai-kit init`
can put the `ai-kit` command on the person's own PATH. Each guardrail and hook is declared as
`<absolute interpreter> -I <script>` with the interpreter that ran the activation (`installer/core.py`); `doctor` checks
that this interpreter exists and that each guardrail answers a probe, and `ai-kit sync --offline` rewrites the commands
when it moved. The engine needs only the standard library; `rich` and `questionary` improve the terminal output. Python
3.11 is the minimum: the bootstrap and the launcher refuse an older one and say what to ask IT. CI tests 3.11 to 3.14 on
Linux, macOS and Windows.

**Why**: guardrail scripts need only the standard library; what keeps them working is a stable, checked path. The venv
gives a path the kit owns and site-packages isolated from the person's Python. A `pip install --user` engine conflicts with
`-I`, which hides user site-packages, and its scripts folder is off the PATH on Windows.

**Consequences**: on Windows under AppLocker or WDAC the venv's `python.exe` sits in the user profile and may need a
publisher rule from IT; where the `ai-kit` command is blocked, use `Installer.cmd`.
`managed-settings` points the guardrails it writes for IT at the venv's POSIX path
(`$HOME/.ai-kit/runtime/venv/bin/python`); it has no Windows interpreter path.

**Considered**: `pip install --user` plus `python -m ai_kit` (conflicts with `-I` and the PATH); hooks through `py -3.11`
(version chosen by a user-editable file, Windows only); an embedded Python in the ZIP (another runtime to maintain).
