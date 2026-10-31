"""0.37: the settings people write are TOML. The person's overrides.json becomes overrides.toml at the next update (same
values, _ explanations as comments, the JSON file in the backup); the installer changes only the lists chosen, never the
person's comments; a mistake is reported with its line and a plain hint."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import KitError
from installer.toml_files import dump_toml, parse_toml, read_toml, set_list


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.kit = self.home/'.ai-kit'
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_kit(self, choices=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            notices = cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini', choices=choices)
        return notices, out.getvalue()


class MigrationTests(Base):
    LEGACY = {'$schema': 'file:///old/kit/schemas/overrides.schema.json', '_doc': 'My settings.\nSecond line.',
              'extra_commands': ['ask'], 'hooks': {'dbt-prod-guard': True}, '_why': 'asked by the team',
              'mcp': {'github': {'server': {'command': 'docker', 'args': ['run', '-i'], 'env': {'TOKEN': '${TOKEN}'}}}}}

    def test_overrides_json_becomes_toml_with_the_same_settings(self):
        self.kit.mkdir()
        (self.kit/'overrides.json').write_text(json.dumps(self.LEGACY), encoding='utf-8')
        notices, _ = self.run_kit()
        self.assertFalse((self.kit/'overrides.json').exists())
        text = (self.kit/'overrides.toml').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('#:schema ' + (self.kit.resolve()/'schemas'/'overrides.schema.json').as_uri()))
        self.assertIn('# My settings.\n# Second line.', text)
        self.assertIn('# asked by the team', text)
        self.assertIn('env = { TOKEN = "${TOKEN}" }', text)
        self.assertEqual(read_toml(self.kit/'overrides.toml'),
                         {k: v for k, v in self.LEGACY.items() if not k.startswith(('_', '$'))})
        self.assertTrue(any('is now ~/.ai-kit/overrides.toml' in n for n in notices))
        backups = list((self.kit/'backups').rglob('overrides.json'))
        self.assertEqual(json.loads(backups[0].read_text(encoding='utf-8')), self.LEGACY)
        self.assertIn('ask', json.loads((self.kit/'state.json').read_text(encoding='utf-8'))['installed']['commands'])

    def test_both_files_the_toml_wins_and_the_json_is_named(self):
        self.kit.mkdir()
        (self.kit/'overrides.json').write_text(json.dumps({'extra_commands': ['ask']}), encoding='utf-8')
        (self.kit/'overrides.toml').write_text('extra_commands = []\n', encoding='utf-8')
        notices, _ = self.run_kit()
        self.assertTrue((self.kit/'overrides.json').exists())
        self.assertTrue(any('overrides.json is no longer read' in n for n in notices))
        self.assertNotIn('ask', json.loads((self.kit/'state.json').read_text(encoding='utf-8'))['installed']['commands'])

    def test_new_file_from_the_commented_template(self):
        self.run_kit()
        text = (self.kit/'overrides.toml').read_text(encoding='utf-8')
        self.assertIn('# [mcp.github.server]', text)
        self.assertEqual(read_toml(self.kit/'overrides.toml'), {})


class ChoicesTests(Base):
    def test_only_the_chosen_lists_change_and_comments_stay(self):
        self.kit.mkdir()
        mine = '# my notes\nextra_commands = [\n  "ask",  # for the data team\n]\n\n[hooks]\ndbt-prod-guard = true  # keep\n'
        (self.kit/'overrides.toml').write_text(mine, encoding='utf-8')
        self.run_kit(choices={'extra_commands': ['ask', 'handoff'], 'disabled_commands': ['retro']})
        text = (self.kit/'overrides.toml').read_text(encoding='utf-8')
        self.assertIn('# my notes', text)
        self.assertIn('dbt-prod-guard = true  # keep', text)
        self.assertEqual(read_toml(self.kit/'overrides.toml'),
                         {'extra_commands': ['ask', 'handoff'], 'disabled_commands': ['retro'], 'hooks': {'dbt-prod-guard': True}})
        self.assertLess(text.index('disabled_commands'), text.index('[hooks]'))  # a new list goes before the first section

    def test_set_list_never_changes_another_value(self):
        text = 'a = ["x # not a comment", "]"]  # c\nb = 1\n'
        self.assertEqual(parse_toml(set_list(text, 'a', ['y'])), {'a': ['y'], 'b': 1})
        self.assertEqual(parse_toml(set_list(text, 'c', ['z'])), {'a': ['x # not a comment', ']'], 'b': 1, 'c': ['z']})


class ErrorTests(Base):
    def test_a_mistake_is_reported_with_its_line_and_a_hint(self):
        self.kit.mkdir()
        (self.kit/'overrides.toml').write_text('extra_commands = ["ask"]\nskill_prefix = kit-\n', encoding='utf-8')
        with self.assertRaises(KitError) as ctx:
            self.run_kit()
        message = str(ctx.exception)
        self.assertIn('line 2', message)
        self.assertIn('a text must be in double quotes', message)
        self.assertIn('skill_prefix = kit-', message)

    def test_dump_refuses_what_it_cannot_write_back(self):
        with self.assertRaises(KitError):
            dump_toml({'a': None})


class RepoFilesTests(unittest.TestCase):
    def test_profiles_and_organization_are_toml(self):
        root = cli.ROOT
        self.assertFalse(list((root/'profiles').glob('*.json')))
        self.assertFalse((root/'organization.json').exists())
        for path in (root/'profiles').glob('*.toml'):
            profile = read_toml(path)
            self.assertEqual(profile['id'], path.stem)
            self.assertEqual(set(profile) - {'id', 'label', 'order', 'practices', 'skills', 'mcp', 'agents', 'commands'}, set(), path.name)


if __name__ == '__main__':
    unittest.main()
