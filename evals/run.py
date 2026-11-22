"""Replays evaluation cases against a coding CLI in non-interactive mode and checks deterministic criteria.

Every real run calls the model once per case and is billed by the provider: it needs --confirm-paid-run, and
AI_KIT_NO_LIVE=1 refuses it. Without a model: --dry-run lists the cases and checks their preconditions;
--stand-in PATH replays them against a stand-in executable (tests of the runner itself).

Usage: python3 evals/run.py [--home DIR] [--cases evals/cases] [--only name] [--dry-run] [--report path.json] [--baseline]
       [--cli gemini|agy|codex|claude] [--model NAME] [--approval-mode MODE] [--timeout S] [--retries N] [--confirm-paid-run | --stand-in PATH]
Each case is a JSON file: {"name", "prompt", "cwd" (fixture relative to evals/fixtures, optional), "subdir" (launch subfolder, optional),
"requires": {"commands": [...], "skills": [...], "agents": [...]} (optional, checked against the installed kit), "sandbox": "workspace-write" (optional: the agent may write and run commands in the case's temporary copy),
"git": {"commit": true, "uncommitted": {"path": "text" | null}} (optional: a real repository, the fixture committed, then these files changed; null deletes one),
"expect": {"contains": [...], "not_contains": [...], "regex": [...], "not_regex": [...], "files_absent": [...], "files_present": [...],
"file_regex": {"path": ["pattern"]}, "unchanged": ["path"]},
"turns": [{"between": {"write": {"path": "text"}, "delete": ["path"], "git": [["checkout", "-b", "x"]]}, "new_session": false,
"prompt": "...", "expect": {...}}] (optional: later turns in the same temporary repo; each resumes the previous session
unless new_session; "between" is done by the runner before the turn (one step, or a list of steps applied in order; at the
top level of the case, before the first turn: the state a previous session left, built without a billed turn); claude and codex only, other CLIs SKIP)}.
file_regex and unchanged take paths from the repository's root (no "any depth" match); file_regex reads a file after the turn; unchanged: a file identical to its state when the turn started (before its
"between"): a test written at turn 1 and approved stays as approved at turn 2.
A multi-turn case stops at its first failing turn: the next ones would be billed for nothing.
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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIS = ('gemini', 'agy', 'codex', 'claude')
BETWEEN_GIT = ('checkout', 'switch', 'add', 'commit', 'stash')  # a closed list: the runner only ever touches the temporary copy

def load_cases(folder, only=None):
    cases = []
    for path in sorted(Path(folder).glob('*.json')):
        case = json.loads(path.read_text(encoding='utf-8'))
        if only and case['name'] != only:
            continue
        for key in ('name', 'prompt', 'expect'):
            if key not in case:
                raise SystemExit('Invalid case (' + path.name + '): missing key ' + key)
        problem = turns_problem(case)
        if problem:
            raise SystemExit('Invalid case (' + path.name + '): ' + problem)
        cases.append(case)
    return cases

def relative_path(rel):
    """A path a case gives: relative to the temporary copy, never absolute, never climbing out of it."""
    parts = Path(rel).parts
    return bool(rel) and not Path(rel).is_absolute() and not Path(rel).drive and '..' not in parts


def between_steps(between):
    """A "between" is one step (an object) or several, applied in order (a list)."""
    if not between:
        return []
    return list(between) if isinstance(between, list) else [between]


def turns_problem(case):
    """What is wrong in a case's turns, checked when the cases load (a --dry-run too), never halfway through a paid run."""
    turns = case.get('turns', [])
    if not isinstance(turns, list):
        return 'turns must be a list'
    for named in [case.get('cli')] + [turn.get('cli') for turn in turns if isinstance(turn, dict)]:
        if named is not None and named not in CLIS:
            return 'unknown CLI ' + str(named) + ' (one of ' + ', '.join(CLIS) + ')'
    paths = []
    for number, turn in enumerate([{'prompt': case['prompt'], 'expect': case['expect'], 'between': case.get('between')}] + turns, 1):
        if not isinstance(turn, dict) or not isinstance(turn.get('prompt'), str) or not isinstance(turn.get('expect'), dict):
            return 'turn ' + str(number) + ' needs a prompt (text) and an expect (object)'
        for between in between_steps(turn.get('between')):
            if not isinstance(between, dict) or set(between) - {'write', 'delete', 'git'}:
                return 'turn ' + str(number) + ': between takes write, delete and git only'
            for command in between.get('git', []):
                if not isinstance(command, list) or not command or command[0] not in BETWEEN_GIT:
                    return 'turn ' + str(number) + ': git ' + ' '.join(map(str, command or [])) + ' is not one of ' + ', '.join(BETWEEN_GIT)
            paths += list(between.get('write', {})) + list(between.get('delete', []))
        paths += list(turn['expect'].get('file_regex', {})) + list(turn['expect'].get('unchanged', []))
    for rel in paths:
        if not relative_path(rel):
            return rel + ': a path relative to the case\'s repository, without ..'
    return None


