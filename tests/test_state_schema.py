"""state.json records schema_version; until V2 slice 0 nothing read it. A state written by a newer kit is refused by the commands
that rewrite it (setup, update, uninstall), with nothing changed; reading commands keep working."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from installer.cli import apply, uninstall
from installer.core import STATE_SCHEMA, KitError


class StateSchemaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            apply('general', self.home, False, None, 'gemini')
        return self.home/'.ai-kit/state.json'

    def test_written_schema_is_the_supported_one(self):
        self.assertEqual(json.loads(self.install().read_text(encoding='utf-8'))['schema_version'], STATE_SCHEMA)

    def test_a_state_from_a_newer_kit_is_refused_and_nothing_changes(self):
        state_file = self.install()
        for value in (STATE_SCHEMA + 1, 'two', [2]):
            with self.subTest(value):
                state = json.loads(state_file.read_text(encoding='utf-8'))
                state['schema_version'] = value
                state_file.write_text(json.dumps(state), encoding='utf-8')
                before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(KitError) as caught:
                        apply('general', self.home, False, None, 'gemini')
                    with self.assertRaises(KitError):
                        uninstall(self.home, confirm=lambda summary: True)
                self.assertIn('schema', str(caught.exception))
                self.assertEqual({p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}, before)

    def test_a_state_without_schema_version_is_still_read(self):
        # States written before schema_version existed are migrated as before, not refused.
        state_file = self.install()
        state = json.loads(state_file.read_text(encoding='utf-8'))
        del state['schema_version']
        state_file.write_text(json.dumps(state), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            apply('general', self.home, False, None, 'gemini')
        self.assertEqual(json.loads(state_file.read_text(encoding='utf-8'))['schema_version'], STATE_SCHEMA)


if __name__ == '__main__':
    unittest.main()
