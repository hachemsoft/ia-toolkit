"""AI Kit launcher: the single entry point behind Installer.cmd (Windows) and scripts/bootstrap.sh (Mac, Linux).

Standard library only, run with `python -I` (no current folder, no PYTHONPATH, no user site on the import path):
1. checks that this Python can create a virtual environment with pip;
2. creates or reuses the kit's private environment, ~/.ai-kit/runtime/venv, at its final place;
3. installs the kit package and its dependencies there: from the release ZIP's wheels/ folder only (no index, no download),
   or from a git clone (built by pip, dependencies from the package index pip is already configured for);
4. runs the kit (python -m ai_kit) with that environment's Python, from the person's current folder;
5. for update in a git clone, first fetches the new version with git, never over local changes.

It never activates the environment for the person, never touches the global Python, the PATH or the shell, and needs no
administrator rights. Messages are plain text: the interface libraries are not installed yet.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

KIT_DIR = Path(__file__).resolve().parents[1]
MINIMUM = (3, 9)
SOURCE_PARTS = ('installer', 'runtime', 'agents', 'commands', 'practices', 'profiles', 'skills', 'templates', 'schemas',
                'packaging', 'VERSION', 'organization.json', 'CHANGELOG.md', 'pyproject.toml', 'README.md', 'LICENSE')
IT_HELP = ('What to ask IT support: Python {}.{} or newer with its standard venv and pip modules, usable by your standard account,'
           ' as provided or approved by the company (software centre). Then run the installer again.').format(*MINIMUM)


class LauncherError(Exception):
    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def say(message=''):
    print(message, flush=True)


def kit_version():
    return (KIT_DIR/'VERSION').read_text(encoding='utf-8').strip()


def kit_kind():
    """'zip' for a release ZIP (wheels/ next to the launchers), 'source' for a git clone or a copy of the repository."""
    if list((KIT_DIR/'wheels').glob('ai_kit-*.whl')):
        return 'zip'
    if (KIT_DIR/'pyproject.toml').is_file() and (KIT_DIR/'installer'/'cli.py').is_file():
        return 'source'
    raise LauncherError('This folder is neither a release ZIP of the kit (wheels/ folder) nor a copy of its repository: '
                        'extract the whole ZIP again, then run the installer from the extracted folder.')


def option(argv, name):
    """Value of --name X or --name=X in the arguments, or None."""
    for i, arg in enumerate(argv):
        if arg == name and i+1 < len(argv):
            return argv[i+1]
        if arg.startswith(name+'='):
            return arg.split('=', 1)[1]
    return None


def action_of(argv):
    """The action: the first argument that is not an option or an option's value."""
    takes_value = {'--home', '--profile', '--user', '--team', '--target', '--since', '--json', '--min-sessions', '--min-prompts'}
    skip = False
    for arg in argv:
        if skip:
            skip = False
        elif arg in takes_value:
            skip = True
        elif not arg.startswith('-'):
            return arg
    return None


def environment_python(venv):
    return venv/('Scripts' if os.name == 'nt' else 'bin')/('python.exe' if os.name == 'nt' else 'python')


def clean_env():
    """The environment given to pip and to the kit: no PYTHON* variable that could import foreign code, never a --user install."""
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE', 'VIRTUAL_ENV', '__PYVENV_LAUNCHER__')}
    env['PIP_USER'] = '0'
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['PYTHONUTF8'] = '1'
    return env


