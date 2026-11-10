"""Does each CLI still offer what the kit relies on? Run against the CLIs installed on this machine (or in CI, against
their latest release): the version each one reports, and the options the kit and its evals use, read from their --help.

Usage: python3 scripts/cli_drift.py [--json report.json]
No model call, no sign-in needed: only --version and --help. Exit code 1 when an option the kit relies on is gone,
0 otherwise; a version newer than the one the kit was checked on is reported, not failed. A CLI that is not installed
is skipped (Antigravity CLI is not published on npm, so the CI does not install it).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from installer.adapters import ADAPTERS  # noqa: E402

# What the kit runs: the evals' non-interactive commands (evals/run.py, cli_command) and nothing else. A missing option
# breaks the evals first; the installed files are checked by the tests and by doctor.
RELIED_ON = {
    'gemini': (['--help'], ['--approval-mode', '--policy', '--skip-trust', '--prompt']),
    'agy': (['--help'], ['--print-timeout']),
    'codex': (['exec', '--help'], ['--skip-git-repo-check', '--ephemeral', '--color', '--sandbox']),
    'claude': (['--help'], ['--print', '--disallowedTools', '--model']),
}


def run(command):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return '', str(exc)
    return (proc.stdout or '') + (proc.stderr or ''), None


def parts(version):
    return tuple(int(x) for x in version.split('.')[:3])


def check(adapter):
    path = shutil.which(adapter.COMMAND)
    if not path:
        return {'cli': adapter.LABEL, 'status': 'not installed'}
    out, error = run([path, '--version'])
    match = re.search(r'\d+(?:\.\d+)+', out)
    version = match.group(0) if match else None
    args, options = RELIED_ON[adapter.NAME]
    help_text, help_error = run([path, *args])
    missing = [o for o in options if not re.search(r'(?<![\w-])' + re.escape(o) + r'(?![\w-])', help_text)]
    result = {'cli': adapter.LABEL, 'version': version, 'verified': adapter.VERIFIED,
              'newer': bool(version) and parts(version) > parts(adapter.VERIFIED), 'missing_options': missing,
              'status': 'broken' if missing or help_error else 'ok'}
    if help_error:
        result['error'] = help_error
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json')
    args = parser.parse_args(argv)
    results = [check(a) for a in ADAPTERS]
    for r in results:
        if r['status'] == 'not installed':
            print('[Skip] ' + r['cli'] + ': not installed')
            continue
        line = r['cli'] + ' ' + str(r['version']) + ' (checked on ' + r['verified'] + ')'
        if r['version'] is None and r['status'] != 'broken':
            print('[Check] ' + r['cli'] + ': version unreadable (--version printed no version); the options were checked')
        elif r['status'] == 'broken':
            print('[Broken] ' + line + ': options gone: ' + ', '.join(r['missing_options'] or [r.get('error', '')]))
        elif r['newer']:
            print('[Newer] ' + line + ': the options the kit relies on are still there; check the adapter, then raise VERIFIED')
        else:
            print('[OK] ' + line)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(results, handle, indent=2)
    return 1 if any(r['status'] == 'broken' for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