TOKENS = re.compile(r'tokens used\s*\n?\s*(\d[\d\s\u202f\u00a0,.]*)', re.I)


def tokens_used(output):
    """The token count a CLI prints at the end of a run (Codex: "tokens used" on stderr), or None. Read on the whole
    output, before the report cuts it to 12,000 characters."""
    found = TOKENS.findall(output)
    digits = ''.join(ch for ch in found[-1] if ch.isdigit()) if found else ''
    return int(digits) if digits else None


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
    for pattern in expect.get('not_regex', []):
        if re.search(pattern, output, re.I | re.S):
            failures.append('forbidden pattern: ' + pattern)
    return failures

def api_error(returncode, output):
    """Tells an infrastructure failure (API, quota, authentication) apart from a behaviour failure. A "status: NNN" counts
    when it is an error status (4xx, 5xx) and, for a run that succeeded, only on the error stream: a model answer may quote
    one ("returns status: 200")."""
    stderr = output.split('\n--- stderr ---\n', 1)[1] if '\n--- stderr ---\n' in output else ''
    match = re.search(r'status: ([45]\d{2})', output if returncode != 0 else stderr) or re.search(r'(?<![.:\d])\b(401|402|403|429|5\d\d)\b[^\n]*(error|Error|quota|billing|permission)', output)
    if match:
        return 'API ' + match.group(1) + ': model answer unavailable (authentication, quota or billing), not a behaviour failure'
    if 'headless mode cannot prompt for' in output:
        return 'Antigravity gave up on the answer: a tool asked for a permission that print mode cannot grant. Replay the case interactively, or from a machine whose user has already approved read rules in their own agy settings (the kit does not write them)'
    if 'invalid model selection' in output or 'is not recognized as a known model' in output:
        return 'model unknown to this CLI (see the list in the output): choose another --model, not a behaviour failure'
    if 'print timeout after' in output and 'returning partial output' in output:
        return 'Antigravity returned a partial answer before the print timeout: not a behaviour failure'
    if 'Please run /login' in output:
        return 'Claude Code not signed in in this home folder: start claude there once and run /login (for --baseline, a home folder of its own)'
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

RESUMABLE = ('claude', 'codex')  # the CLIs whose print mode the runner resumes; gemini and agy are billed on Vertex


def blocked(case, state, baseline, cli=None):
    """Why a case does not run: its preconditions, or a skeleton from ai-kit new whose prompt is still to write (never sent to a model)."""
    if '<…' in case['prompt']:
        return ['skeleton to complete: its prompt and criteria are placeholders']
    if case.get('cli') and cli is not None and case['cli'] != cli:
        return ['this case starts in one CLI: it runs with --cli ' + case['cli'] + ' only']
    previous = case.get('cli') or cli
    for turn in case.get('turns', []):  # a turn that resumes stays in the CLI before it; another CLI starts afresh
        current = turn.get('cli', previous)
        if cli is not None and current == previous and not turn.get('new_session') and current not in RESUMABLE:
            return ['several turns: resume not supported by the runner for ' + current + ' (claude and codex only)']
        previous = current
    return unmet_preconditions(case, state) if case.get('requires') and not baseline else []

