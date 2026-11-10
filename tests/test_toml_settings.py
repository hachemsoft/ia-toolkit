"""The settings people write are TOML: ~/.ai-kit/aikit.toml (AI Kit 3), created once from the commented template; the
installer changes only the lists chosen, never the person's comments; a mistake is reported with its line and a plain hint."""
import contextlib
import io
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
            notices = cli.apply(self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini', choices=choices)
        return notices, out.getvalue()


class NewFileTests(Base):
    def test_new_file_from_the_commented_template(self):
        self.run_kit()
        text = (self.kit/'aikit.toml').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('#:schema ' + (self.kit.resolve()/'schemas'/'aikit.schema.json').as_uri()))
        self.assertTrue((self.kit/'schemas/aikit.schema.json').is_file())
        self.assertIn('# [mcp]', text)
        self.assertEqual(read_toml(self.kit/'aikit.toml'), {'schema': 1})


class ChoicesTests(Base):
    def test_only_the_chosen_lists_change_and_comments_stay(self):
        self.kit.mkdir()
        mine = 'schema = 1\n# my notes\n\n[user]\nextra_commands = [\n  "ask",  # for the data team\n]\n\n[hooks]\ndbt-prod-guard = true  # keep\n'
        (self.kit/'aikit.toml').write_text(mine, encoding='utf-8')
        self.run_kit(choices={'extra_commands': ['ask', 'handoff'], 'disabled_commands': ['retro']})
        text = (self.kit/'aikit.toml').read_text(encoding='utf-8')
        self.assertIn('# my notes', text)
        self.assertIn('dbt-prod-guard = true  # keep', text)
        self.assertEqual(read_toml(self.kit/'aikit.toml'),
                         {'schema': 1, 'user': {'extra_commands': ['ask', 'handoff'], 'disabled_commands': ['retro']}, 'hooks': {'dbt-prod-guard': True}})
        self.assertLess(text.index('disabled_commands'), text.index('[hooks]'))  # a new list goes in its own section [user]

    def test_set_list_never_changes_another_value(self):
        text = 'a = ["x # not a comment", "]"]  # c\nb = 1\n'
        self.assertEqual(parse_toml(set_list(text, 'a', ['y'])), {'a': ['y'], 'b': 1})
        self.assertEqual(parse_toml(set_list(text, 'c', ['z'])), {'a': ['x # not a comment', ']'], 'b': 1, 'c': ['z']})


class LineEndingTests(unittest.TestCase):
    def test_aikit_toml_untouched_without_a_choice_and_crlf_kept_with_one(self):
        import tempfile
        from installer.plan import personal_file
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp)
            (kit/'aikit.toml').write_bytes(b'schema = 1\r\n# mine\r\n')
            self.assertIsNone(personal_file(kit, {}, [])[1])
            written = personal_file(kit, {'extra_skills': ['teach']}, [])[1]
            self.assertIn(b'# mine\r\n', written)
            self.assertNotIn(b'\n', written.replace(b'\r\n', b''))


class ErrorTests(Base):
    def test_a_mistake_is_reported_with_its_line_and_a_hint(self):
        self.kit.mkdir()
        (self.kit/'aikit.toml').write_text('schema = 1\n[user]\nskill_prefix = kit-\n', encoding='utf-8')
        with self.assertRaises(KitError) as ctx:
            self.run_kit()
        message = str(ctx.exception)
        self.assertIn('line 3', message)
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
        self.assertFalse(list((root/'agents'/'internal').rglob('*.json')))  # agents are Markdown, like skills and commands
        for path in (root/'profiles').glob('*.toml'):
            profile = read_toml(path)
            self.assertEqual(profile['id'], path.stem)
            self.assertEqual(set(profile) - {'id', 'label', 'order', 'context', 'skills', 'mcp', 'agents', 'commands'}, set(), path.name)


if __name__ == '__main__':
    unittest.main()
