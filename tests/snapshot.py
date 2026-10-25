"""Photo de ce que l'installeur produit : chaque fichier installé, ramené à une empreinte, pour une série de scénarios.

Usage : python3 tests/snapshot.py --update   (réécrit tests/golden/install-snapshot.json après un changement voulu)
Le test tests/test_snapshot.py compare l'installation du moment à cette référence : un refactor qui change un seul
octet installé échoue, avec la liste des fichiers touchés.
"""
import contextlib, hashlib, io, json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from installer.cli import apply  # noqa: E402

GOLDEN = ROOT / 'tests' / 'golden' / 'install-snapshot.json'
IDENTITY = {'email': 'test@example.org', 'name': 'Test', 'source': 'option'}
FULL_OVERRIDES = {
    'extra_commands': ['ask', 'handoff'], 'extra_skills': ['prototype'], 'disabled_skills': [],
    'extra_agents': [], 'disabled_agents': [], 'mcp': {}, 'hooks': {'dbt-prod-guard': True, 'protected-paths': True},
    'models': {'fast': 'gemini-2.5-flash', 'deep': 'gemini-2.5-pro'}, 'frictions': 'auto',
    'vertex': {'project': 'demo-project-01', 'location': 'europe-west1'}, 'model': 'gemini-2.5-flash',
}
SCENARIOS = [(p, t, None) for p in ('data-analyst', 'data-developer', 'general') for t in ('gemini', 'both', 'all')] + [('data-developer', 'both', FULL_OVERRIDES), ('data-developer', 'all', FULL_OVERRIDES)] + [('data-developer', 'codex', None), ('data-analyst', 'agy', None)] + [(p, 'all', None) for p in ('java-developer', 'devops', 'architect')]

def scenario_name(profile, target, overrides):
    return profile + '/' + target + ('/overrides' if overrides else '')

def capture(profile, target, overrides=None):
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        if overrides is not None:
            (home / '.ai-kit').mkdir()
            (home / '.ai-kit' / 'overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            apply(profile, home, False, IDENTITY, target)
        out = {}
        for path in sorted(home.rglob('*')):
            rel = path.relative_to(home).as_posix()
            if not path.is_file() or rel.startswith('.ai-kit/backups/') or rel == '.ai-kit/state.json':
                continue
            data = path.read_text(encoding='utf-8', errors='replace')
            for real in sorted({str(home), str(home.resolve())}, key=len, reverse=True):
                data = data.replace(real, '<HOME>')
            data = data.replace(sys.executable, '<PYTHON>')
            out[rel] = hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
        return out

def capture_all():
    return {scenario_name(*s): capture(*s) for s in SCENARIOS}

def diff(reference, current):
    lines = []
    for name in sorted(set(reference) | set(current)):
        a, b = reference.get(name, {}), current.get(name, {})
        for rel in sorted(set(a) | set(b)):
            if a.get(rel) != b.get(rel):
                lines.append(name + ' : ' + rel + (' (nouveau)' if rel not in a else ' (disparu)' if rel not in b else ' (modifié)'))
    return lines

if __name__ == '__main__':
    current = capture_all()
    if '--update' in sys.argv:
        before = json.loads(GOLDEN.read_text(encoding='utf-8')) if GOLDEN.exists() else {}
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        changes = diff(before, current)
        print('Référence réécrite :', sum(len(v) for v in current.values()), 'fichiers,', len(changes), 'changements')
        print('\n'.join(changes[:60]))
    else:
        print('\n'.join(diff(json.loads(GOLDEN.read_text(encoding='utf-8')), current)) or 'identique à la référence')
