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


if __name__ == '__main__':
    unittest.main()
