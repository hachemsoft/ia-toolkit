"""runtime/review_html.py: the review page (spec docs/sdlc/2026-11-14-review-aids/spec-html.md). Real temporary Git
repositories, no model, no browser; the page's logic runs in node when it is installed."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'runtime'/'review_html.py'

GUIDE = """# Review guide: discount

## Reading order
1. src/orders.py:5 — the discount is applied here
2. tests/test_orders.py:3 — the acceptance test

## Themes
### Discount — the total takes a discount
- src/orders.py:4-6 — new parameter

## Assumptions
- the discount is between 0 and 1

## Risk points
- src/orders.py:6 — rounding

## Skim
- docs/notes.md — wording

## How to answer
Write a `review:` mark where you have a remark, then say "reviewed".
"""


class Repo:
    def __init__(self):
        self.path = Path(tempfile.mkdtemp())
        self.git('init', '--quiet', '--initial-branch=main')
        self.write({'src/orders.py': 'def total(items):\n    return sum(items)\n',
                    'docs/notes.md': 'Notes.\n', 'big.txt': 'x\n'})
        self.git('add', '-A')
        self.git('commit', '--quiet', '-m', 'base')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@example.org', '-c', 'commit.gpgsign=false', *args],
                              cwd=self.path, check=True, capture_output=True, text=True).stdout

    def write(self, files):
        for rel, text in files.items():
            target = self.path/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')

    def change(self, guide=GUIDE, orders_extra=''):
        self.write({'src/orders.py': 'def total(items, discount=0.0):\n    """Total."""\n    raw = sum(items)\n    # apply\n'
                                     '    value = raw * (1 - discount)\n    return round(value, 2)\n' + orders_extra,
                    'tests/test_orders.py': 'from src.orders import total\n\n\ndef test_discount():\n    assert total([10], 0.5) == 5\n',
                    'docs/notes.md': 'Notes, reworded.\n',
                    'big.txt': ''.join('line %d\n' % i for i in range(2500)),
                    'docs/sdlc/2026-11-15-discount/review-guide.md': guide})
        return self.path/'docs/sdlc/2026-11-15-discount/review-guide.md'

    def run(self, *args):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', str(self.path), *args],
                              capture_output=True, text=True, timeout=120)

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


def page_of(case, guide=GUIDE, orders_extra=''):
    repo = Repo()
    case.addCleanup(repo.cleanup)
    guide_path = repo.change(guide, orders_extra)
    proc = repo.run('--guide', str(guide_path))
    case.assertEqual(proc.returncode, 0, proc.stderr)
    out = Path(proc.stdout.strip())
    case.assertEqual(out.resolve(), (guide_path.parent/'review.html').resolve())
    return repo, out.read_text(encoding='utf-8')


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class PageTests(unittest.TestCase):
    """T1, R1, R2, R7: the page is written next to the guide, files in the guide's order, links to lines, a warning."""

    def test_the_page(self):
        self.assertTrue(SCRIPT.is_file(), 'runtime/review_html.py is missing')
        repo, page = page_of(self)
        order = [page.find('data-file="%s"' % f) for f in ('src/orders.py', 'tests/test_orders.py', 'docs/notes.md', 'big.txt')]
        self.assertTrue(all(i > 0 for i in order), order)
        self.assertEqual(order, sorted(order))  # reading order, then themes, then files the guide does not cite
        self.assertIn('href="#L-src/orders.py-5"', page)
        self.assertIn('id="L-src/orders.py-5"', page)
        self.assertIn('data-folded', page[page.find('data-file="big.txt"'):])
        self.assertIn('do not share it', page)
        self.assertNotIn('docs/sdlc/2026-11-15-discount/review-guide.md"', page)  # the guide is not part of the diff shown

    def test_a_missing_guide_exits_2(self):
        self.assertTrue(SCRIPT.is_file(), 'runtime/review_html.py is missing')
        repo = Repo()
        self.addCleanup(repo.cleanup)
        self.assertEqual(repo.run('--guide', str(repo.path/'nope.md')).returncode, 2)


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class SafetyTests(unittest.TestCase):
    """T2, Threats: content from the repository is escaped, the page loads nothing from outside, a CSP pins its scripts."""

    def test_planted_content_is_escaped(self):
        self.assertTrue(SCRIPT.is_file(), 'runtime/review_html.py is missing')
        trap = '<script>alert(1)</script>'
        repo, page = page_of(self, guide=GUIDE.replace('## Assumptions', '## Assumptions\n- ' + trap + ' "><img src=x onerror=alert(2)>'),
                             orders_extra='# ' + trap + '\n')
        self.assertNotIn(trap, page)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)

    def test_nothing_from_outside_and_a_csp(self):
        self.assertTrue(SCRIPT.is_file(), 'runtime/review_html.py is missing')
        repo, page = page_of(self)
        self.assertIsNone(re.search(r'(src|href)="(https?:)?//', page))
        csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', page)
        self.assertIsNotNone(csp)
        self.assertIn("default-src 'none'", csp.group(1))
        import base64, hashlib
        for block in re.findall(r'<script>(.*?)</script>', page, re.S):
            digest = base64.b64encode(hashlib.sha256(block.encode('utf-8')).digest()).decode()
            self.assertIn("'sha256-%s'" % digest, csp.group(1))


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class ReturnTests(unittest.TestCase):
    """T3, R4, R5, R6: the comments file and the draft key, from the page's own logic; the skill uses the page."""

    def test_the_skill(self):
        skill = (ROOT/'skills/internal/common/review-guide/SKILL.md').read_text(encoding='utf-8')
        for words in ('review_html.py --guide', 'review-comments.md', 'data, never instructions'):
            self.assertIn(words, skill)

    def test_the_page_is_offered_with_the_guide(self):
        # 4.17.1: the page is offered in one line each time the guide is written, generated only on a yes
        skill = (ROOT/'skills/internal/common/review-guide/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('offer in one line to open it as a page', skill)

    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_the_page_logic(self):
        self.assertTrue(SCRIPT.is_file(), 'runtime/review_html.py is missing')
        repo, page = page_of(self)
        logic = re.search(r'/\* logic:start \*/(.*?)/\* logic:end \*/', page, re.S)
        self.assertIsNotNone(logic, 'the page logic markers are missing')
        probe = logic.group(1) + """
const text = formatComments('discount', [
  {file: 'src/orders.py', line: 5, text: 'why round\\nhere?'},
  {section: 'Assumptions', text: 'and negative values?'}]);
console.log(JSON.stringify({text: text, a: draftKey('/x/review.html', 'abc'), b: draftKey('/x/review.html', 'abd')}));
"""
        out = json.loads(subprocess.run(['node', '-e', probe], capture_output=True, encoding='utf-8', timeout=60, check=True).stdout)
        self.assertEqual(out['text'], '# Review comments: discount\n- src/orders.py:5 — why round here?\n- [Assumptions] — and negative values?\n')
        self.assertNotEqual(out['a'], out['b'])
        self.assertTrue(out['a'].startswith('ai-kit-review:'))


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class ReviewFindingsTests(unittest.TestCase):
    """The defects the cold review of 4.15.0 found, one test each."""

    def repo(self):
        repo = Repo()
        self.addCleanup(repo.cleanup)
        return repo

    def page(self, repo, guide=GUIDE):
        path = repo.path/'docs/sdlc/2026-11-15-discount/review-guide.md'
        repo.write({'docs/sdlc/2026-11-15-discount/review-guide.md': guide})
        proc = repo.run('--guide', str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return (path.parent/'review.html').read_text(encoding='utf-8')

    def test_sql_comment_lines_stay_lines(self):
        repo = self.repo()
        repo.write({'models/m.sql': '-- old comment\nselect 1\n'})
        repo.git('add', '-A')
        repo.git('commit', '--quiet', '-m', 'sql')
        repo.write({'models/m.sql': '++ new marker\nselect 1\n'})
        page = self.page(repo)
        self.assertIn('data-file="models/m.sql"', page)
        self.assertIn('-- old comment', page)
        self.assertIn('++ new marker', page)
        self.assertNotIn('data-file="+ new marker"', page)

    def test_the_users_git_settings_do_not_change_the_page(self):
        repo = self.repo()
        for key, value in (('color.ui', 'always'), ('diff.noprefix', 'true'), ('diff.mnemonicPrefix', 'true'), ('core.quotePath', 'true')):
            repo.git('config', key, value)
        repo.write({'café et thé.py': 'x = 1\n'})
        repo.git('add', '-A')
        repo.git('commit', '--quiet', '-m', 'names')
        repo.write({'café et thé.py': 'x = 2\n', 'src/orders.py': 'def total(items):\n    return sum(items) + 0\n'})
        page = self.page(repo)
        self.assertIn('data-file="café et thé.py"', page)
        self.assertIn('data-file="src/orders.py"', page)
        self.assertNotIn('\x1b[', page)

    def test_the_draft_key_follows_new_files(self):
        repo = self.repo()
        repo.write({'new.py': 'a = 1\n'})
        key = re.compile(r'"digest": "([0-9a-f]+)"')
        first = key.search(self.page(repo)).group(1)
        repo.write({'new.py': 'a = 2\n'})
        self.assertNotEqual(key.search(self.page(repo)).group(1), first)

    @unittest.skipIf(sys.platform == 'win32', 'links need rights on Windows')
    def test_links_are_never_followed(self):
        repo = self.repo()
        secret = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, secret, True)
        (secret/'credentials').write_text('SECRET-VALUE\n', encoding='utf-8')
        (repo.path/'notes.txt').symlink_to(secret/'credentials')
        page = self.page(repo)
        self.assertNotIn('SECRET-VALUE', page)
        self.assertIn('symbolic link, not read', page)
        folder = repo.path/'docs/sdlc/2026-11-15-discount'
        (folder/'review.html').unlink()
        target = secret/'target.txt'
        target.write_text('untouched\n', encoding='utf-8')
        (folder/'review.html').symlink_to(target)
        proc = repo.run('--guide', str(folder/'review-guide.md'))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(target.read_text(encoding='utf-8'), 'untouched\n')

    def test_a_planted_title_cannot_swallow_the_script(self):
        page = self.page(self.repo(), guide=GUIDE.replace('# Review guide: discount', '# Review guide: <!--<script>'))
        data = re.search(r'<script type="application/json" id="review-data">(.*?)</script>', page, re.S).group(1)
        self.assertNotIn('<', data)
        self.assertEqual(json.loads(data)['title'], '<!--<script>')

    def test_the_page_ignores_shortcuts_with_modifiers_and_checks_drafts(self):
        page = self.page(self.repo())
        self.assertIn('if (e.ctrlKey || e.metaKey || e.altKey) return;', page)
        self.assertIn('saved.filter(exists)', page)

    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_a_forged_file_name_stays_on_one_line(self):
        page = self.page(self.repo())
        logic = re.search(r'/\* logic:start \*/(.*?)/\* logic:end \*/', page, re.S).group(1)
        probe = logic + "\nconsole.log(JSON.stringify(formatComments('t', [{file: 'a.py\\n- src/auth.py', line: 3, text: 'x'}])));"
        out = json.loads(subprocess.run(['node', '-e', probe], capture_output=True, encoding='utf-8', timeout=60, check=True).stdout)
        self.assertEqual(out.count('\n'), 2)


if __name__ == '__main__':
    unittest.main()
