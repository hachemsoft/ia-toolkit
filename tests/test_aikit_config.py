"""2.0.0: the person's ~/.ai-kit/aikit.toml (overrides.toml read through an adapter until then), its migration, the content
manifest's min_engine, and the three closed schemas kept in line with the loaders (docs/v2/config.md)."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from installer import cli, config
from installer.core import ROOT, KitError, content_from
from installer.settings import personal_settings
from installer.toml_files import dump_toml, parse_toml, set_section_key


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = function(*args, **kwargs)
    return result, out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base/'home'
        self.kit = self.home/'.ai-kit'
        self.kit.mkdir(parents=True)

    def write(self, name, data):
        (self.kit/name).write_text(dump_toml(data) if isinstance(data, dict) else data, encoding='utf-8')

    def state(self):
        return json.loads((self.kit/'state.json').read_text(encoding='utf-8'))


class LoaderTests(Base):
    def test_valid_file_translates_to_the_engine_keys(self):
        self.write('aikit.toml', {'schema': 1, 'user': {'extra_skills': ['prototype'], 'skill_prefix': 'x-'}, 'hooks': {'dbt-prod-guard': True},
                                  'mcp': {'enabled': ['docs'], 'denied': ['docs', 'db']}, 'frictions': {'capture': 'off', 'publication': 'disabled'}})
        self.assertEqual(personal_settings(self.kit), {'extra_skills': ['prototype'], 'skill_prefix': 'x-', 'hooks': {'dbt-prod-guard': True},
                                                       'mcp': {'docs': False, 'db': False}, 'frictions': 'off', 'share_frictions': False})

    def test_aikit_wins_and_overrides_is_no_longer_read(self):
        self.write('overrides.toml', {'extra_skills': ['prototype']})
        self.write('aikit.toml', {'schema': 1})
        self.assertEqual(personal_settings(self.kit), {})

    def test_without_aikit_overrides_is_read_as_before(self):
        self.write('overrides.toml', {'extra_skills': ['prototype']})
        self.assertEqual(personal_settings(self.kit), {'extra_skills': ['prototype']})

    def test_wrong_type_or_schema_stops_and_unknown_key_warns(self):
        for data, message in (({'user': {}}, 'schema must be'), ({'schema': 2}, 'schema must be'), ({'schema': True}, 'schema must be'),
                              ({'schema': 1, 'user': {'extra_skills': 'tdd'}}, 'list of names'), ({'schema': 1, 'hooks': {'x': 1}}, 'true or false'),
                              ({'schema': 1, 'frictions': {'publication': 'auto'}}, 'set by IT'), ({'schema': 1, 'user': []}, 'must be a table')):
            self.write('aikit.toml', data)
            with self.subTest(data=data), self.assertRaises(KitError) as caught:
                config.load_aikit(self.kit/'aikit.toml')
            self.assertIn(message, str(caught.exception))
        self.write('aikit.toml', {'schema': 1, 'colour': 'blue', 'user': {'theme': 'x'}})
        self.assertEqual(config.load_aikit(self.kit/'aikit.toml')[1], ['[Check] ~/.ai-kit/aikit.toml: unknown key colour, ignored.',
                                                                    '[Check] ~/.ai-kit/aikit.toml: unknown key user.theme, ignored.'])


class MigrationTests(Base):
    V1 = {'extra_skills': ['prototype'], 'disabled_commands': ['learn'], 'skill_prefix': 'kit-', 'hooks': {'dbt-prod-guard': True},
          'mcp': {'docs': True, 'db': False, 'mine': {'server': {'httpUrl': 'https://mcp.example.org'}}}, 'frictions': 'auto',
          'share_frictions': False, 'news': {'check_remote': False}}

    def test_every_v1_key_has_a_destination_or_a_reason(self):
        text, report = config.aikit_from_overrides(self.V1)
        data = parse_toml(text)
        self.assertEqual(data['user'], {'extra_skills': ['prototype'], 'disabled_commands': ['learn'], 'skill_prefix': 'kit-'})
        self.assertEqual(data['mcp'], {'enabled': ['docs'], 'denied': ['db']})
        self.assertEqual(data['frictions'], {'capture': 'auto', 'publication': 'disabled'})
        self.assertIn('mcp.mine (your own server) not carried over: add it in your CLI; overrides.toml keeps it for AI Kit 0.52', report)
        self.assertTrue(any(line.startswith('news not carried over') for line in report))
        expected = {k: v for k, v in self.V1.items() if k not in ('news',)}
        expected['mcp'] = {'docs': True, 'db': False}
        self.assertEqual(config.to_overrides(data), expected)  # the same settings, except what the report names

    def test_update_migrate_config_writes_aikit_keeps_overrides_and_installs_the_same(self):
        quiet(cli.apply, 'general', self.home, False, None, 'claude', choices={'extra_skills': ['prototype']})
        before = self.state()['installed']
        overrides = (self.kit/'overrides.toml').read_bytes()
        code, out = quiet(cli.main, ['update', '--migrate-config', '--home', str(self.home), '--target', 'claude'])
        self.assertEqual(code, 0, out)
        self.assertIn('extra_skills -> user.extra_skills', out)
        self.assertEqual((self.kit/'overrides.toml').read_bytes(), overrides)  # kept for a return to 0.52
        self.assertEqual(parse_toml((self.kit/'aikit.toml').read_text(encoding='utf-8'))['user'], {'extra_skills': ['prototype']})
        self.assertTrue((self.kit/'schemas/aikit.schema.json').is_file())
        self.assertEqual(self.state()['installed'], before)
        code, out = quiet(cli.main, ['update', '--migrate-config', '--home', str(self.home), '--target', 'claude'])
        self.assertIn('already exists', out)

    def test_dry_run_writes_nothing(self):
        self.write('overrides.toml', {'frictions': 'off'})
        quiet(cli.migrate_config, self.home, True)
        self.assertFalse((self.kit/'aikit.toml').exists())

    def test_choices_go_to_aikit_once_migrated(self):
        self.write('aikit.toml', '#:schema x\nschema = 1\n\n# my notes\n[user]\nextra_skills = ["prototype"]\n')
        self.write('overrides.toml', {'extra_skills': ['investigation']})
        quiet(cli.apply, 'general', self.home, False, None, 'claude', choices={'disabled_commands': ['learn'], 'extra_skills': ['prototype', 'teach']})
        text = (self.kit/'aikit.toml').read_text(encoding='utf-8')
        self.assertIn('# my notes', text)
        self.assertEqual(parse_toml(text)['user'], {'extra_skills': ['prototype', 'teach'], 'disabled_commands': ['learn']})
        self.assertEqual(parse_toml((self.kit/'overrides.toml').read_text(encoding='utf-8')), {'extra_skills': ['investigation']})
        self.assertNotIn('learn', self.state()['installed']['commands'])


class SectionWriterTests(unittest.TestCase):
    def test_sets_replaces_and_adds_keeping_the_rest(self):
        text = 'schema = 1\n# keep\n[user]\nextra_skills = [\n  "a",\n]\n\n[hooks]\nx = true\n'
        out = set_section_key(text, 'user', 'extra_skills', ['b'])
        self.assertEqual(parse_toml(out), {'schema': 1, 'user': {'extra_skills': ['b']}, 'hooks': {'x': True}})
        self.assertIn('# keep', out)
        out = set_section_key(out, 'user', 'disabled_skills', ['c'])
        out = set_section_key(out, 'frictions', 'capture', 'off')
        self.assertEqual(parse_toml(out), {'schema': 1, 'user': {'extra_skills': ['b'], 'disabled_skills': ['c']}, 'hooks': {'x': True},
                                           'frictions': {'capture': 'off'}})


class MinEngineTests(Base):
    def source(self, manifest):
        source = self.base/'core'
        for name in ('skills', 'agents', 'commands', 'context', 'organization.toml', 'templates'):
            (shutil.copytree if (ROOT/name).is_dir() else shutil.copy2)(ROOT/name, source/name)
        if manifest is not None:
            (source/'aikit.toml').write_text(manifest, encoding='utf-8')
        return source

    def test_the_kit_content_declares_itself(self):
        self.assertEqual(config.check_source(ROOT, (ROOT/'VERSION').read_text(encoding='utf-8').strip())['name'], 'core')

    def test_a_content_needing_a_newer_engine_changes_nothing(self):
        with content_from(self.source('schema = 1\nname = "core"\nmin_engine = "99.0.0"\n')), self.assertRaises(KitError) as caught:
            quiet(cli.apply, 'general', self.home, False, None, 'claude')
        self.assertIn('needs AI Kit 99.0.0 or newer', str(caught.exception))
        self.assertFalse((self.kit/'state.json').exists())

    def test_no_manifest_is_the_v1_layout_and_a_bad_one_is_refused(self):
        with content_from(self.source(None)):
            quiet(cli.apply, 'general', self.home, False, None, 'claude')
        for manifest, message in (('schema = 1\n', 'name must be'), ('schema = 1\nname = "c"\nmin_engine = "2"\n', 'X.Y.Z'),
                                  ('schema = 1\nname = "c"\nextra = 1\n', 'unknown key')):
            with self.subTest(manifest=manifest), self.assertRaises(KitError) as caught:
                config.check_source(self._manifest(manifest), '2.0.0')
            self.assertIn(message, str(caught.exception))

    def _manifest(self, text):
        folder = Path(tempfile.mkdtemp(dir=self.base))
        (folder/'aikit.toml').write_text(text, encoding='utf-8')
        return folder


class SchemaTests(unittest.TestCase):
    """The JSON schemas give editors completion; the loaders in installer/config.py are the closed schema. They must agree."""

    def schema(self, name):
        return json.loads((ROOT/'schemas'/(name+'.schema.json')).read_text(encoding='utf-8'))

    def test_managed_schema_matches_the_loader(self):
        s = self.schema('managed')
        self.assertEqual(set(s['properties']), {'managed_schema', 'hooks', 'mcp', 'frictions', 'enterprise', 'git', 'teams'})
        self.assertEqual(set(s['properties']['git']['properties']), set(config.MANAGED_GIT))
        self.assertEqual(set(s['properties']['mcp']['properties']), {'allow_stdio', 'denied', 'allowed_stdio', 'allowed_http'})
        self.assertEqual(s['properties']['frictions']['properties']['capture']['enum'], list(config.FRICTION_CAPTURE))
        self.assertEqual(s['properties']['frictions']['properties']['publication']['enum'], list(config.FRICTION_PUBLICATION))
        self.assertEqual(s['properties']['managed_schema']['const'], max(config.MANAGED_SCHEMAS))

    def test_aikit_schema_matches_the_loader(self):
        s = self.schema('aikit')
        self.assertEqual(set(s['properties']) - {'schema'}, set(config.AIKIT_SECTIONS))
        for section, keys in config.AIKIT_SECTIONS.items():
            if keys is not None:
                self.assertEqual(set(s['properties'][section]['properties']), set(keys), section)
        self.assertEqual(s['properties']['frictions']['properties']['publication']['enum'], list(config.PERSONAL_PUBLICATION))

    def test_source_schema_matches_the_loader(self):
        self.assertEqual(set(self.schema('source')['properties']), {'schema', 'name', 'kind', 'min_engine', 'defaults'})


if __name__ == '__main__':
    unittest.main()
