"""The model-free suite on a Windows virtual machine, from the Mac, in one command. Optional tool, for a maintainer with a
UTM VM that runs the guest agent; the CI's Windows jobs stay the gate.

It bundles a branch of this checkout (committed work only), pushes the bundle and a cmd script into the guest, clones the
branch there, runs `scripts\\offline_tests.py discover -s tests -v` in the background, polls its log and prints the lines
that matter. It installs nothing and never runs `ai-kit` in the guest.

Usage: python3 scripts/vm_tests.py --python 'C:\\...\\python.exe' [--vm Windows] [--branch main]
       [--guest-dir 'C:\\Users\\Public'] (no space in it) [--interval 30] [--timeout 1800]
Exit code: the suite's own (0 OK), 2 when the VM or its tool cannot be reached or the run does not end in time.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

UTMCTL = '/Applications/UTM.app/Contents/MacOS/utmctl'
KEPT = re.compile(r'^(FAIL|ERROR): |^(OK|FAILED)\b|^Ran \d+ tests|^\w*Error\b|^Traceback')


def guest_script(python, branch, folder=r'C:\Users\Public'):
    """The cmd script run in the guest: a fresh clone of the bundled branch, the suite, then EXIT=<code> as the last line.
    CRLF line endings: cmd.exe misreads a script without them."""
    work = folder + r'\ai-kit-vm-tests'
    lines = ['@echo off',
             'rmdir /s /q "' + work + '" 2>nul',
             'git clone -q -b ' + branch + ' "' + folder + r'\ai-kit-vm-tests.bundle" "' + work + '" || (echo EXIT=2 & exit /b 2)',
             'cd /d "' + work + '"',
             '"' + python + '" --version',
             '"' + python + r'" scripts\offline_tests.py discover -s tests -v',
             'echo EXIT=%ERRORLEVEL%']
    return '\r\n'.join(lines) + '\r\n'


def summary(log):
    """(exit code or None while the suite runs, the lines that matter) of the guest's log."""
    lines = [line.rstrip() for line in log.replace('\r\n', '\n').split('\n')]
    code = None
    for line in lines:
        match = re.match(r'^EXIT=(\d+)', line.strip())
        if match:
            code = int(match.group(1))
    if code is None:
        return None, []
    return code, [line for line in lines if KEPT.search(line)]


def utmctl(*args, stdin=None, timeout=300):
    """One utmctl call, ended after timeout seconds: a guest agent that stops answering must not hold the run forever
    (2026-11-22: a file push waited 30 minutes). A call that timed out returns code 124, as timeout(1) does."""
    try:
        return subprocess.run([UTMCTL, *args], input=stdin, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([UTMCTL, *args], 124, b'', ('utmctl did not answer within ' + str(timeout) + 's').encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the model-free suite on a Windows UTM VM (optional, for maintainers).')
    parser.add_argument('--python', required=True, help="the guest's python.exe (the guest agent's PATH may not have it)")
    parser.add_argument('--vm', default='Windows')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--guest-dir', default=r'C:\Users\Public')
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args(argv)
    if not Path(UTMCTL).is_file():
        print('utmctl not found at ' + UTMCTL + ': this tool needs UTM.', file=sys.stderr)
        return 2
    folder = args.guest_dir.rstrip('\\')
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp)/'branch.bundle'
        made = subprocess.run(['git', 'bundle', 'create', str(bundle), args.branch], capture_output=True, text=True)
        if made.returncode:
            print(made.stderr.strip(), file=sys.stderr)
            return 2
        pushes = ((folder + r'\ai-kit-vm-tests.bundle', bundle.read_bytes()),
                  (folder + r'\ai-kit-vm-tests.cmd', guest_script(args.python, args.branch, folder).encode('utf-8')))
        for target, data in pushes:
            pushed = utmctl('file', 'push', args.vm, target, stdin=data)
            if pushed.returncode:
                print('push to the VM failed: ' + pushed.stderr.decode('utf-8', 'replace').strip(), file=sys.stderr)
                return 2
    log = folder + r'\ai-kit-vm-tests.log'
    utmctl('exec', args.vm, '--cmd', 'cmd.exe', '/c', 'del /q ' + log + ' 2>nul')
    started = utmctl('exec', args.vm, '--cmd', 'cmd.exe', '/c', folder + r'\ai-kit-vm-tests.cmd > ' + log + ' 2>&1')
    if started.returncode:
        print('the VM did not start the run: ' + started.stderr.decode('utf-8', 'replace').strip(), file=sys.stderr)
        return 2
    print('Running on ' + args.vm + ' (' + args.branch + '), log ' + log)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        time.sleep(args.interval)
        pulled = utmctl('file', 'pull', args.vm, log)
        code, lines = summary(pulled.stdout.decode('utf-8', 'replace')) if pulled.returncode == 0 else (None, [])
        if code is not None:
            print('\n'.join(lines))
            print('EXIT=' + str(code))
            return code
    print('No end of run after ' + str(args.timeout) + 's; the log stays at ' + log, file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
