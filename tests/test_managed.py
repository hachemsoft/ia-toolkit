import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import managed
from installer.core import KitError
from installer.managed import managed_settings
from installer.toml_files import parse_toml


class ManagedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)/'out'

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, org=None, hooks_only=False):
        with mock.patch.object(managed, 'organization', return_value=org or {}), contextlib.redirect_stdout(io.StringIO()):
            return managed_settings(self.out, hooks_only)

    def test_default_guardrails_and_denied_paths_for_claude(self):
        self.run_it()
        settings = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        commands = [h['command'] for g in settings['hooks']['PreToolUse'] for h in g['hooks']]
        self.assertEqual(len(commands), 1)
        self.assertIn('protected-paths.py', commands[0])
        self.assertIn('Bash|PowerShell', settings['hooks']['PreToolUse'][0]['matcher'])
        deny = settings['permissions']['deny']
        self.assertIn('Edit(~/.ai-kit/overrides.toml)', deny)
        self.assertFalse(any('30_USER' in d or 'learning' in d for d in deny), '/me and /learn must keep writing')
        self.assertNotIn('allowManagedHooksOnly', settings)

    def test_locked_guardrails_and_hooks_only(self):
        self.run_it({'locked_hooks': ['protected-paths', 'dbt-prod-guard']}, hooks_only=True)
        claude = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        self.assertTrue(claude['allowManagedHooksOnly'])
        self.assertEqual(len(claude['hooks']['PreToolUse']), 2)
        gemini = json.loads((self.out/'gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(h['name'] for g in gemini['hooks']['BeforeTool'] for h in g['hooks']), ['ai-kit-dbt-prod-guard', 'ai-kit-protected-paths'])
        codex = parse_toml((self.out/'codex/requirements.toml').read_text(encoding='utf-8'))
        self.assertNotIn('danger-full-access', codex['allowed_sandbox_modes'])
        self.assertNotIn('never', codex['allowed_approval_policies'])
        self.assertIn('dbt-prod-guard', (self.out/'README.txt').read_text(encoding='utf-8'))

    def test_unknown_guardrail_and_non_empty_folder_refused(self):
        with self.assertRaises(KitError):
            self.run_it({'locked_hooks': ['nope']})
        self.out.mkdir(exist_ok=True)
        (self.out/'x').write_text('keep', encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_it()
        self.assertEqual((self.out/'x').read_text(encoding='utf-8'), 'keep')


if __name__ == '__main__':
    unittest.main()
