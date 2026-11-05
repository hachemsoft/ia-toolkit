"""`ai-kit news`: the script the agent runs on a refused update (runtime/news.py, one source), installed in
~/.ai-kit/bin next to friction.py, callable from the terminal with --home; --later, --list, --check."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import ROOT, read_json


class NewsCommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for patcher in (mock.patch('shutil.which', return_value=None), mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.run_kit('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini')

    def run_kit(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), mock.patch.object(cli, 'interactive', return_value=False):
            code = cli.main([*args, '--home', str(self.home)])
        return code, out.getvalue()

    def test_script_installed_and_actions_run_with_home(self):
        self.assertTrue((self.home/'.ai-kit/bin/news.py').is_file())
        code, out = self.run_kit('news', '--later')
        self.assertEqual(code, 0, out)
        self.assertIn('nothing to decline', out.lower())
        (self.home/'.ai-kit/news.json').write_text(json.dumps({'last_check': {'date': '2026-11-02', 'result': 'ok', 'remote_version': '99.0.0'}}), encoding='utf-8')
        code, out = self.run_kit('news', '--later')
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads((self.home/'.ai-kit/news.json').read_text(encoding='utf-8'))['declined_version'], '99.0.0')
        code, out = self.run_kit('news', '--list')
        self.assertEqual(code, 0, out)
        self.assertIn('99.0.0', out)

    def test_state_records_kit_dir_and_news_setting(self):
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(state.get('kit_dir'), str(ROOT))  # no launcher: the clone the installer runs from
        self.assertEqual(state.get('news'), {'check_remote': True})
        (self.home/'.ai-kit/overrides.toml').write_text('[news]\ncheck_remote = false\n', encoding='utf-8')
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': str(self.home/'kit-folder')}):
            code, out = self.run_kit('update')
        self.assertEqual(code, 0, out)
        self.assertNotIn('unknown', out.lower())
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(state.get('news'), {'check_remote': False})
        self.assertEqual(state.get('kit_dir'), str(self.home/'kit-folder'))  # the launcher names the kit folder
        (self.home/'.ai-kit/overrides.toml').write_text('[news]\ncheck_remote = "no"\n', encoding='utf-8')
        code, out = self.run_kit('update')
        self.assertNotEqual(code, 0)
        self.assertIn('check_remote', out)

    def test_doctor_reports_the_hook_state(self):
        kit = self.home/'kit-folder'
        kit.mkdir()
        (kit/'NEWS.md').write_text('# News\n\n## 2026-11-02 hello : Hello\n\nText.\n\n## 2026-11-02 analysts : Not us\nprofiles: data-analyst\n\nText.\n', encoding='utf-8')
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': str(kit)}):
            self.run_kit('update')
        code, out = self.run_kit('doctor')
        self.assertIn('[OK] Kit folder present for whats-new: '+str(kit), out)
        self.assertIn('[Info] Kit remote not read yet by whats-new', out)
        self.assertIn('[Info] 1 announcement waiting for the next session start: hello', out)
        (self.home/'.ai-kit/news.json').write_text(json.dumps({'announced_news': ['hello'], 'declined_version': '9.0.0', 'last_check': {'date': '2026-11-02', 'result': 'failed', 'detail': 'no route'}}), encoding='utf-8')
        kit.rename(self.home/'moved')
        code, out = self.run_kit('doctor')
        self.assertIn('[Check] Kit folder present for whats-new: '+str(kit)+' (moved or deleted', out)
        self.assertIn('[Info] Kit remote last read by whats-new: 2026-11-02, failed (no route)', out)
        self.assertIn('[Info] Version 9.0.0 declined', out)
        self.assertNotIn('waiting for the next session start', out)
        (self.home/'.ai-kit/overrides.toml').write_text('[hooks]\nwhats-new = false\n', encoding='utf-8')
        self.run_kit('update')
        code, out = self.run_kit('doctor')
        self.assertIn('[Info] whats-new hook off', out)


class NewsFileCheckTests(unittest.TestCase):
    """scripts/check_news.py: the CI refuses a NEWS.md the hook could not read in full."""
    def check(self, text):
        import importlib.util
        spec = importlib.util.spec_from_file_location('check_news', ROOT/'scripts/check_news.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.problems(text, ['general', 'data-analyst'], ['data'])

    def test_good_file_and_the_repository_one(self):
        self.assertEqual(self.check('# News\n\nIntro.\n\n## 2026-11-02 hello : Hello\nprofiles: data-analyst\nteams: data\nuntil: 2026-12-31\n\nText.\n'), [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = __import__('subprocess').run([__import__('sys').executable, str(ROOT/'scripts/check_news.py')], capture_output=True, text=True, encoding='utf-8').returncode
        self.assertEqual(code, 0)

    def test_heading_inside_an_entry_is_refused_and_metadata_stops_at_the_blank_line(self):
        found = self.check('## 2026-11-02 cut : Cut\n\nFirst.\n\n# Not a new entry\n\nLost.\n')
        self.assertTrue(any('cut: a "# " heading inside the entry' in f for f in found), found)
        self.assertEqual(self.check('## 2026-11-02 okay : Ok\n\nowner: me is text, not metadata.\n'), [])

    def test_bad_file_names_each_problem(self):
        found = self.check('## no id here\n\n## 2026-13-01 bad-date : X\n\nT.\n\n## 2026-11-02 twice : A\n\nT.\n\n## 2026-11-02 twice : B\nprofiles: nope\nteams: sales\nuntil: soon\nowner: me\n\nT.\n\n## 2026-11-02 empty : Nothing\n')
        for expected in ('line 1: a heading must be', 'invalid date 2026-13-01', 'twice: id used twice', 'unknown profile nope', 'unknown team sales', 'invalid until date soon', 'unknown metadata "owner"', 'empty: no text'):
            self.assertTrue(any(expected in f for f in found), (expected, found))

if __name__ == '__main__':
    unittest.main()
