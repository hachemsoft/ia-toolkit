"""Gemini CLI's switches over the hooks IT declares (4.17.2, read in google-gemini/gemini-cli: settingsSchema.ts,
hookRegistry.ts, settings.ts): the system file wins on hooksConfig.enabled, but hooksConfig.disabled adds up across levels
and a folder that is not trusted runs none of the settings' hooks. The policy file closes the first, doctor shows the second,
the docs say both."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import doctor, managed
from installer.managed import managed_settings

ROOT = Path(__file__).resolve().parents[1]


class GeminiHookSwitchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_the_policy_file_keeps_the_hooks_system_on(self):
        out = self.root/'out'
        with mock.patch.object(managed, 'core_settings', return_value={}), contextlib.redirect_stdout(io.StringIO()):
            managed_settings(out, False, False, managed_file=self.root/'none.toml')
        gemini = json.loads((out/'gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertIs(gemini.get('hooksConfig', {}).get('enabled'), True)  # the system file is merged last: its value wins

    def test_doctor_shows_a_kit_hook_turned_off(self):
        check = getattr(doctor, 'gemini_hook_switches', None)
        self.assertTrue(callable(check), 'doctor has no check of Gemini CLI hook switches')
        home = self.root/'home'
        (home/'.gemini').mkdir(parents=True)
        (home/'.gemini/settings.json').write_text(json.dumps(
            {'hooksConfig': {'enabled': False, 'disabled': ['ai-kit-integrity', 'my-own-hook']}}), encoding='utf-8')
        seen = []
        check(home, lambda ok, message: seen.append((ok, message)))
        failed = ' '.join(m for ok, m in seen if not ok)
        self.assertIn('ai-kit-integrity', failed)
        self.assertNotIn('my-own-hook', failed)
        self.assertIn('hooksConfig.enabled', failed)
        (home/'.gemini/settings.json').write_text('{}', encoding='utf-8')
        seen.clear()
        check(home, lambda ok, message: seen.append((ok, message)))
        self.assertTrue(all(ok for ok, _ in seen))

    def test_the_limits_are_written(self):
        hooks = (ROOT/'docs/hooks.md').read_text(encoding='utf-8')
        gemini = (ROOT/'docs/cli/gemini.md').read_text(encoding='utf-8')
        for text in (hooks, gemini):
            self.assertIn('hooksConfig.disabled', text)
        self.assertIn('trusted', gemini)


if __name__ == '__main__':
    unittest.main()
