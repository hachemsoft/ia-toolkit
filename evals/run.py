"""Rejoue des cas d'évaluation contre Gemini CLI en mode non interactif et vérifie des critères déterministes.

Usage : python3 evals/run.py [--home DIR] [--cases evals/cases] [--only nom] [--dry-run] [--report chemin.json] [--cli gemini|agy|codex] [--model NOM] [--approval-mode MODE] [--timeout S]
Chaque cas est un JSON : {"name", "prompt", "cwd" (fixture relative à evals/fixtures, optionnel), "subdir" (sous-dossier de lancement, optionnel),
"expect": {"contains": [...], "not_contains": [...], "regex": [...], "files_absent": [...]}}.
Le kit doit être installé dans --home (par défaut le dossier personnel). Non interactif : les écritures sont refusées faute de confirmation.
Code retour 1 si un cas échoue. Aucun appel au modèle en --dry-run.
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
                raise SystemExit('Cas invalide (' + path.name + ') : clé manquante ' + key)
        cases.append(case)
    return cases

def check(output, expect):
    failures = []
    for needle in expect.get('contains', []):
        if needle.lower() not in output.lower():
            failures.append('attendu : ' + needle)
    for needle in expect.get('not_contains', []):
        if needle.lower() in output.lower():
            failures.append('interdit : ' + needle)
    for pattern in expect.get('regex', []):
        if not re.search(pattern, output, re.I | re.S):
            failures.append('motif absent : ' + pattern)
    return failures

def api_error(returncode, output):
    """Distingue une panne d'infrastructure (API, quota, authentification) d'un échec de comportement."""
    match = re.search(r'status: (\d{3})', output) or re.search(r'\b(401|402|403|429|5\d\d)\b[^\n]*(error|Error|quota|billing|permission)', output)
    if match:
        return 'API ' + match.group(1) + ' : réponse du modèle indisponible (authentification, quota ou facturation), pas un échec de comportement'
    if 'headless mode cannot prompt for' in output:
        return 'Antigravity a abandonné la réponse : un outil a demandé une permission impossible en mode print. Rejouer le cas en interactif, ou depuis un poste dont la personne a déjà validé des règles de lecture dans ses propres réglages agy (le kit ne les écrit pas)'
    if 'invalid model selection' in output or 'is not recognized as a known model' in output:
        return 'modèle inconnu de cette CLI (voir la liste dans la sortie) : choisir un autre --model, pas un échec de comportement'
    if 'print timeout after' in output and 'returning partial output' in output:
        return 'Antigravity a rendu une réponse partielle avant la fin du délai de print : pas un échec de comportement'
    if 'Not logged in' in output or 'codex login' in output.lower() and 'error' in output.lower():
        return 'Codex non connecté : lancer codex login'
    if 'usage limit' in output.lower() or "You've hit your usage limit" in output:
        return 'quota Codex atteint : réponse du modèle indisponible, pas un échec de comportement'
    if 'Please set an Auth method' in output:
        return 'authentification Gemini absente dans ce dossier personnel'
    if returncode != 0 and 'critical error' in output:
        return 'Gemini CLI a échoué avant de répondre (code ' + str(returncode) + ')'
    return None

def run_timed(command, timeout, **kwargs):
    """subprocess.run avec délai qui arrête tout le groupe de processus : Gemini CLI se relance lui-même
    (node --max-old-space-size) et le fils survivrait à un simple kill du parent, en orphelin."""
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
            # Mode d'approbation par défaut : en non interactif, les outils qui demandent une confirmation
            # (écriture, shell) sont refusés, mais activate_skill reste disponible. Le mode plan bloque
            # l'activation des skills dans Gemini 0.65 et fausserait l'évaluation.
            policy = ROOT / 'evals' / 'policy.toml'
            if cli == 'codex':
                # Codex : exec en bac à sable lecture seule, session éphémère ; les commandes du kit s'appellent $intent et non /intent.
                prompt = case['prompt']
                if prompt.startswith('/'):
                    prompt = '$' + prompt[1:]
                command = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '-s', 'read-only'] + (['-m', model] if model else []) + [prompt]
            elif cli == 'agy':
                # Antigravity : mode print ; les outils qui demandent une permission sont refusés faute de prompt, les skills s'activent.
                command = ['agy', '-p', case['prompt'], '--print-timeout', str(timeout) + 's'] + (['--model', model] if model else [])
            else:
                command = ['gemini', '--approval-mode', approval_mode, '--skip-trust', '--policy', str(policy)] + (['-m', model] if model else []) + ['-p', case['prompt']]
            # « subdir » : lancer la CLI dans un sous-dossier de la fixture (monorepo lancé depuis une zone).
            run_dir = cwd / case['subdir'] if case.get('subdir') else cwd
            proc = run_timed(command, timeout, cwd=run_dir, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            partial = ((exc.stdout or b'') if isinstance(exc.stdout, bytes) else (exc.stdout or '').encode()).decode('utf-8', 'replace') + '\n' + ((exc.stderr or b'') if isinstance(exc.stderr, bytes) else (exc.stderr or '').encode()).decode('utf-8', 'replace')
            return partial, ['ERREUR délai dépassé après ' + str(timeout) + ' s sans réponse de Gemini (authentification interactive en attente, réseau, ou modèle indisponible)']
        # Les critères portent sur la réponse du modèle (stdout) ; stderr ne sert qu'au diagnostic
        # (avertissements de skills en conflit, erreurs d'API), sinon ses messages polluent les vérifications.
        output = proc.stdout + '\n--- stderr ---\n' + proc.stderr
        error = api_error(proc.returncode, output)
        if error:
            return output, ['ERREUR ' + error]
        failures = check(proc.stdout, case['expect'])
        for rel in case['expect'].get('files_absent', []):
            if (cwd / rel).exists():
                failures.append('fichier créé alors qu’interdit : ' + rel)
        return output, failures

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--cases', type=Path, default=ROOT / 'evals' / 'cases')
    parser.add_argument('--only')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--model', help='modèle Gemini à imposer (par exemple gemini-2.5-flash sur Vertex)')
    parser.add_argument('--approval-mode', default='default', choices=['default', 'plan'], help='plan bloque les skills dans Gemini 0.65 ; default refuse seulement les écritures en non interactif')
    parser.add_argument('--cli', default='gemini', choices=['gemini', 'agy', 'codex'], help='CLI à évaluer : gemini (défaut), agy (Antigravity) ou codex')
    args = parser.parse_args(argv)
    cases = load_cases(args.cases, args.only)
    if not cases:
        print('Aucun cas.')
        return 1
    if args.dry_run:
        for case in cases:
            print(case['name'] + ' : ' + case['prompt'][:80])
        return 0
    if not shutil.which(args.cli):
        print(args.cli + ' absent du PATH.', file=sys.stderr)
        return 2
    results, failed = [], 0
    for case in cases:
        output, failures = run_case(case, args.home.resolve(), int(case.get('timeout', args.timeout)), args.model, args.approval_mode, args.cli)
        status = 'OK' if not failures else ('ERREUR' if failures[0].startswith('ERREUR') else 'ÉCHEC')
        failed += bool(failures)
        print('[' + status + '] ' + case['name'] + ('' if not failures else ' — ' + ' ; '.join(failures)))
        results.append({'name': case['name'], 'status': status, 'failures': failures, 'output': output[:12000]})
    if args.report:
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    errors = sum(1 for r in results if r['status'] == 'ERREUR')
    print(str(len(cases) - failed) + '/' + str(len(cases)) + ' cas réussis' + (', ' + str(errors) + ' en erreur d’infrastructure' if errors else '') + '.')
    if errors == len(cases):
        return 2
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
