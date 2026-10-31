"""Replays evaluation cases against a coding CLI in non-interactive mode and checks deterministic criteria.

Every real run calls the model once per case and is billed by the provider: it needs --confirm-paid-run, and
AI_KIT_NO_LIVE=1 refuses it. Without a model: --dry-run lists the cases and checks their preconditions;
--stand-in PATH replays them against a stand-in executable (tests of the runner itself).

Usage: python3 evals/run.py [--home DIR] [--cases evals/cases] [--only name] [--dry-run] [--report path.json]
       [--cli gemini|agy|codex|claude] [--model NAME] [--approval-mode MODE] [--timeout S] [--retries N] [--confirm-paid-run | --stand-in PATH]
Each case is a JSON file: {"name", "prompt", "cwd" (fixture relative to evals/fixtures, optional), "subdir" (launch subfolder, optional),
"requires": {"profile": ..., "commands": [...], "skills": [...]} (optional, checked against the installed kit),
"git": {"commit": true, "uncommitted": {"path": "text"}} (optional: a real repository, the fixture committed, then these files changed),
"expect": {"contains": [...], "not_contains": [...], "regex": [...], "files_absent": [...], "files_present": [...]}}.
files_absent and files_present are paths relative to the repo; a bare name (intent.md) matches at any depth, where the
commands really write (docs/sdlc/<date>-<slug>/intent.md).
Statuses: OK; FAIL (behaviour); ERROR (infrastructure: CLI exit code, API, quota, timeout); SKIP (precondition not met).
Exit code 1 if a case fails, 2 if none could run.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_cases(folder, only=None):
    cases = []
    for path in sorted(Path(folder).glob('*.json')):
        case = json.loads(path.read_text(encoding='utf-8'))
        if only and case['name'] != only:
            continue
        for key in ('name', 'prompt', 'expect'):
            if key not in case:
                raise SystemExit('Invalid case (' + path.name + '): missing key ' + key)
        cases.append(case)
    return cases

def check(output, expect):
    failures = []
    for needle in expect.get('contains', []):
        if needle.lower() not in output.lower():
            failures.append('expected: ' + needle)
    for needle in expect.get('not_contains', []):
        if needle.lower() in output.lower():
            failures.append('forbidden: ' + needle)
    for pattern in expect.get('regex', []):
        if not re.search(pattern, output, re.I | re.S):
            failures.append('pattern not found: ' + pattern)
    return failures

def api_error(returncode, output):
    """Tells an infrastructure failure (API, quota, authentication) apart from a behaviour failure."""
    match = re.search(r'status: (\d{3})', output) or re.search(r'\b(401|402|403|429|5\d\d)\b[^\n]*(error|Error|quota|billing|permission)', output)
    if match:
        return 'API ' + match.group(1) + ': model answer unavailable (authentication, quota or billing), not a behaviour failure'
    if 'headless mode cannot prompt for' in output:
        return 'Antigravity gave up on the answer: a tool asked for a permission that print mode cannot grant. Replay the case interactively, or from a machine whose user has already approved read rules in their own agy settings (the kit does not write them)'
    if 'invalid model selection' in output or 'is not recognized as a known model' in output:
        return 'model unknown to this CLI (see the list in the output): choose another --model, not a behaviour failure'
    if 'print timeout after' in output and 'returning partial output' in output:
        return 'Antigravity returned a partial answer before the print timeout: not a behaviour failure'
    if 'Not logged in' in output or 'codex login' in output.lower() and 'error' in output.lower():
        return 'Codex not signed in: run codex login'
    if 'usage limit' in output.lower() or "You've hit your usage limit" in output:
        return 'Codex quota reached: model answer unavailable, not a behaviour failure'
    if 'Please set an Auth method' in output:
        return 'no Gemini authentication in this home folder'
    if returncode != 0 and 'critical error' in output:
        return 'Gemini CLI failed before answering (code ' + str(returncode) + ')'
    return None

def run_timed(command, timeout, **kwargs):
    """subprocess.run with a timeout that stops the whole process group: Gemini CLI relaunches itself
    (node --max-old-space-size) and the child would survive a plain kill of the parent, as an orphan."""
    popen_kwargs = dict(kwargs)
    if os.name == 'nt':
        popen_kwargs['creationflags'] = popen_kwargs.get('creationflags', 0) | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs['start_new_session'] = True
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        else:
            import signal
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
        out, err = proc.communicate()
        raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)

def files_matching(repo, rel):
    """Files of the repo matching a criterion: a path with a folder is exact, a bare name matches at any depth."""
    if '/' in rel:
        return [repo / rel] if (repo / rel).exists() else []
    return [path for path in repo.rglob(rel) if '.git' not in path.relative_to(repo).parts]

def unmet_preconditions(case, state):
    """What the case needs from the installed kit (profile, commands, skills) and is not there."""
    needs, installed = case.get('requires', {}), state.get('installed', {}) if state else {}
    missing = []
    if not state:
        return ['kit not installed in this home folder']
    if needs.get('profile') and state.get('profile') != needs['profile']:
        missing.append('profile ' + needs['profile'] + ' (installed: ' + str(state.get('profile')) + ')')
    for kind in ('commands', 'skills'):
        missing += [kind[:-1] + ' ' + name + ' not installed' for name in needs.get(kind, []) if name not in installed.get(kind, [])]
    return missing

def prepare_git(repo, setup):
    """A real repository: the fixture committed, then the "uncommitted" files written over it and left uncommitted."""
    def git(*args):
        subprocess.run(['git', '-c', 'user.name=Evals', '-c', 'user.email=evals@example.org', *args], cwd=repo, check=True, capture_output=True)
    git('init', '--quiet')
    if setup.get('commit', True):
        git('add', '-A')
        git('commit', '--quiet', '--allow-empty', '-m', 'fixture')
    for rel, text in setup.get('uncommitted', {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding='utf-8')

def cli_command(cli, executable, case, timeout, model, approval_mode):
    policy = ROOT / 'evals' / 'policy.toml'
    if cli == 'codex':
        # Codex: exec in a read-only sandbox, ephemeral session; kit commands are called $intent, not /intent.
        prompt = case['prompt']
        if prompt.startswith('/'):
            prompt = '$' + prompt[1:]
        return [executable, 'exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '-s', 'read-only'] + (['-m', model] if model else []) + [prompt]
    if cli == 'claude':
        # Claude Code: print mode, no shell and no file write, as the Gemini policy does; skills and agents stay available.
        return [executable, '-p', case['prompt'], '--disallowedTools', 'Bash,Write,Edit,MultiEdit,NotebookEdit'] + (['--model', model] if model else [])
    if cli == 'agy':
        # Antigravity: print mode; tools that ask for permission are refused for lack of a prompt, skills still activate.
        return [executable, '-p', case['prompt'], '--print-timeout', str(timeout) + 's'] + (['--model', model] if model else [])
    # Default approval mode: in non-interactive mode, tools that ask for confirmation (write, shell) are refused, but
    # activate_skill stays available. Plan mode blocks skill activation in Gemini 0.65 and would skew the evaluation.
    return [executable, '--approval-mode', approval_mode, '--skip-trust', '--policy', str(policy)] + (['-m', model] if model else []) + ['-p', case['prompt']]

def run_case(case, home, timeout, model=None, approval_mode='default', cli='gemini', executable=None):
    fixture = case.get('cwd')
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp) / 'repo'
        if fixture:
            shutil.copytree(ROOT / 'evals' / 'fixtures' / fixture, cwd)
        else:
            cwd.mkdir()
        if case.get('git'):
            prepare_git(cwd, case['git'])
        else:
            (cwd / '.git').mkdir(exist_ok=True)
        env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home)}
        command = cli_command(cli, executable or cli, case, timeout, model, approval_mode)
        # "subdir": start the CLI in a subfolder of the fixture (monorepo started from one area).
        run_dir = cwd / case['subdir'] if case.get('subdir') else cwd
        try:
            proc = run_timed(command, timeout, cwd=run_dir, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            partial = ((exc.stdout or b'') if isinstance(exc.stdout, bytes) else (exc.stdout or '').encode()).decode('utf-8', 'replace') + '\n' + ((exc.stderr or b'') if isinstance(exc.stderr, bytes) else (exc.stderr or '').encode()).decode('utf-8', 'replace')
            return partial, ['ERROR timed out after ' + str(timeout) + ' s without an answer (interactive authentication pending, network, or model unavailable)']
        except OSError as exc:
            return '', ['ERROR cannot start ' + command[0] + ': ' + str(exc)]
        # The criteria apply to the model answer (stdout); stderr only serves diagnosis
        # (conflicting skill warnings, API errors), otherwise its messages pollute the checks.
        output = proc.stdout + '\n--- stderr ---\n' + proc.stderr
        error = api_error(proc.returncode, output)
        if error:
            return output, ['ERROR ' + error]
        if proc.returncode != 0:
            # A CLI that failed did not answer: its output is not judged, whatever it contains.
            return output, ['ERROR ' + cli + ' exited with code ' + str(proc.returncode) + ': execution failure, not a behaviour result']
        failures = check(proc.stdout, case['expect'])
        for rel in case['expect'].get('files_absent', []):
            found = files_matching(cwd, rel)
            if found:
                failures.append('file created although forbidden: ' + ', '.join(f.relative_to(cwd).as_posix() for f in found))
        for rel in case['expect'].get('files_present', []):
            if not files_matching(cwd, rel):
                failures.append('expected file not written: ' + rel)
        return output, failures

def version_of(executable):
    """The CLI's own --version answer: no model call."""
    try:
        proc = run_timed([executable, '--version'], 30, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
        return (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr).strip() else None
    except (OSError, subprocess.SubprocessError):
        return None

MAX_RETRIES = 2

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--cases', type=Path, default=ROOT / 'evals' / 'cases')
    parser.add_argument('--only')
    parser.add_argument('--dry-run', action='store_true', help='list the cases and check their preconditions; no model call')
    parser.add_argument('--timeout', type=int, default=300, help='per case, in seconds: limits time, not cost')
    parser.add_argument('--retries', type=int, default=0, help='extra attempts on an infrastructure error, at most ' + str(MAX_RETRIES) + ' (each one is billed)')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--model', help='model to force (for example gemini-2.5-flash on Vertex)')
    parser.add_argument('--approval-mode', default='default', choices=['default', 'plan'], help='plan blocks skills in Gemini 0.65; default only refuses writes in non-interactive mode')
    parser.add_argument('--cli', default='gemini', choices=['gemini', 'agy', 'codex', 'claude'], help='CLI to evaluate: gemini (default), agy (Antigravity), codex or claude (Claude Code)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--confirm-paid-run', action='store_true', help='required for a real run: each case calls the model and is billed')
    mode.add_argument('--stand-in', type=Path, help='executable that replaces the CLI (tests of the runner, no model)')
    args = parser.parse_args(argv)
    if not 0 <= args.retries <= MAX_RETRIES:
        parser.error('--retries must be between 0 and ' + str(MAX_RETRIES) + '.')
    cases = load_cases(args.cases, args.only)
    if not cases:
        print('No case.')
        return 1
    state_file = args.home.resolve() / '.ai-kit' / 'state.json'
    state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.is_file() else {}
    if args.dry_run:
        for case in cases:
            unmet = unmet_preconditions(case, state) if case.get('requires') else []
            print(case['name'] + ' : ' + case['prompt'][:80] + (' [precondition: ' + '; '.join(unmet) + ']' if unmet else ''))
        print('Dry run: no model called.')
        return 0
    if not args.stand_in:
        if os.environ.get('AI_KIT_NO_LIVE') == '1':
            print('Real run refused: AI_KIT_NO_LIVE=1 is set.', file=sys.stderr)
            return 2
        if not args.confirm_paid_run:
            print('A real run calls the model ' + str(len(cases)) + ' time(s) or more and is billed by your provider.\n'
                  'Add --confirm-paid-run to run it, --dry-run to check the cases, or --stand-in to test the runner.', file=sys.stderr)
            return 2
    executable = str(args.stand_in.resolve()) if args.stand_in else shutil.which(args.cli)
    if not executable or not Path(executable).exists():
        print(args.cli + ' not on the PATH.' if not args.stand_in else 'Stand-in not found: ' + str(args.stand_in), file=sys.stderr)
        return 2
    kit_version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    meta = {'kit': kit_version, 'installed_kit': state.get('version'), 'profile': state.get('profile'), 'cli': args.cli,
            'cli_version': version_of(executable), 'model': args.model or 'CLI default', 'approval_mode': args.approval_mode,
            'retries': args.retries, 'timeout': args.timeout, 'simulated': bool(args.stand_in)}
    print('Kit ' + kit_version + ' | ' + args.cli + ' ' + str(meta['cli_version']) + ' | model ' + meta['model'] + (' | stand-in, no model' if args.stand_in else ''))
    results, failed = [], 0
    for case in cases:
        unmet = unmet_preconditions(case, state) if case.get('requires') else []
        if unmet:
            print('[SKIP] ' + case['name'] + ' — precondition: ' + '; '.join(unmet))
            results.append({'name': case['name'], 'status': 'SKIP', 'failures': unmet, 'attempts': 0, 'output': ''})
            continue
        attempts = 0
        while True:
            attempts += 1
            output, failures = run_case(case, args.home.resolve(), int(case.get('timeout', args.timeout)), args.model, args.approval_mode, args.cli, executable)
            infra = bool(failures) and failures[0].startswith('ERROR')
            if not infra or attempts > args.retries:
                break
        status = 'OK' if not failures else ('ERROR' if failures[0].startswith('ERROR') else 'FAIL')
        failed += bool(failures)
        print('[' + status + '] ' + case['name'] + ('' if not failures else ' — ' + ' ; '.join(failures)) + (' (' + str(attempts) + ' attempts)' if attempts > 1 else ''))
        results.append({'name': case['name'], 'status': status, 'failures': failures, 'attempts': attempts, 'output': output[:12000]})
    if args.report:
        args.report.write_text(json.dumps({'meta': meta, 'results': results}, ensure_ascii=False, indent=2), encoding='utf-8')
    ran = [r for r in results if r['status'] != 'SKIP']
    errors = sum(1 for r in ran if r['status'] == 'ERROR')
    print(str(sum(1 for r in ran if r['status'] == 'OK')) + '/' + str(len(ran)) + ' cases passed' + (', ' + str(errors) + ' with an infrastructure error' if errors else '')
          + (', ' + str(len(results) - len(ran)) + ' skipped (precondition)' if len(ran) != len(results) else '') + '.')
    if not ran or errors == len(ran):
        return 2
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
