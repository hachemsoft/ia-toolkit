"""The parallel agents setting: off by default; on, the kit context carries the rule that says when to give parts of a
task to sub-agents at the same time, and how the ones that write stay out of each other's way."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import config
from installer.core import KitError
from installer.settings import unknown_keys
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402

HEADING = '## Parallel agents'


class ParallelAgentsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()

    def install(self, settings=None, target='gemini'):
        if settings is not None:
            write_personal(self.home, settings)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            apply_as('data-analyst', self.home, False, None, target)
        return out.getvalue()

    def context(self):
        return (self.home/'.ai-kit'/'context'/'00_KIT.md').read_text(encoding='utf-8')

    def test_off_by_default(self):
        self.install()
        self.assertNotIn(HEADING, self.context())
        self.install({'parallel_agents': False})
        self.assertNotIn(HEADING, self.context())

    def test_on_adds_the_rule_to_the_kit_context(self):
        self.install({'parallel_agents': True})
        text = self.context()
        rule = text[text.index(HEADING):]
        for words in ('two or more independent parts', 'only reads works in place', 'its own git worktree', 'never with `--force`',
                      'one sub-agent writes at a time', 'agreement'):
            self.assertIn(words, rule, words)
        self.assertLess(len(rule.split('\n\n')[0].splitlines()), 8)  # a short rule, not a protocol
        self.install({'parallel_agents': False})
        self.assertNotIn(HEADING, self.context())

    def test_the_rule_reaches_every_cli(self):
        (self.home/'.codex').mkdir()
        (self.home/'.claude').mkdir()
        self.install({'parallel_agents': True}, target='all')
        self.assertIn(HEADING, self.context())
        self.assertIn(HEADING, (self.home/'.codex'/'AGENTS.md').read_text(encoding='utf-8'))

    def test_a_team_turns_it_on_and_a_person_turns_it_off(self):
        with mock.patch('installer.plan.team_settings', return_value={'parallel_agents': True}):
            self.install()
            self.assertIn(HEADING, self.context())
            self.install({'parallel_agents': False})
            self.assertNotIn(HEADING, self.context())

    def test_the_setting_is_checked(self):
        path = self.home/'.ai-kit'/'aikit.toml'
        path.parent.mkdir(parents=True)
        path.write_text('schema = 1\n[agents]\nparallel = "yes"\n', encoding='utf-8')
        with self.assertRaises(KitError) as caught:
            config.load_aikit(path)
        self.assertIn('agents.parallel must be true or false', str(caught.exception))
        path.write_text('schema = 1\n[agents]\nparallel = true\nswarm = true\n', encoding='utf-8')
        data, warnings = config.load_aikit(path)
        self.assertEqual(config.to_overrides(data), {'parallel_agents': True})
        self.assertEqual(warnings, ['[Check] ~/.ai-kit/aikit.toml: unknown key agents.swarm, ignored.'])
        self.assertEqual(unknown_keys({'parallel_agents': True}), [])
        path.unlink()  # the person sets nothing: the Team's value is the one checked
        with mock.patch('installer.plan.team_settings', return_value={'parallel_agents': 'often'}), self.assertRaises(KitError):
            self.install()

    def test_where_the_setting_comes_from(self):
        self.assertEqual(config.provenance({}, {'parallel_agents': True}, {})['parallel_agents'], 'team')
        self.assertEqual(config.provenance({}, {'parallel_agents': True}, {'parallel_agents': False})['parallel_agents'], 'you')


if __name__ == '__main__':
    unittest.main()
