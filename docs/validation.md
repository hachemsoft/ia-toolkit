# Validation on enterprise workstations

The kit targets people working on Windows or macOS with a standard account: no administrator rights, possibly a proxy, network restrictions, execution policies and software approved by IT. Python and the CLI are prerequisites provided or approved by the company. The kit checks them, then configures only its own content in the person's folders. This page states what the kit commits to, what CI proves, and the checks that only a real company workstation can make.

## The path, on both platforms

| Step | Windows | macOS |
| --- | --- | --- |
| Download | `ai-kit-<version>.zip`, from the Releases page of the kit repository | the same |
| Extract | right-click the ZIP, **Extract All** | double-click the ZIP |
| Install | double-click `Installer.cmd` in the extracted folder | open **Terminal**, type `sh ` (with a space), drag the `scripts/bootstrap.sh` file of the extracted folder into the window, press Enter |
| Choices | the guided screens: your CLIs, your profile, optional adjustments, a review of the changes, then Install | the same |
| `30_USER.md` | the installer shows its path and offers to open it in Notepad | the same, in the default text editor (TextEdit unless you chose another) |
| Use | start a new session of your CLI | the same |

Update: download and extract the new ZIP, then run the installer the same way. CLIs, profile, team, choices, `overrides.json` and `30_USER.md` are kept. The previous folder can be deleted: nothing installed points to it. Uninstall: run the installer and choose **Uninstall**.

**No double-click launcher on macOS.** A file extracted from a ZIP downloaded with a browser carries the quarantine attribute. Gatekeeper refuses an unsigned script (`spctl --assess` answers "rejected, no usable signature"), and a script cannot be notarized on its own. Getting past this would mean changing a security decision ("Open Anyway"), which the kit never asks for. `sh scripts/bootstrap.sh` reads the file instead of opening it as an application, so quarantine does not apply and there is nothing to authorise. The terminal path is therefore the reliable one.

## Commitments

| Commitment | How it is held | Proof |
| --- | --- | --- |
| No administrator rights, no `sudo`, no elevation | everything is written under the person's home folder: `~/.ai-kit`, `~/.gemini`, `~/.codex`, `~/.claude` and `~/.claude.json` | static test: no elevation command; manual check below (CI runners are administrators) |
| No system change: registry, system or user PATH, execution policy, Gatekeeper, quarantine attributes, shell startup files, the global Python | the launchers only find Python; `scripts/launcher.py` creates the kit's private environment in `~/.ai-kit/runtime` with the standard `venv` and `pip` | `test_no_system_change_in_installer_and_launchers` |
| From a ZIP, nothing downloaded | pip installs the kit and its libraries from the ZIP's `wheels/` folder with `--no-index`; all wheels are pure Python, one ZIP for every system | `test_zip_installs_with_no_index_and_no_network_then_the_folder_can_go`, `test_launchers_download_nothing` |
| From a git clone, the company's package index | pip uses the index, proxy and certificates already configured; the kit adds no index or trust setting | `test_clone_installs_with_the_configured_index_and_no_editable` |
| No call to the model | setup, update, doctor and uninstall never call it; only `doctor --live`, on request, and `AI_KIT_NO_LIVE=1` refuses it | `test_setup_and_update_never_call_a_cli`, `test_live_refused_when_no_live_is_set` |
| Python without `venv` or `pip` | a precise message for IT, nothing fetched to work around it | `test_missing_venv_support_explains_the_it_prerequisite` |
| No false success | a package that does not install configures nothing; an interrupted or failed installation is detected and started again; one run at a time | `test_failed_package_install_configures_nothing_and_is_detected_next_time`, `test_interrupted_install_is_started_again`, `test_a_second_run_waits_for_the_first` |
| Python absent, too old or blocked: a precise message for IT | launcher message "What to ask IT support" | `test_python_absent_says_what_to_ask_it_support` (3 systems), `test_old_or_blocked_python_is_explained` (Mac, Linux) |
| Paths with spaces and accents | no assumption on the kit or home folder path | the launcher tests run from `Mes documents é/Kit IA été/ai-kit 1` |
| The extracted folder can be deleted | the package lives in the private environment; hooks, scripts and the `overrides.json` schema are copied to `~/.ai-kit` | `test_setup_then_the_extracted_folder_can_be_deleted` |
| Uninstall removes only the kit's files | managed files recognised as unchanged, kit entries and blocks; personal files and a hand-edited file kept | `UninstallTests` |
| Existing configuration preserved: proxy, authentication, CLI settings, `30_USER.md`, `overrides.json` | managed keys and blocks only; a hand-edited managed file is refused, not overwritten; backup before writing | `test_new_version_from_another_folder_keeps_personal_settings` and the installation tests |
| No secret kept or shown | frictions are redacted; `doctor` flags a key or token written in `30_USER.md` or `overrides.json` without printing it; diagnoses never print environment values | `SecretsAndNetworkTests` |
| `30_USER.md` stays plain text | native plain-text editor; a file saved as rich text, renamed or not UTF-8 is detected and not applied | `PersonalContextTests` |

