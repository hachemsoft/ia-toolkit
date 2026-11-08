"""V2 slice 4: every adapter states what it does with each kit capability (OK, DEGRADED, BLOCKED, with why), and doctor shows
it for the CLIs installed, instead of hiding a degraded behaviour (docs/v2/resources.md)."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from installer import cli
from installer.adapters import ADAPTERS


class CapabilityTests(unittest.TestCase):
    def test_every_adapter_states_the_same_capabilities(self):
        keys = set(ADAPTERS[0].CAPABILITIES)
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.NAME):
                self.assertEqual(set(adapter.CAPABILITIES), keys)
                for name, (level, why) in adapter.CAPABILITIES.items():
                    self.assertIn(level, ('OK', 'DEGRADED', 'BLOCKED'))
                    if level != 'OK':
                        self.assertTrue(why, name+': a degraded or blocked capability says why')

    def test_doctor_shows_them_for_the_installed_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            with contextlib.redirect_stdout(io.StringIO()):
                cli.apply('general', home, False, None, 'gemini')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli.doctor(home)
        self.assertIn('Gemini CLI capabilities: OK: ', out.getvalue())
        self.assertIn('BLOCKED: user-only skills (ignored: the model may activate any skill)', out.getvalue())
        self.assertNotIn('Claude Code capabilities', out.getvalue())


if __name__ == '__main__':
    unittest.main()
