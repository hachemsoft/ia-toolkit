"""Runs the test suite with no access to a model: the real CLIs are taken off the PATH and replaced by stand-ins that
record any call and fail. Use it on a workstation where gemini, agy or codex is installed (CI runners have none).

Usage: python3 scripts/offline_tests.py [unittest arguments, for example -k codex or tests.test_hooks]
Exit code: that of the tests, or 3 when a test reached one of the CLIs.
"""
import os
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
    """The current PATH without the folders that hold a real CLI."""
    kept = []
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        if folder and not any(shutil.which(name, path=folder) for name in CLIS):
            kept.append(folder)
    return kept

def main(argv):
    with tempfile.TemporaryDirectory(prefix='ai-kit-offline-') as tmp:
        tools = Path(tmp)/'bin'
        tools.mkdir()
        log = Path(tmp)/'cli-calls.log'
        # The interpreter running this script, git and sh stay reachable when their folder also held a CLI and was dropped.
        kept = clean_path()
        for name, path in (('python3', sys.executable), ('python', sys.executable), ('git', shutil.which('git')), ('sh', shutil.which('sh'))):
            if path and str(Path(path).parent) not in kept:
                target = tools/(name+('.exe' if os.name == 'nt' and not name.endswith('.exe') else ''))
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
