"""Table des profils (commandes et agents installés), insérée dans docs/getting-started.md entre deux marqueurs.

Usage : python3 scripts/profile_table.py           affiche la table
        python3 scripts/profile_table.py --write   la réécrit dans la page
Un test vérifie que la page est à jour.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.cli import PROFILE_MENU, allowed_commands, resolve_skills, selected_commands  # noqa: E402
from installer.core import load_commands, read_json  # noqa: E402

PAGE = ROOT/'docs/getting-started.md'
START, END = '<!-- table-profils:début -->', '<!-- table-profils:fin -->'
WORKFLOW = ('intent', 'spec', 'build', 'test', 'review', 'ship', 'diagnose')


def table():
    commands = load_commands()
    catalog = read_json(ROOT/'skills/catalog.json')
    rows = ['| Profil | Étapes du workflow | Autres commandes | Agents |', '| --- | --- | --- | --- |']
    for pid, label in PROFILE_MENU:
        profile = read_json(ROOT/'profiles'/(pid+'.json'))
        resolved = resolve_skills(profile, {}, catalog, log=lambda *a: None)
        skills = resolved[0] if isinstance(resolved, tuple) else resolved
        allowed = allowed_commands(profile.get('commands'), {}, [c['name'] for c in commands])
        names = [c['name'] for c in selected_commands(skills, commands, allowed)]
        steps = ' '.join('`/'+n+'`' for n in WORKFLOW if n in names)
        others = ' '.join('`/'+n+'`' for n in names if n not in WORKFLOW)
        agents = ', '.join(profile['agents'])
        rows.append('| **'+label.split(' : ')[0]+'** (`'+pid+'`) | '+steps+' | '+others+' | '+agents+' |')
    return '\n'.join(rows)


def page_with_table(text):
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    return before+START+'\n'+table()+'\n'+END+after


if __name__ == '__main__':
    if '--write' in sys.argv:
        PAGE.write_text(page_with_table(PAGE.read_text(encoding='utf-8')), encoding='utf-8')
    else:
        print(table())
