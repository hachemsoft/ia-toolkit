"""Runs the test suite with no access to a model: the real CLIs are taken off the PATH and replaced by stand-ins that
record any call and fail. Use it on a workstation where gemini, agy or codex is installed (CI runners have none).

Usage: python3 scripts/offline_tests.py [unittest arguments, for example -k codex or tests.test_hooks]
Exit code: that of the tests, or 3 when a test reached one of the CLIs.
"""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLIS = ('gemini', 'agy', 'codex', 'claude')

def stand_in(folder, name, log):
    """An executable named like the CLI: records its arguments, answers nothing, fails."""
    if os.name == 'nt':
        script = folder/(name+'.cmd')
        script.write_text('@echo off\r\necho '+name+' %*>>"'+str(log)+'"\r\nexit /b 97\r\n', encoding='utf-8')
    else:
        script = folder/name
        script.write_text('#!/bin/sh\nprintf "%s %s\\n" "'+name+'" "$*" >> "'+str(log)+'"\nexit 97\n', encoding='utf-8')
        script.chmod(0o755)

def clean_path():
    """The current PATH without the folders that hold a real CLI, or an installed copy of the kit (an `ai-kit` command that
    doctor would report: the tests must not depend on what this workstation has installed)."""
    kept = []
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        if folder and not any(shutil.which(name, path=folder) for name in CLIS + ('ai-kit',)):
            kept.append(folder)
    return kept

RAN = re.compile(r'^Ran (\d+) tests? in ([\d.]+)s$', re.M)
STATUS = re.compile(r'^(OK|FAILED)(?: \((.*)\))?$', re.M)


def discovered_files(args):
    """The test files a plain `discover -s DIR [-p PATTERN] [-v]` would load, or None for any other use (-k, a module, -t):
    those run as before, in one process."""
    if not args or args[0] != 'discover':
        return None
    rest, start, pattern = args[1:], None, 'test*.py'
    while rest:
        flag = rest.pop(0)
        if flag in ('-s', '--start-directory') and rest:
            start = rest.pop(0)
        elif flag in ('-p', '--pattern') and rest:
            pattern = rest.pop(0)
        elif flag not in ('-v', '--verbose', '-q', '--quiet'):
            return None
    if not start:
        return None
    folder = Path(start) if Path(start).is_absolute() else ROOT/start
    return sorted(folder.glob(pattern))


def run_in_parallel(files, args, env, jobs):
    """One process per test file, `jobs` at a time (the biggest files first); their output in file order, then one total
    in unittest's own words, which the CI annotations read (scripts/ci_annotations.py)."""
    import concurrent.futures
    import time
    verbosity = [a for a in args[1:] if a in ('-v', '--verbose', '-q', '--quiet')]
    start = str(files[0].parent)

    # The children write UTF-8 into their pipe, whatever the console's encoding (cp1252 on a Windows runner); the runner
    # writes their output back in its own console's encoding, replacing what that encoding cannot show.
    child_env = {**env, 'PYTHONIOENCODING': 'utf-8'}
    console = sys.stdout.encoding or 'utf-8'

    def show(text):
        sys.stdout.flush()
        sys.stdout.buffer.write(text.encode(console, errors='replace'))
        sys.stdout.buffer.flush()

    def run(path):
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', start, '-p', path.name, *verbosity],
                              cwd=ROOT, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding='utf-8', errors='replace')
        return proc.returncode, proc.stdout

    began = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {path: pool.submit(run, path) for path in sorted(files, key=lambda p: p.stat().st_size, reverse=True)}
        results = [(path, futures[path].result()) for path in files]
    total, counts, failed = 0, {}, False
    for path, (code, output) in results:
        ran = list(RAN.finditer(output))
        body = output[:output.rfind('\n-', 0, ran[-1].start()) + 1] if ran else output
        show(body if body.endswith('\n') else body + '\n')
        total += int(ran[-1].group(1)) if ran else 0
        status = list(STATUS.finditer(output))
        if not ran or not status or status[-1].group(1) == 'FAILED' or code not in (0, 5):
            failed = True
        for part in (status[-1].group(2) or '').split(', ') if status else []:
            if '=' in part:
                key, value = part.split('=')
                counts[key] = counts.get(key, 0) + int(value)
        if not ran or not status:
            counts['errors'] = counts.get('errors', 0) + 1
            print('ERROR: ' + path.name + ' did not report (exit code ' + str(code) + ')')
    detail = ', '.join(key + '=' + str(counts[key]) for key in ('failures', 'errors', 'skipped', 'expected failures', 'unexpected successes') if counts.get(key))
    print('-' * 70)
    print('Ran ' + str(total) + ' tests in ' + format(time.monotonic() - began, '.3f') + 's (' + str(len(files)) + ' files, ' + str(jobs) + ' at a time)')
    print()
    print(('FAILED' if failed else 'OK') + (' (' + detail + ')' if detail else ''))
    sys.stdout.flush()
    return 1 if failed else 0


def main(argv):
    with tempfile.TemporaryDirectory(prefix='ai-kit-offline-') as tmp:
        tools = Path(tmp)/'bin'
        tools.mkdir()
        log = Path(tmp)/'cli-calls.log'
        # The interpreter running this script, git and sh stay reachable when their folder also held a CLI and was dropped.
        kept = clean_path()
        for name, path in (('python3', sys.executable), ('python', sys.executable), ('git', shutil.which('git')), ('sh', shutil.which('sh'))):
            if path and str(Path(path).parent) not in kept:
                if os.name == 'nt':
                    # A copy of python.exe or git.exe does not start away from its DLLs (0xC0000135, seen on a Windows VM
                    # where Python is not on SYSTEM's PATH): a .cmd calls the program where it is.
                    (tools/(name+'.cmd')).write_text('@"' + str(path) + '" %*\r\n', encoding='utf-8')
                    continue
                target = tools/name
                try:
                    target.symlink_to(path)
                except OSError:
                    shutil.copy2(path, target)
        stand_ins = Path(tmp)/'stand-ins'
        stand_ins.mkdir()
        for name in CLIS:
            stand_in(stand_ins, name, log)
        env = {k: v for k, v in os.environ.items() if not k.endswith(('_API_KEY', '_TOKEN')) and k not in ('GOOGLE_APPLICATION_CREDENTIALS', 'PYTHONPATH')}
        env.update({'PATH': os.pathsep.join([str(tools)] + kept), 'AI_KIT_NO_LIVE': '1', 'AI_KIT_STAND_INS': str(stand_ins),
                    'AI_KIT_CLI_LOG': str(log), 'PYTHONDONTWRITEBYTECODE': '1'})
        for name in CLIS:
            if shutil.which(name, path=env['PATH']):
                print('A real '+name+' is still reachable on the cleaned PATH: tests not run.', file=sys.stderr)
                return 3
        args = list(argv) or ['discover', '-s', 'tests']
        jobs = int(os.environ.get('AI_KIT_TEST_JOBS') or os.cpu_count() or 1)
        files = discovered_files(args)
        if jobs > 1 and files and len(files) > 1:
            code = run_in_parallel(files, args, env, jobs)
        else:
            code = subprocess.call([sys.executable, '-m', 'unittest', *args], cwd=ROOT, env=env)
        calls = log.read_text(encoding='utf-8').splitlines() if log.exists() else []
        if calls:
            print('\nCalls to a model CLI during the tests (stand-ins, nothing sent):', file=sys.stderr)
            for line in calls:
                print('  '+line, file=sys.stderr)
            return 3
        print('\nNo call to gemini, agy, codex or claude during the tests.')
        return code

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
