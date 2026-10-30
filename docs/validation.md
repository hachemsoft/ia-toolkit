# Validation on enterprise workstations

The kit targets people working on Windows or macOS with a standard account: no administrator rights, possibly a proxy, network restrictions, execution policies and software approved by IT. Python and the CLI are prerequisites provided or approved by the company. The kit checks them, then configures only its own content in the person's folders. This page states what the kit commits to, what CI proves, and the checks that only a real company workstation can make.

## The path, on both platforms

| Step | Windows | macOS |
| --- | --- | --- |
| Download | `ai-kit-<version>.zip`, from the Releases page of the kit repository | the same |
| Extract | right-click the ZIP, **Extract All** | double-click the ZIP |
| Install | double-click `Installer.cmd` in the extracted folder | open **Terminal**, type `sh ` (with a space), drag the `scripts/bootstrap.sh` file of the extracted folder into the window, press Enter |
| Profile | choose from the menu | the same |
| `30_USER.md` | the installer shows its path and offers to open it in Notepad | the same, in the default text editor (TextEdit unless you chose another) |
| Use | start a new session of your CLI | the same |

Update: download and extract the new ZIP, then run the installer the same way. Profile, team, `overrides.json` and `30_USER.md` are kept. The previous folder can be deleted: nothing installed points to it.

**No double-click launcher on macOS.** A file extracted from a ZIP downloaded with a browser carries the quarantine attribute. Gatekeeper refuses an unsigned script (`spctl --assess` answers "rejected, no usable signature"), and a script cannot be notarized on its own. Getting past this would mean changing a security decision ("Open Anyway"), which the kit never asks for. `sh scripts/bootstrap.sh` reads the file instead of opening it as an application, so quarantine does not apply and there is nothing to authorise. The terminal path is therefore the reliable one.

## Commitments

| Commitment | How it is held | Proof |
| --- | --- | --- |
| No administrator rights, no `sudo`, no elevation | everything is written under the person's home folder: `~/.ai-kit`, `~/.gemini`, `~/.codex` | static test: no elevation command; manual check below (CI runners are administrators) |
| No system change: registry, system or user PATH, execution policy, Gatekeeper, quarantine attributes, shell startup files | the launchers only find Python and run `python -m installer` from the kit folder | `test_no_system_change_in_installer_and_launchers` |
| Nothing downloaded, nothing installed | Python standard library only; no pip, pipx, uv, Homebrew, Git, Node.js | `test_launchers_download_nothing`, `test_no_runtime_dependency_and_python39` |
| Works offline | only the final check calls the model; if it fails, the installation is still complete and the message names the cause (network, proxy, certificate, authentication) | `test_network_proxy_and_certificate_failures_explained` |
| Python absent, too old or blocked: a precise message for IT | launcher message "What to ask IT support" | `test_python_absent_says_what_to_ask_it_support` (3 systems), `test_old_or_blocked_python_is_explained` (Mac, Linux) |
| Paths with spaces and accents | no assumption on the kit or home folder path | the launcher tests run from `Mes documents é/Kit IA été/ai-kit 1` |
| The extracted folder can be deleted | hooks, scripts and the `overrides.json` schema are copied to `~/.ai-kit` | `test_setup_then_the_extracted_folder_can_be_deleted` |
| Existing configuration preserved: proxy, authentication, CLI settings, `30_USER.md`, `overrides.json` | managed keys and blocks only; a hand-edited managed file is refused, not overwritten; backup before writing | `test_new_version_from_another_folder_keeps_personal_settings` and the installation tests |
| No secret kept or shown | frictions are redacted; `doctor` flags a key or token written in `30_USER.md` or `overrides.json` without printing it; diagnoses never print environment values | `SecretsAndNetworkTests` |
| `30_USER.md` stays plain text | native plain-text editor; a file saved as rich text, renamed or not UTF-8 is detected and not applied | `PersonalContextTests` |

## What CI proves

The `Portability` workflow runs on every push and on each version tag.

- **Native tests**: the whole suite on Ubuntu, macOS and Windows, with Python 3.9, 3.11, 3.13 and 3.14. On Windows, `Installer.cmd` really runs under `cmd.exe`, and on macOS and Linux `bootstrap.sh` really runs under `sh`. Both start from folders with spaces and accents.
- **Release ZIP**: `scripts/package.sh` builds the ZIP people download. On each of the three systems, the tests extract it and install from it with its own launcher. They also run the launcher without Python, then install a new version from another folder after deleting the first.
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
| 8 | CLI present, not signed in | install, then run the final check | install complete; the check says which sign-in is missing and how to do it |
| 9 | Network unavailable or model blocked | disconnect, or a network without access to the model | install complete; the check names the network, the proxy or the certificate, never asks to disable a protection |
| 10 | Existing settings preserved | a `~/.gemini/settings.json` with a proxy and an authentication mode set beforehand | these values unchanged after install and update |
| 11 | No system change | Windows: `reg query HKCU\Environment` before and after; macOS: `ls -le@ ~/.zshrc ~/.zprofile` and the folder attributes before and after | identical |
| 12 | `30_USER.md` | at the end of setup, accept to open it, write a sentence about your role, save, press Enter; start a new session of the CLI and ask "what do you know about me?" | Notepad or TextEdit opens it as plain text; the agent cites the sentence |

## What IT may have to provide or allow

- Python 3.9 or newer (3.11 recommended), usable by a standard account from a command prompt or the Terminal.
- The CLI (Gemini CLI, Antigravity CLI or Codex CLI) and its authentication, following the company procedure.
- Network access to the model through the company proxy. With HTTPS inspection, the company root certificate, which Node.js reads from `NODE_EXTRA_CA_CERTS`.
- Windows: running `Installer.cmd` from the folder where the person extracted the ZIP. The launcher only finds Python, then runs `python -m installer` from that folder.
