# AI Kit – Windows installation sheet (pilot)

About 15 minutes, no administrator rights: at the end, `ai-kit doctor` reports nothing left to fix and your AI CLI starts with the company's context.

## 1. Before you start

Check these four points in a terminal (PowerShell or Command Prompt). If one is missing, ask IT for it before going further: the kit downloads nothing to work around it.

| Need | Check with | Expected |
| --- | --- | --- |
| Python 3.11 or newer, with `venv` and `pip`, usable by your account | `python --version` (or `py -3 --version`) | `Python 3.11.x` or newer |
| Git 2.29 or newer | `git --version` | `git version 2.29` or newer |
| An account on the company's GitLab, with access to the kit's project and to your Team's | open the project's page in the browser | the page shows |
| Your AI CLI installed and signed in (Claude Code, Gemini CLI or Codex) | start it once | it answers |

If you ran `pip install .` during an earlier try, remove that copy first: `pip uninstall ai-kit`.

## 2. Install

1. Open the **Releases** page of the kit's project on the company's GitLab and download `ai-kit-<version>.zip` of the latest version (4.19.2 or newer). The `SHA256SUMS.txt` file next to it is for checking the download if you are asked to.
2. Right-click the ZIP, **Extract All**, into a folder of yours (for example `Documents\ai-kit-4.19.2`).
3. In the extracted folder, double-click **`Installer.cmd`**. It creates the kit's private environment in your home folder, installs the kit from the ZIP (no download), then starts the setup.
4. Answer the questions in the window:
   - **Identity**: "Detected identity: …", press Enter to confirm, or type your email address.
   - **First use of the Core**: the kit shows the Core repository's URL, tag and commit. Check that the URL is the company's GitLab, then confirm.
   - **GitLab sign-in**: a Git sign-in window may open the first time; sign in with your GitLab account.
   - **`ai-kit` command on the PATH**: accept (yes by default). It is added to your user's PATH, without administrator rights.
5. Close the window and **open a new terminal**: the `ai-kit` command only exists in terminals opened after the installation.

Keep the extracted folder until the end of the pilot: it is used to run the installation again if needed.

## 3. Check

In the new terminal:

| Command | What you should see |
| --- | --- |
| `ai-kit status` | the kit's version (4.19.2 or newer) and the active Core with its `vX.Y.Z` tag |
| `ai-kit doctor` | a summary with no `[Check]` line; each `[Check]` says what to do |

`ai-kit doctor` does not call the model and changes nothing. Do not run `ai-kit doctor --live` without a reason: it makes a real call to the model, which may be billed.

## 4. Join your Team

Your pilot contact gives you your Team's name and its repository URL. The first time:

```
ai-kit team use <team-name> --url https://<gitlab-host>/<group>/<team-project>.git
```

Afterwards, `ai-kit team list` shows the known Teams (the active one is marked `*`), and `ai-kit team use none` leaves the Team. As for the Core, the first use shows the URL, tag and commit to confirm.

## 5. First session

1. Open a terminal in one of your repositories and start your AI CLI.
2. Type `/guide where do I start?` (in Codex: `$guide`). Plain sentences work too: commands are shortcuts.
3. Introduce yourself to the agent: type `/me` in the CLI, or `ai-kit user edit` in a terminal to edit your `USER.md`. Then start a new session.
4. Something gets in your way during the pilot? Type `/friction`: it is recorded locally, for the usage review.

## 6. Update

Two things change separately:

| What changes | Example | How you get it |
| --- | --- | --- |
| The content: Core and Team | context, commands, skills, announcements | `ai-kit sync` (follows the repositories' `vX.Y.Z` tags) |
| The kit's engine | a fix to the `ai-kit` command or the hooks | download the new ZIP from the Releases page, extract it, double-click `Installer.cmd`, open a new terminal |

Nothing to uninstall before an update: your `aikit.toml`, your `USER.md` and your Team are kept. `ai-kit status` says whether a newer tag was seen at the last sync, and `ai-kit rollback` returns to the previous configuration.

## 7. If something goes wrong

| Message or symptom | What to do |
| --- | --- |
| `Python 3.11 or newer was not found` (or "older than 3.11") | ask IT for Python 3.11+ with `venv` and `pip` |
| `This Python has no venv or pip support` | ask IT for a complete Python installation |
| `ai-kit` is not recognized | open a **new** terminal; otherwise run `Installer.cmd` again |
| `doctor`: "The `ai-kit` command on your PATH is another copy of the kit" | `pip uninstall ai-kit` with the Python used for an earlier `pip install .`, then a new terminal |
| `git ls-remote failed (auth)` | sign in to GitLab: run `git ls-remote <repository URL>` once in a terminal and sign in, then run the command again |
| `git ls-remote failed (network)` with `CRYPT_E_NO_REVOCATION_CHECK` | `git config --global http.schannelCheckRevoke false` (passed on by the kit since 4.19.1), or ask IT to set it in Git's configuration |
| `First use of <URL> needs your confirmation in a terminal` | run `ai-kit sync` in a terminal and confirm the URL, tag and commit |
| `Another run of the kit installer is in progress` | wait for the other window to finish |

Still stuck: send the full output of `ai-kit doctor` to your pilot contact (read it first: it shows your identity and paths on your workstation).

## 8. What the kit does on your workstation

- No administrator rights: everything is written under your home folder (`~\.ai-kit` and your CLIs' folders).
- One change outside these folders: the `ai-kit` command on your user's PATH, removed by uninstall.
- No model call, except `ai-kit doctor --live` when you ask for it.
- A backup in `~\.ai-kit\backups` at every run that changes files.

To uninstall: `ai-kit uninstall --dry-run` shows what would be removed, then `ai-kit uninstall` asks for confirmation. Kept: your `USER.md`, your `aikit.toml` and the backups.
