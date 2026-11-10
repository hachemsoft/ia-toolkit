"""`ai-kit friction`: the same script as /friction (runtime/friction.py, one source), callable from the terminal with
--home, a --list of the last frictions; how the agent captures them is frictions.capture in aikit.toml (--mode is gone)."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, core
from installer.core import ROOT
from personal import write_personal


class FrictionCommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for patcher in (mock.patch('shutil.which', return_value=None), mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.run_kit('init', '--user', 'a@example.org', '--target', 'gemini')

    def run_kit(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), mock.patch.object(cli, 'interactive', return_value=False):
            code = cli.main([*args, '--home', str(self.home)])
        return code, out.getvalue()

    def lines(self):
        path = self.home/'.ai-kit/frictions.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.is_file() else []

    def test_logs_like_the_script_and_lists(self):
        code, out = self.run_kit('friction', '--category', 'docs', '--command', '/build', '--cli', 'claude', '--text', 'The plan step is too long')
        self.assertEqual(code, 0, out)
        self.assertIn('Friction ', out)
        self.assertIn('nothing is sent', out)
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        proc = subprocess.run([sys.executable, '-I', str(self.home/'.ai-kit/bin/friction.py'), '--category', 'docs', '--command', '/build', '--cli', 'claude', '--text', 'Same thing from the agent'],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        first, second = self.lines()
        self.assertEqual(set(first), set(second))  # the very same format: one implementation
        self.assertEqual((first['category'], first['command'], first['cli'], first['source'], first['kit'], first.get('profile')), ('docs', 'build', 'claude', 'person', cli.kit_version(), None))
        self.assertEqual(first['text'], 'The plan step is too long')
        code, out = self.run_kit('friction', '--list')
        self.assertEqual(code, 0, out)
        self.assertIn(first['id'], out)
        self.assertIn('The plan step is too long', out)
        self.assertIn('/build', out)
        self.assertLess(out.index('The plan step'), out.index('Same thing'))  # oldest first, the last ones
        code, out = self.run_kit('friction', '--list', '1')
        self.assertNotIn('The plan step', out)
        self.assertIn('Same thing', out)

    def test_bad_input_and_a_secret(self):
        code, out = self.run_kit('friction', '--category', 'nope', '--text', 'x')
        self.assertEqual(code, 2)
        code, out = self.run_kit('friction', '--category', 'tool', '--text', 'token ghp_'+'a'*36+' leaked')
        self.assertEqual(code, 0, out)
        self.assertIn('[redacted]', self.lines()[-1]['text'])
        (self.home/'.ai-kit/frictions.jsonl').unlink()
        code, out = self.run_kit('friction', '--list')
        self.assertEqual(code, 0)
        self.assertIn('No friction logged', out)

    def test_capture_setting_of_aikit_toml_changes_the_rule(self):
        kit_text = lambda: (self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8')
        self.assertIn('Offer in one line', kit_text())  # propose: the default
        write_personal(self.home, {'frictions': 'auto'})
        code, out = self.run_kit('init')
        self.assertEqual(code, 0, out)
        self.assertIn('Log the friction yourself, without asking', kit_text())
        write_personal(self.home, {'frictions': 'off'})
        self.assertEqual(self.run_kit('init')[0], 0)
        self.assertNotIn('## Frictions', kit_text())
        (self.home/'.ai-kit/aikit.toml').write_text('schema = 1\n[frictions]\ncapture = "always"\n', encoding='utf-8')
        code, out = self.run_kit('init')
        self.assertEqual(code, 1)
        self.assertIn('propose, auto, off', out)
        code, out = self.run_kit('friction', '--mode', 'auto')
        self.assertEqual(code, 2)  # --mode is gone: the script refuses an unknown option

    def test_one_implementation_for_the_secret_filter_and_the_ids(self):
        friction = core.friction_module()
        self.assertIs(core.SECRET, friction.SECRET)
        self.assertIs(core.friction_id, friction.friction_id)
        self.assertEqual(friction.__file__, str(ROOT/'runtime/friction.py'))
        core.record_auto_friction(self.home, 'HTTP 407: proxy wants a sign-in', cli='gemini')
        entry = self.lines()[-1]
        self.assertEqual((entry['category'], entry['command'], entry['source'], entry['cli']), ('auth', 'doctor', 'doctor', 'gemini'))
        self.assertEqual(entry['kit'], cli.kit_version())
        self.assertEqual(entry['id'], friction.friction_id(entry['ts'], entry['text']))


if __name__ == '__main__':
    unittest.main()
