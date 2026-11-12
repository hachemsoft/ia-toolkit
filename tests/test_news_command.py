"""AI Kit 3: no `ai-kit news` command and no remote read. The installation copies the active content's CHANGELOG.md and
NEWS.md to ~/.ai-kit/news, the whats-new hook announces them once; doctor says what is waiting. scripts/check_news.py
refuses a NEWS.md the hook could not read."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import ROOT
from personal import write_personal


class NewsInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for patcher in (mock.patch('shutil.which', return_value=None), mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''})):
            patcher.start()
            self.addCleanup(patcher.stop)
        code, out = self.run_kit('init', '--user', 'a@example.org', '--target', 'gemini')
        self.assertEqual(code, 0, out)

    def run_kit(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), mock.patch.object(cli, 'interactive', return_value=False):
            code = cli.main([*args, '--home', str(self.home)])
        return code, out.getvalue()

    def test_news_copies_installed_and_no_news_command(self):
        news = self.home/'.ai-kit/news'
        self.assertEqual((news/'CHANGELOG.md').read_bytes(), (ROOT/'CHANGELOG.md').read_bytes())
        if (ROOT/'NEWS.md').is_file():
            self.assertEqual((news/'NEWS.md').read_bytes(), (ROOT/'NEWS.md').read_bytes())
        self.assertFalse((self.home/'.ai-kit/bin/news.py').exists())
        with self.assertRaises(SystemExit) as raised:
            self.run_kit('news', '--later')
        self.assertEqual(raised.exception.code, 2)  # removed: a usage error
        state = json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))
        self.assertNotIn('news', state)  # no check_remote setting any more

    def test_doctor_reports_what_the_hook_will_announce(self):
        code, out = self.run_kit('doctor')
        self.assertIn('[Info] Session start: ', out)
        self.assertIn('item(s) to announce', out)  # the installed version, not announced yet
        news = self.home/'.ai-kit/news'
        installed = (news/'NEWS.md').read_bytes() if (news/'NEWS.md').is_file() else None
        (news/'NEWS.md').write_text('# News\n', encoding='utf-8')
        version = json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))['version']
        (self.home/'.ai-kit/news.json').write_text(json.dumps({'announced_versions': [version]}), encoding='utf-8')
        code, out = self.run_kit('doctor')
        self.assertIn('[Info] Session start: 1 item(s) to announce', out)  # the /me offer: USER.md is the installer's
        (self.home/'.ai-kit/news.json').write_text(json.dumps({'announced_versions': [version], 'offered_me': True}), encoding='utf-8')
        code, out = self.run_kit('doctor')
        self.assertIn('[Info] Session start: nothing new to announce', out)
        (news/'NEWS.md').write_text('# News\n\n## 2026-11-02 hello : Hello\n\nText.\n\n## 2026-11-02 analysts : Not us\nteams: analysts\n\nText.\n', encoding='utf-8')
        code, out = self.run_kit('doctor')
        self.assertIn('[Info] Session start: 1 item(s) to announce', out)  # the news entry for everyone
        if installed is None:
            (news/'NEWS.md').unlink()
        else:
            (news/'NEWS.md').write_bytes(installed)  # a copy the kit manages: a hand edit stops the next sync
        write_personal(self.home, {'hooks': {'whats-new': False}})
        code, out = self.run_kit('sync', '--offline')
        self.assertEqual(code, 0, out)
        code, out = self.run_kit('doctor')
        self.assertNotIn('Session start:', out)


class NewsFileCheckTests(unittest.TestCase):
    """scripts/check_news.py: the CI refuses a NEWS.md the hook could not read in full."""
    def check(self, text):
        import importlib.util
        spec = importlib.util.spec_from_file_location('check_news', ROOT/'scripts/check_news.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.problems(text)  # 3.0: teams are Team repositories, not a list the check knows

    def test_good_file_and_the_repository_one(self):
        self.assertEqual(self.check('# News\n\nIntro.\n\n## 2026-11-02 hello : Hello\nteams: data\nuntil: 2026-12-31\n\nText.\n'), [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = __import__('subprocess').run([__import__('sys').executable, str(ROOT/'scripts/check_news.py')], capture_output=True, text=True, encoding='utf-8').returncode
        self.assertEqual(code, 0)

    def test_heading_inside_an_entry_is_refused_and_metadata_stops_at_the_blank_line(self):
        found = self.check('## 2026-11-02 cut : Cut\n\nFirst.\n\n# Not a new entry\n\nLost.\n')
        self.assertTrue(any('cut: a "# " heading inside the entry' in f for f in found), found)
        self.assertEqual(self.check('## 2026-11-02 okay : Ok\n\nowner: me is text, not metadata.\n'), [])

    def test_bad_file_names_each_problem(self):
        found = self.check('## no id here\n\n## 2026-13-01 bad-date : X\n\nT.\n\n## 2026-11-02 twice : A\n\nT.\n\n## 2026-11-02 twice : B\nteams: sales\nuntil: soon\nprofiles: nope\nowner: me\n\nT.\n\n## 2026-11-02 empty : Nothing\n')
        for expected in ('line 1: a heading must be', 'invalid date 2026-13-01', 'twice: id used twice', 'unknown metadata "profiles"', 'invalid until date soon', 'unknown metadata "owner"', 'empty: no text'):
            self.assertTrue(any(expected in f for f in found), (expected, found))

if __name__ == '__main__':
    unittest.main()
