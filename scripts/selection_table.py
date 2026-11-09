"""Selection table (2.2: no profiles): what the Core installs by default and what a Team or a person can turn on, inserted in
docs/getting-started.md between two markers.

Usage: python3 scripts/selection_table.py           prints the table
       python3 scripts/selection_table.py --write   rewrites it in the page
A test checks that the page is up to date.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.core import load_commands  # noqa: E402
from installer.resolve import agent_catalog, skill_catalog  # noqa: E402

PAGE = ROOT/'docs/getting-started.md'
START, END = '<!-- selection-table:start -->', '<!-- selection-table:end -->'
WORKFLOW = ('intent', 'spec', 'build', 'test', 'review', 'ship', 'diagnose')


def table():
    commands, skills, agents = load_commands(), skill_catalog(ROOT), agent_catalog(ROOT)
    def names(items, default, fmt, want):
        return ' '.join(fmt(n) for n in items if bool(default(n)) == want)
    rows = ['| | Commands | Skills | Agents |', '| --- | --- | --- | --- |']
    for label, want in (('**Core default** (installed for everyone)', True), ('**Optional** (a Team\'s `[defaults]`, or `extra_*`)', False)):
        rows.append('| '+label+' | '+names([c['name'] for c in commands], lambda n: next(c for c in commands if c['name'] == n).get('default', True), lambda n: '`/'+n+'`', want)
                    + ' | '+names([n for n, e in skills.items() if 'path' in e], lambda n: skills[n].get('default'), lambda n: n, want)
                    + ' | '+names(list(agents), lambda n: agents[n].get('default'), lambda n: n, want)+' |')
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
