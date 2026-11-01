"""`ai-kit friction`: the same script as /friction (runtime/friction.py, one source), callable from the terminal with
--home, a --list of the last frictions, and --mode to change the frictions setting of overrides.toml and reapply."""
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
from installer.core import ROOT, read_json
from installer.toml_files import read_toml


class FrictionCommandTests(unittest.TestCase):
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

    def lines(self):
        path = self.home/'.ai-kit/frictions.jsonl'
        return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()] if path.is_file() else []

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
        self.assertEqual((first['category'], first['command'], first['cli'], first['source'], first['kit'], first['profile']), ('docs', 'build', 'claude', 'person', cli.kit_version(), 'general'))
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

    def test_mode_shows_then_changes_the_setting_and_reapplies(self):
        code, out = self.run_kit('friction', '--mode')
        self.assertEqual(code, 0, out)
        self.assertIn('Frictions mode: propose', out)
        self.assertRegex(out, r"kit default|organization's defaults")  # the kit's organization.toml sets propose
        kit_text = lambda: (self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8')
        self.assertIn('Offer in one line', kit_text())
        code, out = self.run_kit('friction', '--mode', 'auto', '--yes')
        self.assertEqual(code, 0, out)
        self.assertEqual(read_toml(self.home/'.ai-kit/overrides.toml')['frictions'], 'auto')
        self.assertIn('Log the friction yourself, without asking', kit_text())
        self.assertIn('Frictions mode: auto', out)
        code, out = self.run_kit('friction', '--mode')
        self.assertIn('Frictions mode: auto (your overrides.toml)', out)
        code, out = self.run_kit('friction', '--mode', 'off', '--yes')
        self.assertNotIn('## Frictions', kit_text())
        code, out = self.run_kit('friction', '--mode', 'always')
        self.assertEqual(code, 2)
        self.assertIn('propose, auto or off', out)
        # The other keys and comments of overrides.toml are kept.
        text = (self.home/'.ai-kit/overrides.toml').read_text(encoding='utf-8')
        self.assertIn('#:schema', text)
        self.assertEqual(text.count('frictions ='), 1)

    def test_auto_asks_in_a_terminal(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(cli, 'interactive', return_value=True), mock.patch('builtins.input', return_value='n'):
            code = cli.main(['friction', '--mode', 'auto', '--home', str(self.home), '--plain'])
        self.assertEqual(code, 1)
        self.assertNotIn('frictions', read_toml(self.home/'.ai-kit/overrides.toml'))

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
