"""Freeze a model-free baseline of the V1 kit before the V2 migration (docs/v2/evals-tests.md, Phase 0).

Reads the repository, installs each profile into a throw-away home (setup calls no model: tests/test_no_model_calls.py),
lists the eval preconditions per CLI with evals/run.py --dry-run, and writes one JSON file. It changes nothing in the
repository except the output file, calls no model and needs no network.

    python3 scripts/baseline_v1.py --out docs/v2/baseline/baseline-v1.json [--offline-output <unittest output file>]
"""
import argparse
import ast
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIS = ('gemini', 'agy', 'codex', 'claude')
ENV = {**os.environ, 'AI_KIT_NO_LIVE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')


def frontmatter(text):
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return match.group(1) if match else ''


def test_counts():
    counts = {}
    for path in sorted((ROOT/'tests').glob('test_*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        counts[path.stem] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test') for n in ast.walk(tree))
    return counts


def offline_result(path):
    if not path:
        return None
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    # The last summary is the suite's: a test may print the output of a nested run before it.
    runs = re.findall(r'^Ran (\d+) tests? in ([\d.]+)s$', text, re.M)
    statuses = re.findall(r'^(OK|FAILED)(?: \((.*)\))?$', text, re.M)
    ran, status = (runs[-1] if runs else None), (statuses[-1] if statuses else None)
    return {'ran': int(ran[0]) if ran else None, 'seconds': float(ran[1]) if ran else None,
            'status': status[0] if status else None, 'detail': status[1] if status else '',
            'no_model_call': 'No call to gemini, agy, codex or claude' in text}


def inventory():
    skills = json.loads((ROOT/'skills/catalog.json').read_text(encoding='utf-8'))
    for name, entry in skills.items():
        skill_md = ROOT/entry.get('path', '')/'SKILL.md'
        if skill_md.is_file():
            text = skill_md.read_text(encoding='utf-8')
            entry['disable_model_invocation'] = 'disable-model-invocation: true' in frontmatter(text)
            entry['sha256'] = digest(skill_md)
    agents = json.loads((ROOT/'agents/catalog.json').read_text(encoding='utf-8'))
    commands = {}
    for path in sorted((ROOT/'commands').glob('*.md')):
        head = frontmatter(path.read_text(encoding='utf-8'))
        fields = dict(re.findall(r'^([a-z_]+):\s*(.*)$', head, re.M))
        commands[path.stem] = {'category': fields.get('category', ''), 'stage': fields.get('stage', ''),
                               'skills': fields.get('skills', ''), 'sha256': digest(path)}
    hooks = json.loads((ROOT/'runtime/hooks/hooks.json').read_text(encoding='utf-8'))
    return {'skills': skills, 'agents': agents, 'commands': commands, 'hooks': hooks}


def verified_cli_versions():
    found = {}
    for path in sorted((ROOT/'installer/adapters').glob('*.py')):
        match = re.search(r"^VERIFIED = '([^']+)'", path.read_text(encoding='utf-8'), re.M)
        if match:
            found[path.stem] = match.group(1)
    return found


def profile_baseline(profile, work):
    home = Path(work)/profile
    setup = run([sys.executable, '-m', 'installer', 'setup', '--profile', profile, '--home', str(home), '--user',
                 'baseline@example.org', '--target', 'all', '--yes', '--plain', '--no-live', '--command-on-path', 'no'])
    result = {'setup_exit': setup.returncode}
    state_file = home/'.ai-kit/state.json'
    if setup.returncode or not state_file.is_file():
        result['setup_error'] = (setup.stderr or setup.stdout)[-2000:]
        return result
    installed = json.loads(state_file.read_text(encoding='utf-8')).get('installed', {})
    result['installed'] = {key: sorted(installed.get(key) or []) for key in ('skills', 'commands', 'agents', 'clis')}
    result['eval_preconditions'] = {}
    for cli in CLIS:
        dry = run([sys.executable, 'evals/run.py', '--dry-run', '--cli', cli, '--home', str(home)])
        skipped = dict(re.findall(r'^(\S+) : .*\[precondition: (.*)\]$', dry.stdout, re.M))
        listed = re.findall(r'^(\S+) : ', dry.stdout, re.M)
        result['eval_preconditions'][cli] = {'exit': dry.returncode, 'runnable': [c for c in listed if c not in skipped],
                                             'skipped': skipped}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', required=True)
    parser.add_argument('--offline-output', help='saved output of scripts/offline_tests.py discover -s tests')
    args = parser.parse_args()
    sha = run(['git', 'rev-parse', 'HEAD']).stdout.strip()
    dirty = sorted(line[3:] for line in run(['git', 'status', '--porcelain']).stdout.splitlines() if line.strip())
    golden = ROOT/'tests/golden/install-snapshot.json'
    snapshot = json.loads(golden.read_text(encoding='utf-8'))
    profiles = sorted(p.stem for p in (ROOT/'profiles').glob('*.toml'))
    with tempfile.TemporaryDirectory(prefix='ai-kit-baseline-') as work:
        per_profile = {p: profile_baseline(p, work) for p in profiles}
    baseline = {
        'schema': 1,
        'engine': {'version': (ROOT/'VERSION').read_text(encoding='utf-8').strip(), 'git_sha': sha,
                   'working_tree_changes': dirty, 'python': platform.python_version(), 'os': sys.platform},
        'offline_tests': {'per_module': test_counts(), 'observed_run': offline_result(args.offline_output)},
        'install_snapshot': {'file': 'tests/golden/install-snapshot.json', 'sha256': digest(golden),
                             'scenarios': len(snapshot), 'files': sum(len(v) for v in snapshot.values())},
        'inventory': inventory(),
        'cli_verified': verified_cli_versions(),
        'profiles': per_profile,
        'eval_cases': {p.stem: digest(p) for p in sorted((ROOT/'evals/cases').glob('*.json'))},
        'eval_fixtures': sorted(p.name for p in (ROOT/'evals/fixtures').iterdir() if p.is_dir()),
        'historical_live_results': sorted(str(p.relative_to(ROOT)) for p in (ROOT/'evals/results').glob('*.json')),
        'note': 'Model-free baseline. Live behaviour is only in historical_live_results (one run per case, model "CLI default").',
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, indent=1, ensure_ascii=False, sort_keys=True)+'\n', encoding='utf-8')
    failed = [p for p, r in per_profile.items() if r.get('setup_exit')]
    print('Baseline written to', out, '| profiles:', len(profiles), '| setup failures:', failed or 'none')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