def unmet_preconditions(case, state):
    """What the case needs from the installed kit (commands, skills, agents) and is not there."""
    needs, installed = case.get('requires', {}), state.get('installed', {}) if state else {}
    missing = []
    if not state:
        return ['kit not installed in this home folder']
    for kind in ('commands', 'skills'):
        missing += [kind[:-1] + ' ' + name + ' not installed' for name in needs.get(kind, []) if name not in installed.get(kind, [])]
    agents = installed.get('agents', [])  # recorded with the kit's prefix (ai-kit-<name>)
    missing += ['agent ' + name + ' not installed' for name in needs.get('agents', []) if name not in agents and 'ai-kit-' + name not in agents]
    return missing

def prepare_git(repo, setup):
    """A real repository: the fixture committed, then the "uncommitted" files written over it (null: deleted) and left uncommitted."""
    def git(*args):
        subprocess.run(['git', '-c', 'user.name=Evals', '-c', 'user.email=evals@example.org', *args], cwd=repo, check=True, capture_output=True)
    git('init', '--quiet')
    if setup.get('commit', True):
        git('add', '-A')
        git('commit', '--quiet', '--allow-empty', '-m', 'fixture')
    for rel, text in setup.get('uncommitted', {}).items():
        if text is None:
            (repo / rel).unlink()
            continue
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding='utf-8')

def git_in(repo, *args):
    subprocess.run(['git', '-c', 'user.name=Evals', '-c', 'user.email=evals@example.org', '-C', str(repo), *args], check=True, capture_output=True)


