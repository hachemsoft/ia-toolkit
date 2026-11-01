# Spec: the `ai-kit` command in the person's terminal

## Decision
At setup, the guided screen asks "Add the `ai-kit` command to your terminal?" (yes by default). `update` keeps the answer,
`uninstall` undoes it. Without the launcher (no kit folder known) nothing is asked or written: there is nothing to point to.

## What is installed
- `~/.ai-kit/bin/ai-kit.cmd` (Windows) or `~/.ai-kit/bin/ai-kit` (Mac, Linux): a managed file, tracked in `state.json`
  like `friction.py`, that runs the launcher of the kit folder (`Installer.cmd`, `scripts/bootstrap.sh`) with the same
  arguments. `ai-kit update` is therefore the launcher's update: fetch, reinstall, apply. `ai-kit` alone opens the menu
  without the final pause.
- The folder on the person's own PATH:
  - Windows: `%USERPROFILE%\.ai-kit\bin` appended to the user `Path` (`HKCU\Environment`, kept `REG_EXPAND_SZ`), never
    the machine PATH, never through `setx` (it truncates at 1024 characters); Windows is told the environment changed.
    Only when the kit runs in the real home folder: a `--home` trial touches no registry.
  - Mac, Linux: a marked block in the login shell's startup file under the home folder (`.zshrc` for zsh, `.bash_profile`
    for bash on macOS, `.bashrc` on Linux, `.profile` for sh), written and backed up like every other file of the plan.
    An unknown shell gets the line to add, as a notice.
- `state.json` records `command`: chosen, the startup file edited, whether the registry was changed, the kit folder.

## Behaviour
- First setup: question, yes by default. `setup --profile …` without a terminal: yes, unless `--command-on-path no`.
- `update`: the recorded choice; the shim is rewritten when the kit folder changed (a moved clone).
- `update` run without the launcher (a developer's `pip install .`): the existing shim is kept as it is, never deleted.
- Choice turned to no, or `uninstall`: the shim goes (managed file), the startup block is removed, the registry entry too.
- `doctor`: `[OK]` when the shim's kit folder exists; `[Check]` when it moved or was deleted ("run the installer from the
  kit folder"); `[Info]` when `~/.ai-kit/bin` is not yet in this terminal's PATH ("open a new terminal").
- Nothing downloaded, no model call, no administrator right.

## Contract changes (documented in installer.md and compliance.md)
- "Changes nothing to the PATH or the shell startup files" becomes "only the person's own PATH, only when chosen (default
  yes), removed by uninstall". The system PATH, the execution policy and the kit folder are untouched.
- Launcher comments and the getting-started table name `ai-kit <action>` as the everyday form, the launcher as the fallback.

## Risks
- The startup file is the person's own: the kit writes one marked block, idempotent, backed up, removed by uninstall, and
  never touches the rest of the file. A file that is a symbolic link stops the installation (existing rule).
- A kit folder moved or deleted leaves a dead shim: `doctor` says so; running the installer from the new place rewrites it.
- The registry write cannot be rolled back with the files: it is idempotent and done after the files are committed.

## Acceptance (tests)
- Plan with a kit folder: shim written with that folder, startup block present once, state records it; twice: no change.
- Choice no, then uninstall: shim and block gone, the rest of the startup file intact.
- No kit folder known: no shim, no question; an existing shim is kept.
- Registry: add/remove on a fake registry keeps the other entries and the `REG_EXPAND_SZ` kind; idempotent.
- Doctor: moved folder reported.
- Launcher comment and docs updated; CHANGELOG 0.46.0.
