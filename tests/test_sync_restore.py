"""4.9.1: `ai-kit sync --offline --restore` puts back what the integrity check reports: the kit's files and its part of the
files it shares with a CLI, the edited copy kept in ~/.ai-kit/backups/; without --restore, sync still refuses (spec in
docs/sdlc/2026-11-14-sync-restore)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from installer.core import ROOT


class Restore(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.run_cli('init', '--target', 'all', '--user', 'a@example.org')

    def run_cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, '-m', 'installer', *args, '--home', str(self.home)], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'AI_KIT_NO_LIVE': '1'})
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc

    def backups_holding(self, text):
        return [p for p in (self.home/'.ai-kit'/'backups').rglob('*') if p.is_file() and text in p.read_text(encoding='utf-8', errors='replace')]

    def test_an_edited_kit_file_is_put_back_with_restore_only(self):
        skill = self.home/'.claude'/'skills'/'ai-kit-grilling'/'SKILL.md'
        original = skill.read_bytes()
        skill.write_bytes(original + b'\nmy edit 7f3\n')
        self.run_cli('sync', '--offline', code=1)  # unchanged: sync still refuses an edited kit file
        self.run_cli('sync', '--offline', '--restore')
        self.assertEqual(skill.read_bytes(), original)
        self.assertTrue(self.backups_holding('my edit 7f3'))  # the edited copy is kept

    def test_the_kit_part_of_a_shared_file_is_put_back_and_the_rest_stays(self):
        settings = self.home/'.claude'/'settings.json'
        data = json.loads(settings.read_text(encoding='utf-8'))
        kit_events = sorted(data['hooks'])
        data['hooks'].pop('PostToolUse')
        data['permissions'] = {'allow': ['Bash(ls)']}
        settings.write_text(json.dumps(data, indent=2), encoding='utf-8')
        claude_md = self.home/'.claude'/'CLAUDE.md'
        imports = claude_md.read_text(encoding='utf-8').splitlines()
        user_import = next(line for line in imports if line.startswith('@') and line.endswith('context/USER.md'))  # absolute path
        claude_md.write_text('\n'.join(line for line in imports if line != user_import) + '\n\nMine, outside the block.\n', encoding='utf-8')
        restored = self.run_cli('sync', '--offline', '--restore')
        self.assertIn('[Check] a kit hook in ~/.claude/settings.json', restored.stdout)  # it says what it put back
        after = json.loads(settings.read_text(encoding='utf-8'))
        self.assertEqual(sorted(after['hooks']), kit_events)
        self.assertEqual(after['permissions'], {'allow': ['Bash(ls)']})  # the person's own setting stays
        text = claude_md.read_text(encoding='utf-8')
        self.assertIn(user_import, text.splitlines())
        self.assertIn('Mine, outside the block.', text)

    def test_the_integrity_report_gives_the_command_that_works(self):
        skill = self.home/'.claude'/'skills'/'ai-kit-grilling'/'SKILL.md'
        skill.write_bytes(skill.read_bytes() + b'\nedit\n')
        hook = self.home/'.ai-kit'/'hooks'/'integrity.py'
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        out = json.loads(subprocess.run([sys.executable, '-I', str(hook)], input='{"hook_event_name": "PostToolUse"}', capture_output=True,
                                        text=True, encoding='utf-8', env=env).stdout or '{}')
        self.assertIn('ai-kit sync --offline --restore', out.get('systemMessage', ''))
        # The kit folder's git settings are not sync's: the report says to look at its remotes instead.
        state_path = self.home/'.ai-kit'/'state.json'
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if 'kit_git' in state:
            state['kit_git'] = {'remote.origin.url': hashlib.sha256(b'https://example.org/other.git').hexdigest()}
            state_path.write_text(json.dumps(state), encoding='utf-8')
            message = json.loads(subprocess.run([sys.executable, '-I', str(hook)], input='{"hook_event_name": "PostToolUse"}',
                                                capture_output=True, text=True, encoding='utf-8', env=env).stdout or '{}').get('systemMessage', '')
            self.assertIn('remote', message)
            self.assertIn('git -C', message)


if __name__ == '__main__':
    unittest.main()
