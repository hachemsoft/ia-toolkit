#!/usr/bin/env python3
"""Prove that an acceptance test fails without the code of the change (ADR 0033), for the verifier.

Modes:
  prove --test PATH [--test PATH...] [--keep PATH...] [--base REF] [--timeout S] -- COMMAND...
      put each code file of the change back to its base version (a new file set aside, a deleted one put back), keep the
      tests at their new version, run COMMAND, restore. Verdict: proven (COMMAND fails without the code), not_proven (it
      passes), not_possible (with the reason), timeout.
  base-run [--base REF] [--timeout S] -- COMMAND...
      put every file of the change back to its base version, tests included, run COMMAND, restore. Verdict:
      fails_on_base (the failure was already there), passes_on_base (the change brought it), not_possible, timeout.
  recover
      restore the backup an interrupted run left in <repo root>/.ai-kit-proof/. Verdict: recovered, nothing_to_recover.
  modified-tests [--base REF]
      the test files that existed on the base and that the change modifies or deletes.

Paths are relative to the repository root; COMMAND runs in the current folder (an area of a monorepo), stdin closed.
Safety: before any write, each file the run touches is copied into <repo root>/.ai-kit-proof/ (a folder that ignores
itself in git; its creation is the lock) with its mode and a SHA-256 digest; the files are restored on every exit the
process sees (end, error, timeout, interruption, termination signal), mode included, and checked; the backup is deleted
only when all match. A file that changed during the run (an editor saving it) is never overwritten: it is reported and
the backup stays. A symbolic link or a submodule in the change makes the proof not possible. A backup found at start
blocks every mode but recover. Git runs in read mode only (rev-parse, merge-base, diff, ls-files, ls-tree, cat-file) with
the repository's hooks, fsmonitor, external diff and textconv neutralized; a base version goes through the checkout
filters the person configured (line endings). Nothing is written to .git or the index. COMMAND runs without a shell, in
its own process group, killed with its children at the timeout. A warehouse command (dbt) needs an explicit --target.
Standard library only; no model.

Output (stdout, JSON): {"schema": 1, "mode", "base", "merge_base", "verdict", "exit_code", "command", "swapped", "kept",
"tests", "output_tail", "reason", "error"}; "tests" lists paths in prove, {"path", "change"} objects in modified-tests.
Exit code 0 when the output is valid, 2 when the repository cannot be read, a backup blocks the run or the files could
not all be restored, 130 when interrupted (files restored).
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = 1
BACKUP = '.ai-kit-proof'
TAIL = 4000
DEFAULT_TIMEOUT = 420  # under the verifier's 10 minutes, so the run ends before the agent is stopped
TEST_DIRS = {'test', 'tests', '__tests__', 'spec'}
TEST_NAMES = ('test_*.py', '*_test.py', '*_test.go', '*.test.js', '*.test.ts', '*.test.jsx', '*.test.tsx', '*.spec.js',
              '*.spec.ts', '*.spec.jsx', '*.spec.tsx', '*Test.java', '*Tests.java', '*Spec.scala', '*Test.php')
WAREHOUSE = {'dbt'}


class RepoError(Exception):
    pass


class Stopped(BaseException):
    """A termination signal: unwinds like KeyboardInterrupt so the files are restored."""


# --- Git, read-only ----------------------------------------------------------------------------------------------------

def git(repo, *args, check=True, raw=False):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    proc = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath='+os.devnull, '-C', str(repo), *args],
                          capture_output=True, env=env, timeout=60, stdin=subprocess.DEVNULL)
    if check and proc.returncode != 0:
        raise RepoError(proc.stderr.decode('utf-8', 'replace').strip() or 'git '+args[0]+' failed')
    if proc.returncode != 0:
        return None
    return proc.stdout if raw else proc.stdout.decode('utf-8', 'replace')


def resolve_base(repo, base):
    if base:
        if git(repo, 'rev-parse', '--verify', '--quiet', base+'^{commit}', check=False) is None:
            raise RepoError('base not found: '+base)
        return base
    remote = git(repo, 'rev-parse', '--abbrev-ref', 'origin/HEAD', check=False)
    if remote and remote.strip() != 'origin/HEAD':
        return remote.strip()
    for name in ('main', 'master'):
        if git(repo, 'rev-parse', '--verify', '--quiet', name+'^{commit}', check=False) is not None:
            return name
    raise RepoError('no base: pass --base (no origin/HEAD, main or master)')


def changes(repo, merge_base):
    """[(status, old_path, new_path)] from the merge base to the working tree, untracked files included as added."""
    fields = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '-M', '--name-status', '-z', merge_base).split('\0')
    found, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        if status in 'RC':
            found.append((status, fields[i+1], fields[i+2]))
            i += 3
        else:
            found.append((status, fields[i+1], fields[i+1]))
            i += 2
    for path in filter(None, git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')):
        if path.split('/')[0] != BACKUP:
            found.append(('A', path, path))
    return found


def base_mode(repo, merge_base, path):
    """'100644', '100755', '120000' (link), '160000' (submodule), or None when absent on the base."""
    line = git(repo, 'ls-tree', '-z', merge_base, '--', path)
    return line.split(' ', 1)[0] if line else None


def base_bytes(repo, merge_base, path):
    data = git(repo, 'cat-file', '--filters', merge_base+':'+path, check=False, raw=True)
    if data is None:
        raise RepoError('cannot read the base version of '+path)
    return data


def is_test_path(path, explicit=()):
    parts = path.split('/')
    return (path in explicit or any(part in TEST_DIRS for part in parts[:-1])
            or any(fnmatch.fnmatchcase(parts[-1], pattern) for pattern in TEST_NAMES))


# --- Files -------------------------------------------------------------------------------------------------------------

def digest(data):
    return hashlib.sha256(data).hexdigest()


def current(target):
    """(digest, mode bits) of a regular file, 'link' or 'other' for anything else, None when absent."""
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return 'link'
    if not stat.S_ISREG(info.st_mode):
        return 'other'
    return digest(Path(target).read_bytes()), file_mode(stat.S_IMODE(info.st_mode))


def file_mode(mode):
    """The mode bits that matter: none on Windows, where they only carry the read-only flag, read back as 0o666."""
    return None if os.name == 'nt' else mode


def retry(action):
    for attempt in range(10):  # Windows: a file held by an antivirus or an editor for a moment
        try:
            return action()
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2)


def write_file(repo, rel, data, mode):
    """Write through a temporary file in the backup folder, then replace: the target is never half written."""
    target = repo/rel
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = repo/BACKUP/'write.tmp'
    temp.write_bytes(data)
    if mode is not None:
        os.chmod(temp, mode)
    retry(lambda: os.replace(temp, target))


def remove(repo, rel):
    retry(lambda: (repo/rel).unlink(missing_ok=True))


# --- Plan, backup, swap, restore ---------------------------------------------------------------------------------------

def plan(repo, merge_base, entries, is_code):
    """{path: (bytes, mode) or None}: the base state of every file to swap (None: absent on the base, set aside)."""
    target = {}
    for status, old, new in entries:
        if status == 'D':
            code = is_code(old)
        elif status in 'RC':
            code = is_code(new) or is_code(old)
        else:
            code = is_code(new)
        if not code:
            continue
        if status == 'T':
            raise Unsupported('a file changed type (link or submodule): '+new)
        paths = [new] + ([old] if status == 'R' else [])
        for rel in paths:
            if current(repo/rel) in ('link', 'other'):
                raise Unsupported('not a regular file: '+rel)
        if status in 'RC' or status == 'A':
            target[new] = None
        if status in 'MDR':
            rel = old if status == 'R' else new
            mode = base_mode(repo, merge_base, rel)
            if mode not in ('100644', '100755'):
                raise Unsupported('not a regular file on the base: '+rel)
            target[rel] = (base_bytes(repo, merge_base, rel), file_mode(0o755 if mode == '100755' else 0o644))
    return target


class Unsupported(Exception):
    pass


def missing_parents(repo, rel):
    found, folder = [], (repo/rel).parent
    while folder != repo and not folder.exists():
        found.append(str(folder.relative_to(repo).as_posix()))
        folder = folder.parent
    return found


def backup(repo, target):
    """Copy each file as it is now into <repo>/.ai-kit-proof/; the manifest is written last, so it marks a full backup."""
    folder = repo/BACKUP
    folder.mkdir()  # fails when it exists: the lock against a second run
    (folder/'.gitignore').write_text('*\n', encoding='utf-8')
    entries, created = [], []
    for i, rel in enumerate(sorted(target)):
        now = current(repo/rel)
        swapped = target[rel]
        item = {'path': rel, 'existed': now is not None,
                'swapped': None if swapped is None else [digest(swapped[0]), swapped[1]]}
        if now is not None:
            copy = folder/str(i)
            shutil.copyfile(repo/rel, copy)
            os.chmod(copy, 0o600)
            item.update(copy=str(i), sha256=now[0], mode=now[1])
        elif swapped is not None:
            created += missing_parents(repo, rel)
        entries.append(item)
    manifest = {'schema': SCHEMA, 'files': entries, 'created_folders': sorted(set(created), key=len, reverse=True)}
    temp = folder/'manifest.json.tmp'
    with open(temp, 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, folder/'manifest.json')
    return manifest


def swap(repo, target):
    for rel, state in target.items():
        if state is None:
            remove(repo, rel)
        else:
            write_file(repo, rel, *state)


def restore(repo, manifest):
    """Put every file back and check it; a file changed during the run is kept and reported; the backup is deleted only
    when every file matches. Termination signals wait until it is done."""
    folder = repo/BACKUP
    previous = {}
    for name in ('SIGINT', 'SIGTERM', 'SIGBREAK', 'SIGHUP'):
        if hasattr(signal, name):
            try:
                previous[name] = signal.signal(getattr(signal, name), signal.SIG_IGN)
            except (OSError, ValueError):
                pass
    wrong, changed = [], []
    try:
        for item in manifest['files']:
            rel = item['path']
            now = current(repo/rel)
            original = (item['sha256'], item['mode']) if item['existed'] else None
            swapped = tuple(item['swapped']) if item['swapped'] else None
            try:
                if now == original:
                    continue
                if now != swapped and not (now is None and swapped is None):
                    changed.append(rel)  # written during the run: never overwritten
                    continue
                if original is None:
                    remove(repo, rel)
                else:
                    write_file(repo, rel, (folder/item['copy']).read_bytes(), item['mode'])
                if current(repo/rel) != original:
                    wrong.append(rel)
            except OSError:
                wrong.append(rel)
        for name in manifest.get('created_folders', []):
            path = repo/name
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    finally:
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), handler)
    if changed or wrong:
        parts = (['changed during the run, kept as they are: '+', '.join(changed)] if changed else []) + \
                (['not restored: '+', '.join(wrong)] if wrong else [])
        raise RepoError('; '.join(parts)+'. The backup stays in '+str(folder)+': compare, then run prove_test.py recover')
    shutil.rmtree(folder)


# --- Running the command -----------------------------------------------------------------------------------------------

def kill_group(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, stdin=subprocess.DEVNULL)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


def run_command(command, cwd, timeout):
    """(exit code or None on timeout, tail of stdout and stderr). The command and its children are one group."""
    extra = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    proc = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, **extra)
    deadline = time.monotonic() + timeout
    try:
        while True:  # short waits: a Windows wait does not let a signal handler run until it returns
            try:
                out, _ = proc.communicate(timeout=max(0.01, min(0.5, deadline - time.monotonic())))
                return proc.returncode, out.decode('utf-8', 'replace')[-TAIL:]
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    raise
    except subprocess.TimeoutExpired:
        kill_group(proc)
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out = b''
        return None, out.decode('utf-8', 'replace')[-TAIL:]
    finally:
        kill_group(proc)


def swapped_run(repo, target, command, cwd, timeout):
    """Back up, swap to the base state, run, restore: (exit code or None, output tail). Restores on every exit."""
    manifest = backup(repo, target)
    try:
        swap(repo, target)
        return run_command(command, cwd, timeout)
    finally:
        restore(repo, manifest)


def resolve_command(command):
    """The command with its program found on PATH (PATHEXT on Windows: npm.cmd, gradlew.bat), or None."""
    program = shutil.which(command[0])
    if program is None:
        return None
    name = Path(command[0]).name.lower()
    if Path(name).stem in WAREHOUSE and '--target' not in command and not any(a.startswith('--target=') for a in command):
        raise Unsupported('a warehouse command needs an explicit --target (the development target AGENTS.md declares)')
    return [program, *command[1:]]


# --- Modes -------------------------------------------------------------------------------------------------------------

def stopped(signum, frame):
    raise Stopped()


def result(mode, **fields):
    out = {'schema': SCHEMA, 'mode': mode, 'base': None, 'merge_base': None, 'verdict': None, 'exit_code': None,
           'command': None, 'swapped': [], 'kept': [], 'tests': [], 'output_tail': '', 'reason': None, 'error': None}
    out.update(fields)
    return out


def scope(repo, base):
    base = resolve_base(repo, base)
    merge_base = git(repo, 'merge-base', base, 'HEAD').strip()
    return base, merge_base, changes(repo, merge_base)


def rooted(repo, cwd, path):
    """A path given from the current folder, made relative to the repository root."""
    full = (cwd/path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        return full.relative_to(repo).as_posix()
    except ValueError:
        return Path(path).as_posix()


def run_mode(repo, args, mode, is_code_for):
    base, merge_base, entries = scope(repo, args.base)
    out = result(mode, base=base, merge_base=merge_base, command=args.command)
    try:
        command = resolve_command(args.command)
        if command is None:
            return dict(out, verdict='not_possible', reason='command not found: '+args.command[0]), 0
        is_code, extra = is_code_for(entries, out)
        if extra:
            return dict(out, **extra), 0
        target = plan(repo, merge_base, entries, is_code)
    except Unsupported as reason:
        return dict(out, verdict='not_possible', reason=str(reason)), 0
    out['swapped'] = sorted(target)
    if not target:
        return dict(out, verdict='not_possible', reason='no code file in the change, only tests'), 0
    code, tail = swapped_run(repo, target, command, args.cwd, args.timeout)
    return dict(out, exit_code=code, output_tail=tail, verdict=None if code is None else code), 0


def prove(repo, args):
    tests = [rooted(repo, args.cwd, t) for t in args.test]
    keep = {rooted(repo, args.cwd, k) for k in args.keep}

    def is_code_for(entries, out):
        changed = {new for status, _, new in entries if status != 'D'}
        missing = [t for t in tests if t not in changed]
        if missing:
            return None, {'verdict': 'not_possible', 'reason': 'not in the change: '+', '.join(missing)}
        out.update(kept=sorted(keep & changed), tests=sorted(p for p in changed if is_test_path(p, tests)))
        return (lambda path: not is_test_path(path, tests) and path not in keep), None

    out, code = run_mode(repo, args, 'prove', is_code_for)
    if isinstance(out['verdict'], int) or (out['verdict'] is None and out['swapped']):
        out['verdict'] = 'timeout' if out['exit_code'] is None else 'not_proven' if out['exit_code'] == 0 else 'proven'
    return out, code


def base_run(repo, args):
    out, code = run_mode(repo, args, 'base-run', lambda entries, out: ((lambda path: True), None))
    if isinstance(out['verdict'], int) or (out['verdict'] is None and out['swapped']):
        out['verdict'] = 'timeout' if out['exit_code'] is None else 'passes_on_base' if out['exit_code'] == 0 else 'fails_on_base'
    return out, code


def safe_manifest(repo, manifest):
    """A manifest is data the repository could have planted: every path stays inside the repository."""
    root = repo.resolve()
    for item in manifest.get('files', []):
        rel = item.get('path', '')
        full = (repo/rel).resolve() if rel else None
        if (not rel or Path(rel).is_absolute() or '..' in Path(rel).parts or full is None or root not in full.parents
                or (item.get('existed') and not re.fullmatch(r'\d+', str(item.get('copy', ''))))):
            raise RepoError('the backup manifest names a path outside the repository: refused')
    for name in manifest.get('created_folders', []):
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise RepoError('the backup manifest names a folder outside the repository: refused')


def recover(repo, args):
    folder = repo/BACKUP
    if folder.is_symlink() or git(repo, 'ls-files', '--', BACKUP).strip():
        raise RepoError(BACKUP+' is a link or tracked by git: not a backup this kit wrote; refused')
    manifest_file = folder/'manifest.json'
    if not manifest_file.is_file():
        if folder.is_dir():
            shutil.rmtree(folder)  # cut short before any swap: nothing to put back
        return result('recover', verdict='nothing_to_recover'), 0
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    safe_manifest(repo, manifest)
    restore(repo, manifest)
    return result('recover', verdict='recovered', swapped=[m['path'] for m in manifest['files']]), 0


def modified_tests(repo, args):
    base, merge_base, entries = scope(repo, args.base)
    found = [{'path': old, 'change': 'deleted' if status == 'D' else 'modified'}
             for status, old, new in entries if status in 'MDRT' and is_test_path(old)]
    return result('modified-tests', base=base, merge_base=merge_base, tests=found), 0


MODES = {'prove': prove, 'base-run': base_run, 'recover': recover, 'modified-tests': modified_tests}


def parse(argv):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if '--' in argv:
        i = argv.index('--')
        argv, command = argv[:i], argv[i+1:]
    parser = argparse.ArgumentParser(prog='prove_test.py', description='Prove that a test fails without the code (ADR 0033).')
    parser.add_argument('--repo', default='.', help='a folder of the repository (default: the current folder)')
    sub = parser.add_subparsers(dest='mode', required=True)
    for name in MODES:
        mode = sub.add_parser(name)
        if name != 'recover':
            mode.add_argument('--base', help='the branch the work merges into (default: origin/HEAD, else main, else master)')
        if name in ('prove', 'base-run'):
            mode.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                              help='seconds before the command and its children are stopped (default %d)' % DEFAULT_TIMEOUT)
        if name == 'prove':
            mode.add_argument('--test', action='append', default=[], required=True, help='an approved acceptance test file')
            mode.add_argument('--keep', action='append', default=[], help='a changed file left at its new version')
    args = parser.parse_args(argv)
    args.command = command
    if args.mode in ('prove', 'base-run') and not command:
        parser.error('give the test command after --')
    return args


def main(argv=None):
    args = parse(argv)
    start = Path(args.repo).resolve()
    args.cwd = start
    for name in ('SIGTERM', 'SIGBREAK', 'SIGHUP'):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stopped)
            except (OSError, ValueError):
                pass
    try:
        repo = Path(git(start, 'rev-parse', '--show-toplevel').strip()).resolve()
        if args.mode != 'recover' and (repo/BACKUP).exists():
            raise RepoError('a proof is running in this repository, or one was cut short: '+str(repo/BACKUP)+
                            ' exists; if none is running, run prove_test.py recover')
        out, code = MODES[args.mode](repo, args)
    except (RepoError, OSError, subprocess.SubprocessError) as error:
        out, code = result(args.mode, error=str(error)), 2
    except (KeyboardInterrupt, Stopped):
        out, code = result(args.mode, error='interrupted; the files were restored'), 130
    sys.stdout.write(json.dumps(out, ensure_ascii=True, indent=1)+'\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
