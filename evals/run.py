"""Replays evaluation cases against Gemini CLI in non-interactive mode and checks deterministic criteria.

Usage: python3 evals/run.py [--home DIR] [--cases evals/cases] [--only name] [--dry-run] [--report path.json] [--cli gemini|agy|codex] [--model NAME] [--approval-mode MODE] [--timeout S]
Each case is a JSON file: {"name", "prompt", "cwd" (fixture relative to evals/fixtures, optional), "subdir" (launch subfolder, optional),
"expect": {"contains": [...], "not_contains": [...], "regex": [...], "files_absent": [...]}}.
The kit must be installed in --home (the home folder by default). Non-interactive: writes are refused for lack of confirmation.
Exit code 1 if a case fails. No call to the model with --dry-run.
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

def run_case(case, home, timeout, model=None, approval_mode='default', cli='gemini'):
    fixture = case.get('cwd')
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp) / 'repo'
        if fixture:
            shutil.copytree(ROOT / 'evals' / 'fixtures' / fixture, cwd)
        else:
            cwd.mkdir()
        (cwd / '.git').mkdir(exist_ok=True)
        env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home)}
        try:
            # Default approval mode: in non-interactive mode, tools that ask for confirmation
            # (write, shell) are refused, but activate_skill stays available. Plan mode blocks
            # skill activation in Gemini 0.65 and would skew the evaluation.
            policy = ROOT / 'evals' / 'policy.toml'
            if cli == 'codex':
                # Codex: exec in a read-only sandbox, ephemeral session; kit commands are called $intent, not /intent.
                prompt = case['prompt']
                if prompt.startswith('/'):
                    prompt = '$' + prompt[1:]
                command = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '-s', 'read-only'] + (['-m', model] if model else []) + [prompt]
            elif cli == 'agy':
                # Antigravity: print mode; tools that ask for permission are refused for lack of a prompt, skills still activate.
                command = ['agy', '-p', case['prompt'], '--print-timeout', str(timeout) + 's'] + (['--model', model] if model else [])
            else:
                command = ['gemini', '--approval-mode', approval_mode, '--skip-trust', '--policy', str(policy)] + (['-m', model] if model else []) + ['-p', case['prompt']]
            # "subdir": start the CLI in a subfolder of the fixture (monorepo started from one area).
            run_dir = cwd / case['subdir'] if case.get('subdir') else cwd
            proc = run_timed(command, timeout, cwd=run_dir, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            partial = ((exc.stdout or b'') if isinstance(exc.stdout, bytes) else (exc.stdout or '').encode()).decode('utf-8', 'replace') + '\n' + ((exc.stderr or b'') if isinstance(exc.stderr, bytes) else (exc.stderr or '').encode()).decode('utf-8', 'replace')
            return partial, ['ERROR timed out after ' + str(timeout) + ' s without an answer from Gemini (interactive authentication pending, network, or model unavailable)']
        # The criteria apply to the model answer (stdout); stderr only serves diagnosis
        # (conflicting skill warnings, API errors), otherwise its messages pollute the checks.
        output = proc.stdout + '\n--- stderr ---\n' + proc.stderr
        error = api_error(proc.returncode, output)
        if error:
            return output, ['ERROR ' + error]
        failures = check(proc.stdout, case['expect'])
        for rel in case['expect'].get('files_absent', []):
            if (cwd / rel).exists():
                failures.append('file created although forbidden: ' + rel)
        return output, failures

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--cases', type=Path, default=ROOT / 'evals' / 'cases')
    parser.add_argument('--only')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--model', help='Gemini model to force (for example gemini-2.5-flash on Vertex)')
    parser.add_argument('--approval-mode', default='default', choices=['default', 'plan'], help='plan blocks skills in Gemini 0.65; default only refuses writes in non-interactive mode')
    parser.add_argument('--cli', default='gemini', choices=['gemini', 'agy', 'codex'], help='CLI to evaluate: gemini (default), agy (Antigravity) or codex')
    args = parser.parse_args(argv)
    cases = load_cases(args.cases, args.only)
    if not cases:
        print('No case.')
        return 1
    if args.dry_run:
        for case in cases:
            print(case['name'] + ' : ' + case['prompt'][:80])
        return 0
    if not shutil.which(args.cli):
        print(args.cli + ' not on the PATH.', file=sys.stderr)
        return 2
    results, failed = [], 0
    for case in cases:
        output, failures = run_case(case, args.home.resolve(), int(case.get('timeout', args.timeout)), args.model, args.approval_mode, args.cli)
        status = 'OK' if not failures else ('ERROR' if failures[0].startswith('ERROR') else 'FAIL')
        failed += bool(failures)
        print('[' + status + '] ' + case['name'] + ('' if not failures else ' — ' + ' ; '.join(failures)))
        results.append({'name': case['name'], 'status': status, 'failures': failures, 'output': output[:12000]})
    if args.report:
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    print(str(len(cases) - failed) + '/' + str(len(cases)) + ' cases passed' + (', ' + str(errors) + ' with an infrastructure error' if errors else '') + '.')
    if errors == len(cases):
        return 2
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
