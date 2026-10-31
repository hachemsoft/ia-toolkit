"""uninstall removes what the kit installed and nothing else: the person's files, settings and the CLIs' folders stay,
a managed file edited by hand is kept and named, a dry run changes nothing, automation must confirm explicitly."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import read_json


class UninstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        # The person's own settings before the kit came.
        (self.home/'.gemini').mkdir()
        (self.home/'.gemini/settings.json').write_text(json.dumps({'theme': 'Dark', 'context': {'fileName': ['MINE.md']}}), encoding='utf-8')
        (self.home/'.codex').mkdir()
        (self.home/'.codex/AGENTS.md').write_text('# My Codex notes\n', encoding='utf-8')
        (self.home/'.codex/config.toml').write_text('model = "my-model"\n', encoding='utf-8')
        self.quiet(cli.apply, 'general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'all')
        (self.home/'.gemini/30_USER.md').write_text('My preferences\n', encoding='utf-8')

    def quiet(self, function, *args, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = function(*args, **kwargs)
        self.out = out.getvalue()
        return result

    def kit_files(self):
        return [p for p in self.home.rglob('*') if p.is_file() and '/backups/' not in p.as_posix()]

    def test_removes_only_what_the_kit_installed(self):
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(self.quiet(cli.uninstall, self.home), 0)
        for rel in state['files']:
            self.assertFalse((self.home/rel).exists(), rel)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        settings = read_json(self.home/'.gemini/settings.json')
        self.assertEqual(settings['theme'], 'Dark')
        self.assertIn('MINE.md', settings['context']['fileName'])
        self.assertNotIn('hooks', settings)
        self.assertFalse([n for n in settings['context']['fileName'] if n[:2] in ('00', '10', '20')])
        self.assertEqual((self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'), '# My Codex notes\n')
        self.assertEqual((self.home/'.codex/config.toml').read_text(encoding='utf-8'), 'model = "my-model"\n')
        # Kept: the personal context, overrides.json, the backups; the CLIs' folders are never removed.
        self.assertEqual((self.home/'.gemini/30_USER.md').read_text(encoding='utf-8'), 'My preferences\n')
        self.assertTrue((self.home/'.ai-kit/overrides.json').is_file())
        self.assertTrue(any((self.home/'.ai-kit/backups').iterdir()))
        self.assertTrue((self.home/'.gemini').is_dir() and (self.home/'.codex').is_dir())
        self.assertIn('Backup of every removed or cleaned file', self.out)

    def test_a_managed_file_edited_by_hand_is_kept_and_named(self):
        edited = self.home/'.gemini/skills/tdd/SKILL.md'
        edited.write_text('my own version\n', encoding='utf-8')
        self.quiet(cli.uninstall, self.home)
        self.assertEqual(edited.read_text(encoding='utf-8'), 'my own version\n')
        self.assertIn('.gemini/skills/tdd/SKILL.md: modified since the kit installed it, kept', self.out)

    def test_dry_run_changes_nothing(self):
        before = {p: p.read_bytes() for p in self.kit_files()}
        report = {}
        self.assertEqual(self.quiet(cli.uninstall, self.home, True, None, None, report), 0)
        self.assertEqual({p: p.read_bytes() for p in self.kit_files()}, before)
        self.assertIn('.ai-kit/state.json', report['removed'])
        self.assertIn('Dry run: nothing changed', self.out)

    def test_refused_confirmation_changes_nothing(self):
        before = {p: p.read_bytes() for p in self.kit_files()}
        self.assertEqual(self.quiet(cli.uninstall, self.home, False, lambda summary: False), 1)
        self.assertEqual({p: p.read_bytes() for p in self.kit_files()}, before)

    def test_automation_must_confirm_explicitly(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['uninstall', '--home', str(self.home)]), 2)
        self.assertIn('--yes', err.getvalue())
        self.assertTrue((self.home/'.ai-kit/state.json').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['uninstall', '--yes', '--home', str(self.home)]), 0)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())

    def test_reinstall_after_uninstall_reuses_the_personal_context(self):
        self.quiet(cli.uninstall, self.home)
        self.quiet(cli.apply, 'general', self.home, False, None, 'gemini')
        self.assertEqual((self.home/'.gemini/30_USER.md').read_text(encoding='utf-8'), 'My preferences\n')
        self.quiet(cli.doctor_checks, self.home)
        self.assertFalse([line for line in self.out.splitlines() if line.startswith('[Check] .')], self.out)

    def test_nothing_to_remove_is_said(self):
        self.quiet(cli.uninstall, self.home)
        with self.assertRaises(cli.KitError):
            self.quiet(cli.uninstall, self.home)


if __name__ == '__main__':
    unittest.main()