## What CI proves

The `Portability` workflow runs on every push and on each version tag.

- **Native tests**: the whole suite on Ubuntu, macOS and Windows, with Python 3.9, 3.11, 3.13 and 3.14, through `scripts/offline_tests.py` (no model CLI reachable, `AI_KIT_NO_LIVE=1`). A local folder of wheels stands for a company package index. On Windows, `Installer.cmd` really runs under `cmd.exe`, and on macOS and Linux `bootstrap.sh` really runs under `sh`. Both start from folders with spaces, accents and parentheses, with parasite modules in the current folder and `PYTHONPATH`.
- **Release ZIP**: `scripts/build_release.py` builds the ZIP people download. On each of the three systems, with Python 3.9 and 3.14 and no package index reachable, the tests extract it and install from it with its own launcher. They also run the launcher without Python, then install a new version from another folder after deleting the first.
- **Publication**: on a `v<version>` tag, once everything above has passed, the ZIP is attached to the GitHub release with the CHANGELOG section.

What CI does not prove: the runners are administrator accounts, without a proxy, AppLocker, Gatekeeper prompts, Mark of the Web or a company policy. No real CLI is signed in.

## Checks on real company workstations

To do on a Windows and a macOS workstation, with a **standard account**, for each version that changes the launchers or the installer. Note the date, the system version, the Python version and the CLI version for each run.

| # | Criterion | How | Expected |
| --- | --- | --- | --- |
| 1 | Standard account | install from the ZIP | no administrator prompt (UAC, macOS password) at any time |
| 2 | Install and update without elevation | install version N, then N+1 from a new ZIP extracted elsewhere; delete the first folder | profile, team, `overrides.json`, `30_USER.md` kept; `doctor` green |
| 3 | Spaces and accents | extract to `Documents\Kit IA été` (Windows), `Documents/Kit IA été` (macOS) | install OK |
| 4 | Compatible Python present | the company Python | install OK |
| 5 | Python absent | a workstation or session without Python | message "What to ask IT support", nothing written |
| 6 | Python inaccessible | Windows: only the Microsoft Store alias, or Python blocked by AppLocker or WDAC; macOS: `/usr/bin/python3` without developer tools | message about an absent or blocked Python; no Store window, no developer tools installation prompt |
| 7 | Downloaded launcher (Windows) | double-click `Installer.cmd` from the extracted ZIP | either Windows asks to confirm a downloaded file (the company decides), or the launcher runs; if a policy blocks it, IT decides, nothing is changed |
| 8 | CLI present, not signed in | install, then `doctor --live` (one real call, may be billed) | install complete without any call; the check says which sign-in is missing and how to do it |
| 9 | Network unavailable or model blocked | disconnect, then install from the ZIP; then `doctor --live` | install complete offline; the check names the network, the proxy or the certificate, never asks to disable a protection |
| 10 | Existing settings preserved | a `~/.gemini/settings.json` with a proxy and an authentication mode set beforehand | these values unchanged after install and update |
| 11 | No system change | Windows: `reg query HKCU\Environment` before and after; macOS: `ls -le@ ~/.zshrc ~/.zprofile` and the folder attributes before and after | identical |
| 12 | `30_USER.md` | at the end of setup, accept to open it, write a sentence about your role, save, press Enter; start a new session of the CLI and ask "what do you know about me?" | Notepad or TextEdit opens it as plain text; the agent cites the sentence |
| 13 | Python without `venv` or `pip` (some Linux or trimmed company builds) | run the installer | the message names the missing module and what to ask IT; nothing written in the CLIs' folders |
| 14 | Guided screens | run the installer in the standard terminal (Windows Terminal or the Command Prompt, macOS Terminal); use the arrows, Space, Enter, then Ctrl+C at the review | readable, keys work; after Ctrl+C, no CLI configuration changed |
| 15 | Git clone behind the company index | `git clone`, then the launcher, with the company's pip configuration | the package builds from the company index; nothing forced to PyPI |
| 16 | Uninstall | run the installer, **Uninstall**, then `uninstall --remove-runtime --yes` | only the kit's files go; `30_USER.md`, `overrides.json` and the CLIs' own settings stay; then the private environment goes |

## What IT may have to provide or allow

- Python 3.9 or newer (3.11 recommended) with its standard `venv` and `pip` modules, usable by a standard account from a command prompt or the Terminal.
- The CLI (Gemini CLI, Antigravity CLI, Codex CLI or Claude Code) and its authentication, following the company procedure.
- Network access to the model through the company proxy. With HTTPS inspection, the company root certificate, declared for command-line tools as IT says (`NODE_EXTRA_CA_CERTS` for Node.js CLIs, `SSL_CERT_FILE` for others).
- Windows: running `Installer.cmd` from the folder where the person extracted the ZIP. The launcher only finds Python, then runs `scripts\launcher.py`, which installs the kit in `%USERPROFILE%\.ai-kit\runtime` from the ZIP's own wheels.
- For a git clone only: pip's access to the company package index (it fetches the build tool and the libraries there).
