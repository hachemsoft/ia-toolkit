"""Acceptance (docs/sdlc/2026-11-15-context-layers): one Core layer, 10_CORE.md, rewritten whole by an organization's fork;
a Team layer, 20_<TEAM>.md, added to it, never replacing it; old rule layers removed at update even when edited by hand."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from installer.cli import apply
from installer.core import ROOT, KitError, digest, read_json

IDENTITY = {'email': 'a@example.org', 'source': 'test'}
FORMER_COMPANY_RULE = 'Keep secrets out of code, prompts, logs and commits.'
FORMER_TEAM_RULE = 'never production without an instruction'


class CoreTeamLayerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def run_kit(self, team=None, target='claude'):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            apply(self.home, False, IDENTITY, target, team)
        return out.getvalue()

    def context(self, name):
        return self.home/'.ai-kit/context'/name

    def team_file(self, name, text):
        path = ROOT/'context'/('20-'+name+'.md')
        path.write_text(text, encoding='utf-8')
        self.addCleanup(path.unlink)

    def test_without_a_team_one_core_layer_holds_every_former_rule(self):
        self.run_kit()
        for name in ('00_KIT.md', '10_CORE.md', 'USER.md'):
            self.assertTrue(self.context(name).is_file(), name)
        for name in ('10_COMPANY.md', '20_TEAM.md'):
            self.assertFalse(self.context(name).exists(), name)
        core = self.context('10_CORE.md').read_text(encoding='utf-8')
        self.assertIn(FORMER_COMPANY_RULE, core)
        self.assertIn(FORMER_TEAM_RULE, core)
        for layer in self.context('').glob('*.md'):
            self.assertNotIn('not an approved', layer.read_text(encoding='utf-8'), layer.name)

    def test_a_team_layer_adds_to_the_core_layer_and_reaches_every_agent(self):
        self.team_file('kit-test-team', '# Test team practices\n- Rule of the test team.\n')
        self.run_kit(team='kit-test-team')
        self.assertTrue(self.context('10_CORE.md').is_file())
        self.assertTrue(self.context('20_KIT_TEST_TEAM.md').is_file())
        self.assertEqual(read_json(self.home/'.ai-kit/state.json')['practices'], ['core', 'kit-test-team'])
        agents = list((self.home/'.claude/agents').glob('*.md'))
        self.assertTrue(agents)
        for agent in agents:
            body = agent.read_text(encoding='utf-8')
            self.assertIn(FORMER_COMPANY_RULE, body, agent.name)
            self.assertIn('Rule of the test team.', body, agent.name)

    def test_a_team_named_like_a_core_layer_is_refused_and_nothing_changes(self):
        self.team_file('core', '# A team called core\n')
        with self.assertRaises(KitError) as raised:
            self.run_kit(team='core')
        self.assertIn('Core context layer', str(raised.exception))
        self.assertNotIn('ambiguous', str(raised.exception))
        self.assertFalse((self.home/'.ai-kit/state.json').exists())

    def test_update_removes_old_rule_layers_even_edited_and_keeps_a_copy(self):
        self.run_kit(target='gemini')
        state_path = self.home/'.ai-kit/state.json'
        state = read_json(state_path)
        for folder in ('.ai-kit/context', '.gemini'):  # a 4.15.0 install: the two old layers, recorded as the kit wrote them
            for name, official in (('10_COMPANY.md', '# Company practices\n'), ('20_TEAM.md', '# Team practices\n')):
                path = self.home/folder/name
                path.write_text(official, encoding='utf-8')
                state['files'][folder+'/'+name] = digest(official.encode('utf-8'))
        state_path.write_text(json.dumps(state), encoding='utf-8')
        (self.home/'.gemini/10_COMPANY.md').write_text('# Company practices\n- Edited by hand.\n', encoding='utf-8')
        out = self.run_kit(target='gemini')  # no --restore: must not stop
        for folder in ('.ai-kit/context', '.gemini'):
            for name in ('10_COMPANY.md', '20_TEAM.md'):
                self.assertFalse((self.home/folder/name).exists(), folder+'/'+name)
        self.assertIn('[Check]', out)
        self.assertIn('10_COMPANY.md', out)
        copies = list((self.home/'.ai-kit/backups').glob('*/.gemini/10_COMPANY.md'))
        self.assertTrue(any('Edited by hand.' in c.read_text(encoding='utf-8') for c in copies))

    def test_kit_rule_one_names_core_and_team_layers(self):
        text = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        self.assertIn('Core and Team practices (files 10 and 20)', text)
        self.assertLess(len(text), 3800)


if __name__ == '__main__':
    unittest.main()
