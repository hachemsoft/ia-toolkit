"""V2 slice 9 (ADR 0018, NR-MIG-01 to 03): an installation made with a profile (V1, 2.0, 2.1) keeps everything it had. What
the Core default does not give is carried over as plain personal lines, commented, once; the MCP servers the profile turned on
stay on; the person is told. After: installed = what V1 installed + the Core default."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from installer import cli
from installer.settings import core_selection
from installer.toml_files import read_toml
from v1_profiles import PROFILES


class MigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.kit = self.home/'.ai-kit'

    def v1_installation(self, role):
        """A home as a profile installation left it: installed with that profile's resources, state.json naming the profile."""
        profile = PROFILES[role]
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'gemini', choices={'extra_skills': profile['skills'], 'extra_agents': profile['agents']})
        state = json.loads((self.kit/'state.json').read_text(encoding='utf-8'))
        before = dict(state['installed'])
        state['profile'] = role
        (self.kit/'state.json').write_text(json.dumps(state), encoding='utf-8')
        (self.kit/'overrides.toml').write_text('# mine\nfrictions = "off"\n', encoding='utf-8')  # the person's own file, no extra lines
        return before

    def update(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            notices = cli.apply('general', self.home, False, None, 'gemini')
        return notices, out.getvalue()

    def test_nothing_is_lost_and_the_lines_are_said(self):
        before = self.v1_installation('data-analyst')
        notices, _ = self.update()
        state = json.loads((self.kit/'state.json').read_text(encoding='utf-8'))
        core = core_selection()
        self.assertEqual(state['profile'], 'core')
        self.assertTrue(set(before['skills']) | set(core['skills']) <= set(state['installed']['skills']))
        self.assertTrue(set(before['agents']) <= set(state['installed']['agents']))
        text = (self.kit/'overrides.toml').read_text(encoding='utf-8')
        self.assertIn('# mine', text)
        self.assertIn('# carried over from profile data-analyst on ', text)
        mine = read_toml(self.kit/'overrides.toml')
        self.assertEqual(mine['frictions'], 'off')
        self.assertIn('sql-review', mine['extra_skills'])
        self.assertNotIn('tdd', mine['extra_skills'])  # a Core default is not carried
        self.assertIn('sql-reviewer', mine['extra_agents'])
        self.assertTrue(any('AI Kit 3 has no profiles' in n and 'sql-review' in n for n in notices), notices)

    def test_a_second_update_carries_nothing_more(self):
        self.v1_installation('data-developer')
        self.update()
        text = (self.kit/'overrides.toml').read_text(encoding='utf-8')
        notices, _ = self.update()
        self.assertEqual((self.kit/'overrides.toml').read_text(encoding='utf-8'), text)
        self.assertFalse([n for n in notices if 'no profiles' in n])

    def test_a_resource_the_person_had_turned_off_stays_off(self):
        self.v1_installation('data-analyst')
        (self.kit/'overrides.toml').write_text('disabled_skills = ["sql-review"]\n', encoding='utf-8')
        self.update()
        self.assertNotIn('sql-review', read_toml(self.kit/'overrides.toml').get('extra_skills', []))
        self.assertNotIn('sql-review', json.loads((self.kit/'state.json').read_text(encoding='utf-8'))['installed']['skills'])

    def test_a_general_installation_carries_nothing(self):
        self.v1_installation('general')
        notices, _ = self.update()
        self.assertNotIn('extra_skills', read_toml(self.kit/'overrides.toml'))
        self.assertFalse([n for n in notices if 'no profiles' in n])


if __name__ == '__main__':
    unittest.main()