def apply_between(repo, between):
    """What happens outside the agent before a turn: a person edits or deletes a file, switches branch."""
    for rel, text in between.get('write', {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding='utf-8')
    for rel in between.get('delete', []):
        (repo / rel).unlink(missing_ok=True)
    for command in between.get('git', []):  # checked against BETWEEN_GIT when the cases load
        git_in(repo, *command)


def snapshot(repo, paths):
    """The bytes of the files a turn's "unchanged" names, when the turn starts (None: absent)."""
    return {rel: (repo / rel).read_bytes() if (repo / rel).is_file() else None for rel in paths}


def file_failures(repo, expect, before):
    failures = []
    for rel in expect.get('files_absent', []):
        found = files_matching(repo, rel)
        if found:
            failures.append('file created although forbidden: ' + ', '.join(f.relative_to(repo).as_posix() for f in found))
    for rel in expect.get('files_present', []):
        if not files_matching(repo, rel):
            failures.append('expected file not written: ' + rel)
    for rel, patterns in expect.get('file_regex', {}).items():
        path = repo / rel
        text = path.read_text(encoding='utf-8', errors='replace') if path.is_file() else None
        for pattern in patterns:
            if text is None:
                failures.append(rel + ': file missing')
                break
            if not re.search(pattern, text, re.I | re.S):
                failures.append(rel + ': pattern not found: ' + pattern)
    for rel in expect.get('unchanged', []):
        path = repo / rel
        if (path.read_bytes() if path.is_file() else None) != before.get(rel, b''):
            failures.append('changed: ' + rel)
    return failures


def turn_outputs(output):
    """Each turn's output of a multi-turn case, split on the markers run_case writes; None for a case with one turn."""
    if not output.startswith('=== turn '):
        return None
    return ['=== turn ' + chunk for chunk in output.split('=== turn ')[1:]]


def kept_output(output, limit=12000):
    """The output for the report: whole when short, else its start and its end, where the final answer is."""
    if len(output) <= limit:
        return output
    half = limit // 2
    return output[:half] + '\n[... ' + str(len(output) - 2 * half) + ' characters cut ...]\n' + output[-half:]

def cli_command(cli, executable, case, timeout, model, approval_mode, prompt=None, resume=False):
    """The command line of one turn. prompt: a later turn's text (default: the case's); resume: continue the previous
    turn's session (claude -c, codex exec resume --last)."""
    policy = ROOT / 'evals' / 'policy.toml'
    prompt = case['prompt'] if prompt is None else prompt
    if cli == 'codex':
        # Codex: exec in a read-only sandbox; kit commands are called $intent, not /intent. Never --ephemeral: an ephemeral
        # session cannot start a sub-agent ("collab spawn failed: ... no rollout found for thread id"), nor be resumed.
        if prompt.startswith('/'):
            prompt = '$' + prompt[1:]
        if resume:
            # `codex exec resume` takes no --sandbox: the resumed turn runs with the session's settings (not verified).
            return [executable, 'exec', 'resume', '--last', '--skip-git-repo-check'] + (['-m', model] if model else []) + [prompt]
        # A case that must write (the verifier's proof) asks for "sandbox": "workspace-write": the agent writes in the case's
        # temporary copy, never in the person's repository.
        sandbox = 'workspace-write' if case.get('sandbox') == 'workspace-write' else 'read-only'
        return [executable, 'exec', '--skip-git-repo-check', '--color', 'never', '-s', sandbox] + (['-m', model] if model else []) + [prompt]
    if cli == 'claude':
        # Claude Code: print mode, no shell and no file write, as the Gemini policy does; skills and agents stay available.
        # A writable case: file edits are accepted without a prompt (print mode cannot answer one), and of the shell only the
        # test runner and git, for the correction loop (decided 2026-11-21), and the kit's proof script, which the verifier
        # runs to show a test fails without the code (it runs the test command it is given, in the case's temporary copy);
        # Claude Code has no sandbox of its own here.
        locked = (['--permission-mode', 'acceptEdits', '--allowedTools', 'Bash(python -m pytest:*)', 'Bash(python3 -m pytest:*)', 'Bash(git:*)',
                   'Bash(python3 ~/.ai-kit/bin/prove_test.py:*)', 'Bash(python ~/.ai-kit/bin/prove_test.py:*)']
                  if case.get('sandbox') == 'workspace-write' else
                  # A read-only case: no write, and of the shell only git's reads, as Codex's read-only sandbox allows them.
                  ['--disallowedTools', 'Write,Edit,NotebookEdit', '--allowedTools', 'Bash(git status:*)', 'Bash(git branch:*)', 'Bash(git log:*)', 'Bash(git diff:*)'])
        return [executable] + (['-c'] if resume else []) + ['-p', prompt] + locked + (['--model', model] if model else [])
    if cli == 'agy':
        # Antigravity: print mode refuses every shell command the person has not approved word for word, and drops the whole
        # answer; --sandbox ("terminal restrictions") lets them run, the plan mode does not (agy 1.5.14). agy may then write
        # in the case's temporary copy; what the sandbox blocks outside it is not verified.
        return [executable, '-p', prompt, '--sandbox', '--print-timeout', str(timeout) + 's'] + (['--model', model] if model else [])
    # Default approval mode: in non-interactive mode, tools that ask for confirmation (write, shell) are refused, but
    # activate_skill stays available. Plan mode blocks skill activation in Gemini 0.65 and would skew the evaluation.
    return [executable, '--approval-mode', approval_mode, '--skip-trust', '--policy', str(policy)] + (['-m', model] if model else []) + ['-p', prompt]

def run_case(case, home, timeout, model=None, approval_mode='default', cli='gemini', executable=None, stand_in=False):
    """Runs the case's turns in one temporary copy. Returns the output of every turn, the failures of the first turn that
    failed (later turns are not sent) and the number of turns run."""
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
        # "subdir": start the CLI in a subfolder of the fixture (monorepo started from one area).
        run_dir = cwd / case['subdir'] if case.get('subdir') else cwd
        turns = [{'prompt': case['prompt'], 'expect': case['expect'], 'between': case.get('between'), 'new_session': True}] + case.get('turns', [])
        outputs = []
        previous_cli = cli
        for number, turn in enumerate(turns, 1):
            try:
                # unchanged: as the turn found it. A later turn's "between" (a change made outside the agent) comes after the
                # snapshot; the case-level one (turn 1) is the state a previous session left: the snapshot comes after it.
                if number > 1:
                    before = snapshot(cwd, turn['expect'].get('unchanged', []))
                for step in between_steps(turn.get('between')):
                    apply_between(cwd, step)
                if number == 1:
                    before = snapshot(cwd, turn['expect'].get('unchanged', []))
            except (OSError, subprocess.CalledProcessError) as exc:
                outputs.append('=== turn ' + str(number) + ' ===\n')
                return '\n'.join(outputs), ['ERROR turn ' + str(number) + ': the runner could not prepare it (' + str(exc) + '): not a behaviour result'], number
            # A turn may name another CLI (a resume across CLIs): no conversation crosses them, so it starts afresh there.
            turn_cli = turn.get('cli', previous_cli)
            resume = not turn.get('new_session') and turn_cli == previous_cli
            turn_executable = executable if (stand_in or turn_cli == cli) else shutil.which(turn_cli)
            command = cli_command(turn_cli, turn_executable or turn_cli, case, timeout, model, approval_mode, turn['prompt'], resume=resume)
            previous_cli = turn_cli
            output, failures = run_turn(command, run_dir, env, timeout, turn_cli, turn['expect'])
            if failures and not failures[0].startswith('ERROR'):
                failures += file_failures(cwd, turn['expect'], before)
            elif not failures:
                failures = file_failures(cwd, turn['expect'], before)
            outputs.append(output if len(turns) == 1 else '=== turn ' + str(number) + ' ===\n' + output)
            if failures:
                if len(turns) > 1:
                    failures = ['turn ' + str(number) + ': ' + f if not f.startswith('ERROR') else f for f in failures]
                return '\n'.join(outputs), failures, number
        return '\n'.join(outputs), [], len(turns)


def run_turn(command, run_dir, env, timeout, cli, expect):
    """One call to the CLI: its output and what fails in its answer (an ERROR first when the infrastructure failed)."""
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
    return output, check(proc.stdout, expect)

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
    parser.add_argument('--timeout', type=int, default=300, help='per call (each turn of a case), in seconds: limits time, not cost')
    parser.add_argument('--retries', type=int, default=0, help='extra attempts on an infrastructure error, at most ' + str(MAX_RETRIES) + ' (each one is billed)')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--baseline', action='store_true', help='measure the CLI without the kit: --home must hold no kit; every case runs, preconditions ignored; compare with evals/compare.py')
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
    if args.baseline and state_file.is_file():
        print('--baseline measures the CLI without the kit, but the kit is installed in ' + str(args.home) + ': give --home a folder where the CLI is signed in and the kit is not installed.', file=sys.stderr)
        return 2
    if args.dry_run:
        for case in cases:
            unmet = blocked(case, state, args.baseline, args.cli)
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
    meta = {'kit': kit_version, 'installed_kit': state.get('version'), 'cli': args.cli,
            'cli_version': version_of(executable), 'model': args.model or 'CLI default', 'approval_mode': args.approval_mode,
            'retries': args.retries, 'timeout': args.timeout, 'simulated': bool(args.stand_in), 'baseline': args.baseline}
    print('Kit ' + kit_version + ' | ' + args.cli + ' ' + str(meta['cli_version']) + ' | model ' + meta['model'] + (' | stand-in, no model' if args.stand_in else ''))
    results, failed = [], 0
    for case in cases:
        unmet = blocked(case, state, args.baseline, args.cli)
        if unmet:
            print('[SKIP] ' + case['name'] + ' — precondition: ' + '; '.join(unmet))
            results.append({'name': case['name'], 'status': 'SKIP', 'failures': unmet, 'attempts': 0, 'tokens': None, 'turns': 0, 'duration_s': 0.0, 'output': ''})
            continue
        attempts = 0
        started = time.monotonic()
        while True:
            attempts += 1
            output, failures, turns = run_case(case, args.home.resolve(), int(case.get('timeout', args.timeout)), args.model, args.approval_mode, args.cli, executable, bool(args.stand_in))
            infra = bool(failures) and failures[0].startswith('ERROR')
            if not infra or attempts > args.retries:
                break
        status = 'OK' if not failures else ('ERROR' if failures[0].startswith('ERROR') else 'FAIL')
        failed += bool(failures)
        tokens = tokens_used(output)
        duration = round(time.monotonic() - started, 1)
        print('[' + status + '] ' + case['name'] + ('' if not failures else ' — ' + ' ; '.join(failures)) + (' (' + str(attempts) + ' attempts)' if attempts > 1 else '') + (' · ' + str(tokens) + ' tokens' if tokens is not None else ''))
        results.append({'name': case['name'], 'status': status, 'failures': failures, 'attempts': attempts, 'tokens': tokens, 'turns': turns, 'duration_s': duration, 'output': kept_output(output),
                        **({'turns_output': [kept_output(o) for o in turn_outputs(output)]} if turn_outputs(output) else {})})
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