def fingerprint(kind):
    """What the private environment was built from: the wheels of a ZIP, or the source files of a clone, and this Python."""
    digest = hashlib.sha256((sys.version+'|'+str(Path(sys.executable).resolve())+'|'+kind+'\n').encode('utf-8'))
    if kind == 'zip':
        files = sorted((KIT_DIR/'wheels').glob('*.whl'))
    else:
        files = []
        for part in SOURCE_PARTS:
            path = KIT_DIR/part
            files += [path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for path in files:
        digest.update(path.relative_to(KIT_DIR).as_posix().encode('utf-8')+b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def process_alive(pid):
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Lock:
    """One installer at a time for a home folder: a second one stops and says so; a lock left by a stopped run is taken over."""
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    owner = json.loads(self.path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    owner = {}
                if process_alive(int(owner.get('pid', 0))):
                    raise LauncherError('Another run of the kit installer is in progress (process '+str(owner.get('pid'))+'): wait for it to'
                                        ' finish, then run this command again.', 4)
                self.path.unlink()
                continue
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump({'pid': os.getpid(), 'started': time.time()}, out)
            return self
        raise LauncherError('Could not take the installer lock '+str(self.path)+': remove it if no installer is running.', 4)

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass


def read_record(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    os.replace(tmp, path)


def check_python():
    if sys.version_info < MINIMUM:
        raise LauncherError('This Python is '+'.'.join(map(str, sys.version_info[:3]))+': the kit needs Python {}.{} or newer. '.format(*MINIMUM)+IT_HELP)
    try:
        import venv  # noqa: F401
        import ensurepip  # noqa: F401
    except ImportError:
        raise LauncherError('This Python has no venv or pip support (on Linux, the python3-venv package is often missing). '+IT_HELP)


def runs(python):
    """The private environment's Python starts and holds the kit and its interface libraries."""
    try:
        return subprocess.run([str(python), '-I', '-c', 'import ai_kit.cli, rich, questionary'], capture_output=True, env=clean_env(),
                              timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def installed_version(python):
    try:
        proc = subprocess.run([str(python), '-I', '-c', 'import importlib.metadata as m; print(m.version("ai-kit"))'],
                              capture_output=True, text=True, env=clean_env(), timeout=120)
        return proc.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def pip(python, args):
    proc = subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--no-input', '--quiet', *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', env=clean_env(), cwd=str(KIT_DIR))
    if proc.returncode != 0:
        tail = '\n'.join((proc.stderr or proc.stdout).strip().splitlines()[-12:])
        raise LauncherError('Installing the kit package failed; the agents were not configured.\n'+tail, 3)


def ensure_runtime(runtime, kind):
    """The private environment, ready for this version of the kit. Rebuilt when it does not run or a previous install stopped."""
    venv, record_file = runtime/'venv', runtime/'install.json'
    python = environment_python(venv)
    record, wanted = read_record(record_file), fingerprint(kind)
    if record.get('status') == 'ready' and record.get('fingerprint') == wanted and runs(python):
        return python, False
    if record.get('status') == 'installing':
        say('A previous installation of the kit runtime did not finish: it is started again from scratch.')
    elif record.get('status') == 'failed':
        say('The previous installation of the kit runtime failed: it is started again from scratch.')
    # Unfinished, failed or not starting: rebuilt from scratch. Ready but older: reused, only the package changes.
    if venv.exists() and (record.get('status') != 'ready' or not runs(python)):
        shutil.rmtree(venv)
    write_record(record_file, {'status': 'installing', 'version': kit_version(), 'kind': kind, 'started': time.time()})
    try:
        if not python.exists():
            say('Creating the kit\'s private Python environment: '+str(venv))
            # In a process of its own, from the runtime folder, without PYTHONPATH: on Python 3.9, ensurepip runs pip without
            # -I, so a json.py in the person's current folder or PYTHONPATH would break it.
            made = subprocess.run([sys.executable, '-I', '-m', 'venv', '--clear', str(venv)], cwd=str(runtime), env=clean_env(),
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if made.returncode != 0 or not python.exists():
                detail = '\n'.join((made.stderr or made.stdout).strip().splitlines()[-6:])
                raise LauncherError('Could not create the private Python environment.\n'+detail+'\n'+IT_HELP, 3)
        if kind == 'zip':
            say('Installing the kit '+kit_version()+' and its libraries from this folder (no download)…')
            pip(python, ['--no-index', '--find-links', str(KIT_DIR/'wheels'), '--force-reinstall', 'ai-kit=='+kit_version()])
        else:
            say('Installing the kit '+kit_version()+' from this folder (pip builds it; libraries from your configured package index)…')
            subprocess.run([str(python), '-I', '-m', 'pip', 'uninstall', '--yes', '--quiet', 'ai-kit'], capture_output=True, env=clean_env())
            pip(python, ['--constraint', str(KIT_DIR/'packaging'/'runtime.txt'), str(KIT_DIR)])
        if not runs(python):
            raise LauncherError('The kit package was installed but does not start in '+str(venv)+'.', 3)
    except BaseException:
        write_record(record_file, {'status': 'failed', 'version': kit_version(), 'kind': kind, 'at': time.time()})
        raise
    write_record(record_file, {'status': 'ready', 'version': installed_version(python), 'kind': kind, 'fingerprint': wanted,
                               'python': sys.executable, 'at': time.time()})
    return python, True


def git(*args):
    return subprocess.run(['git', '-C', str(KIT_DIR), *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          stdin=subprocess.DEVNULL, timeout=300)


def fetch_new_version():
    """update in a git clone: fast-forward only, never over local changes, never a reset, stash or merge. (status, detail)."""
    if not (KIT_DIR/'.git').exists():
        return 'skipped', 'not a git clone'
    if not shutil.which('git'):
        return 'failed', 'git is not installed'
    try:
        if git('diff', '--quiet').returncode != 0 or git('diff', '--cached', '--quiet').returncode != 0:
            return 'refused', 'the kit folder has local changes: nothing was fetched; commit them or set them aside yourself, then update again'
        before = git('rev-parse', '--short', 'HEAD').stdout.strip()
        pulled = git('pull', '--ff-only', '--quiet')
    except (OSError, subprocess.SubprocessError) as exc:
        return 'failed', str(exc)
    if pulled.returncode != 0:
        reason = (pulled.stderr or pulled.stdout).strip().splitlines()
        return 'failed', (reason[-1] if reason else 'git pull --ff-only failed')+' (network, credentials or a diverging history; nothing was changed)'
    after = git('rev-parse', '--short', 'HEAD').stdout.strip()
    return 'ok', ('already the latest version ('+after+')' if before == after else before+' → '+after)


def main(argv):
    try:
        check_python()
        kind = kit_kind()
        remove_runtime = '--remove-runtime' in argv
        args = [a for a in argv if a != '--remove-runtime']
        action = action_of(args)
        home = Path(option(args, '--home') or Path.home()).expanduser().resolve()
        runtime = home/'.ai-kit'/'runtime'
        fetched = None
        with Lock(runtime/'install.lock'):
            if action == 'update' and kind == 'source':
                say('Step 1/3: fetching the new version of the kit (git pull --ff-only)…')
                fetched = fetch_new_version()
                say('  '+{'ok': 'Fetched: ', 'skipped': 'Not fetched: ', 'refused': 'Not fetched: ', 'failed': 'Fetch failed: '}[fetched[0]]+fetched[1])
                say('Step 2/3: kit package in the private environment…')
            elif action == 'update':
                say('Step 1/3: version of this folder: '+kit_version()+' (a newer version comes as a new ZIP: run its installer).')
                say('Step 2/3: kit package in the private environment…')
            python, installed = ensure_runtime(runtime, kind)
            version = installed_version(python)
            if version != kit_version():
                say('The kit folder holds version '+kit_version()+' but the private environment has '+str(version)+'.')
            elif action == 'update':
                say('  Kit package '+str(version)+(' installed.' if installed else ' already installed.'))
            if action == 'update':
                say('Step 3/3: applying the configuration…')
            code = subprocess.call([str(python), '-I', '-m', 'ai_kit', *args], env={**clean_env(), 'AI_KIT_LAUNCHER': '1',
                                   'AI_KIT_SOURCE': kind, 'AI_KIT_SOURCE_DIR': str(KIT_DIR)})
        if fetched and fetched[0] in ('failed', 'refused'):
            say('\nUpdate incomplete: the new version was not fetched ('+fetched[1]+'). '
                + ('The configuration of version '+str(version)+' was reapplied.' if code == 0 else 'The configuration step failed too (see above).'))
            return code or 1
        if action == 'uninstall' and remove_runtime and code == 0 and '--dry-run' not in args:
            # The kit has exited: its environment can be removed without deleting files in use.
            shutil.rmtree(runtime/'venv', ignore_errors=True)
            (runtime/'install.json').unlink(missing_ok=True)
            if runtime.is_dir() and not any(runtime.iterdir()):
                runtime.rmdir()
            say('Kit runtime removed: '+str(runtime/'venv'))
        return code
    except LauncherError as exc:
        say('Error: '+str(exc))
        return exc.code
    except KeyboardInterrupt:
        say('\nOperation cancelled.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
