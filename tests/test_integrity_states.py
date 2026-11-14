"""4.8.1: the integrity check tells three states apart, healthy (silent), drift (a change) and check failed (it could not
check), and an installed check never takes a missing or incomplete state.json for a healthy one."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from installer.core import ROOT

HOOK = ROOT/'runtime'/'hooks'/'integrity.py'
POST = {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash'}


class States(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.hooks = self.home/'.ai-kit'/'hooks'
        self.hooks.mkdir(parents=True)
        self.guard = self.hooks/'shell-guard.py'
        self.guard.write_text('print(1)\n', encoding='utf-8')
        self.installed = self.hooks/'integrity.py'
        shutil.copy(HOOK, self.installed)
        self.files = {'.ai-kit/hooks/shell-guard.py': hashlib.sha256(b'print(1)\n').hexdigest(),
                      '.ai-kit/hooks/integrity.py': hashlib.sha256(HOOK.read_bytes()).hexdigest()}

    def state(self, data):
        (self.home/'.ai-kit'/'state.json').write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')

    def run_hook(self, script=None, payload=POST):
        proc = subprocess.run([sys.executable, '-I', str(script or self.installed)], input=json.dumps(payload), capture_output=True,
                              text=True, encoding='utf-8', env={**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)})
        return json.loads(proc.stdout or '{}')

    def test_p0_an_installed_check_reports_a_missing_or_incomplete_state(self):
        answers = {'missing': self.run_hook()}
        self.state({'version': '4.8.0'})
        answers['no files'] = self.run_hook()
        self.state({'version': '4.8.0', 'files': {'.ai-kit/hooks/shell-guard.py': self.files['.ai-kit/hooks/shell-guard.py']}})
        answers['check not recorded'] = self.run_hook()
        for case, answer in answers.items():
            self.assertIn('state.json', answer.get('systemMessage', ''), case)
            self.assertIn('could not check', answer.get('systemMessage', ''), case)
        self.state({'version': '4.8.0', 'files': self.files})
        self.assertEqual(self.run_hook(), {})  # healthy: silent
        # Never installed: the check run from a kit folder, with no state.json in the home folder, says nothing.
        (self.home/'.ai-kit'/'state.json').unlink()
        self.assertEqual(self.run_hook(HOOK), {})

    def test_p1_a_check_that_cannot_be_made_is_not_reported_as_a_change_nor_kept_silent(self):
        self.state({'version': '4.8.0', 'files': self.files})
        os.chmod(self.guard, 0)
        self.addCleanup(os.chmod, self.guard, 0o644)
        unreadable = self.run_hook()
        self.assertIn('could not check', unreadable.get('systemMessage', ''))
        self.assertIn('shell-guard.py', unreadable.get('systemMessage', ''))
        self.assertNotIn('changed outside the kit', unreadable.get('systemMessage', ''))
        self.assertEqual(self.run_hook(), {})  # said once
        os.chmod(self.guard, 0o644)
        # A shared file to judge while the adapters cannot load (the installed copy, with no kit package on this Python).
        (self.home/'.claude').mkdir()
        (self.home/'.claude'/'settings.json').write_text('{}', encoding='utf-8')
        self.state({'version': '4.8.0', 'files': self.files, 'targets': ['claude'], 'blocks': {'.claude/settings.json': 'x'}, 'hooks': {}})
        shared = self.run_hook()
        self.assertIn('could not check', shared.get('systemMessage', ''))
        self.assertIn('.claude/settings.json', shared.get('systemMessage', ''))


if __name__ == '__main__':
    unittest.main()
