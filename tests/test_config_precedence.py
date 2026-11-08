"""managed.toml (2.0.0, ADR 0015): read from an administered path, closed schema, every key present wins (false and [] included),
an absent key locks nothing, restrictions add up, an unusable file changes nothing (exit code 3)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli, config
from installer.toml_files import dump_toml

GUARDRAILS = ('protected-paths', 'dbt-prod-guard')
TRACKER = {'friction_tracker': {'kind': 'gitlab', 'project': 'tools/feedback', 'host': 'gitlab.example.org'}}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)/'home'
        self.home.mkdir()
        self.managed = Path(temp.name)/'managed.toml'
        trusted = mock.patch('installer.config.ownership_problem', return_value=None)  # a temp file cannot be root-owned
        trusted.start()
        self.addCleanup(trusted.stop)

    def write_managed(self, data):
        self.managed.write_text(dump_toml(data) if isinstance(data, dict) else data, encoding='utf-8')

    def personal(self, data):
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        (self.home/'.ai-kit/overrides.toml').write_text(dump_toml(data), encoding='utf-8')

    def apply(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.apply('general', self.home, False, None, 'claude', managed_file=self.managed, **kwargs)

    def state(self):
        return json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))


class SchemaTests(Base):
    def refused(self, data):
        self.write_managed(data)
        with self.assertRaises(config.ManagedConfigError):
            config.load_managed(self.managed, GUARDRAILS)

    def test_no_file_means_not_administered(self):
        self.assertIsNone(config.load_managed(self.managed, GUARDRAILS))

    def test_closed_schema_refuses_unknown_keys_types_and_schemas(self):
        for data in ({'hooks': {}},  # managed_schema missing
                     {'managed_schema': 2}, {'managed_schema': True},
                     {'managed_schema': 1, 'git': {'allowed_hosts': ['h']}},  # not applied by this version: refused, never ignored
                     {'managed_schema': 1, 'hooks': {'unknown-guard': True}},
                     {'managed_schema': 1, 'hooks': {'protected-paths': 'yes'}},
                     {'managed_schema': 1, 'hooks': {'locked': ['nope']}},
                     {'managed_schema': 1, 'hooks': {'locked': ['protected-paths'], 'protected-paths': False}},  # contradiction
                     {'managed_schema': 1, 'mcp': {'allow_stdio': 'false'}}, {'managed_schema': 1, 'mcp': {'denied': 'x'}},
                     {'managed_schema': 1, 'mcp': {'allowed': ['x']}},
                     {'managed_schema': 1, 'frictions': {'publication': 'sometimes'}}, {'managed_schema': 1, 'frictions': {'retention_days': 30}}):
            with self.subTest(data):
                self.refused(data)

    def test_unreadable_and_user_writable_files_are_refused(self):
        self.refused('managed_schema = 1\n[hooks\n')
        self.write_managed({'managed_schema': 1})
        with mock.patch('installer.config.ownership_problem', return_value='the current user can write it'):
            with self.assertRaises(config.ManagedConfigError) as caught:
                config.load_managed(self.managed, GUARDRAILS)
        self.assertIn('IT', str(caught.exception))

    def test_an_unusable_file_changes_nothing_and_exits_3(self):
        self.apply()
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.write_managed({'managed_schema': 1, 'unknown': 1})
        with self.assertRaises(config.ManagedConfigError):
            self.apply()
        self.assertEqual({p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}, before)
        with mock.patch('installer.config.managed_path', return_value=self.managed), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['update', '--home', str(self.home), '--target', 'claude']), 3)

    def test_the_administered_path_is_fixed_not_taken_from_the_environment(self):
        with mock.patch.dict('os.environ', {'ProgramData': '/tmp/elsewhere', 'AI_KIT_MANAGED': '/tmp/x'}):
            self.assertNotIn('elsewhere', str(config.managed_path()))
            self.assertNotIn('/tmp/x', str(config.managed_path()))


class PrecedenceTests(Base):
    def test_a_managed_false_wins_over_the_person_and_over_organization_locks(self):
        self.personal({'hooks': {'protected-paths': True}})
        self.write_managed({'managed_schema': 1, 'hooks': {'protected-paths': False}})
        with mock.patch('installer.plan.organization', return_value={'locked_hooks': ['protected-paths']}):
            notices = self.apply()
        self.assertNotIn('protected-paths', self.state()['hooks'])
        self.assertTrue(any('ignored: IT sets it to false' in n for n in notices))

    def test_hooks_locked_adds_to_restrictions_and_the_person_cannot_lift_it(self):
        self.personal({'hooks': {'dbt-prod-guard': False}})
        self.write_managed({'managed_schema': 1, 'hooks': {'locked': ['dbt-prod-guard']}})
        self.apply()
        self.assertIn('dbt-prod-guard', self.state()['hooks'])

    def test_an_absent_key_locks_nothing(self):
        self.personal({'hooks': {'protected-paths': False}})
        self.write_managed({'managed_schema': 1})
        self.apply()
        self.assertNotIn('protected-paths', self.state()['hooks'])

    def test_frictions_capture_is_set_by_it(self):
        self.personal({'frictions': 'auto'})
        self.write_managed({'managed_schema': 1, 'frictions': {'capture': 'off'}})
        self.apply()
        self.assertNotIn('## Frictions', (self.home/'.ai-kit/context/00_KIT.md').read_text(encoding='utf-8'))  # off: no section

    def test_mcp_denied_and_stdio_refused(self):
        servers = {'mcp': {'docs': {'server': {'httpUrl': 'https://mcp.example.org/docs'}}, 'local': {'server': {'command': 'my-mcp'}},
                           'other': {'server': {'httpUrl': 'https://mcp.example.org/o'}}}}
        self.personal(servers)
        self.write_managed({'managed_schema': 1, 'mcp': {'denied': ['other'], 'allow_stdio': False}})
        notices = self.apply()
        self.assertEqual(sorted(self.state()['mcp']), ['ai-kit-docs'])
        self.assertTrue(any('refused by IT (managed.toml mcp.denied)' in n for n in notices))
        self.assertTrue(any('mcp.allow_stdio = false' in n for n in notices))

    def test_an_empty_denied_list_is_a_value_not_an_error(self):
        self.personal({'mcp': {'docs': {'server': {'httpUrl': 'https://mcp.example.org/docs'}}}})
        self.write_managed({'managed_schema': 1, 'mcp': {'denied': []}})
        self.apply()
        self.assertEqual(sorted(self.state()['mcp']), ['ai-kit-docs'])


class FrictionPublicationTests(Base):
    def tracker_state(self, managed=None, personal=None):
        if managed is not None:
            self.write_managed({'managed_schema': 1, 'frictions': managed})
        if personal is not None:
            self.personal(personal)
        with mock.patch('installer.cli.org_defaults_root', return_value=TRACKER):
            self.apply()
        return self.state().get('friction_tracker')

    def test_approval_is_the_default(self):
        self.assertEqual(self.tracker_state()['publication'], 'approval')

    def test_managed_auto_and_disabled(self):
        self.assertEqual(self.tracker_state({'publication': 'auto'})['publication'], 'auto')
        self.assertIsNone(self.tracker_state({'publication': 'disabled'}))

    def test_a_person_who_refuses_sharing_keeps_frictions_local_even_when_it_imposes_auto(self):
        # O4: the person's refusal is a restriction of their own; managed.toml sets the mode, not the person's consent.
        self.assertIsNone(self.tracker_state({'publication': 'auto'}, {'share_frictions': False}))


class DriftTests(Base):
    """The managed file as applied is recorded (its digest): doctor tells the person when IT changed it since the last update."""

    def test_digest_recorded_and_changes_detected(self):
        self.assertIsNone(config.drift(None, self.managed))  # not administered, nothing recorded
        self.write_managed({'managed_schema': 1, 'mcp': {'allow_stdio': False}})
        self.assertIn('added', config.drift(None, self.managed))
        self.apply()
        recorded = self.state()['managed']['digest']
        self.assertIsNone(config.drift(recorded, self.managed))
        self.write_managed({'managed_schema': 1, 'mcp': {'allow_stdio': True}})
        self.assertIn('changed', config.drift(recorded, self.managed))
        self.managed.unlink()
        self.assertIn('removed', config.drift(recorded, self.managed))

    def test_no_managed_key_in_state_when_not_administered(self):
        self.apply()
        self.assertNotIn('managed', self.state())


class ProvenanceTests(unittest.TestCase):
    def test_the_highest_layer_names_the_origin_and_it_wins(self):
        origin = config.provenance({'frictions': 'auto', 'hooks': {'dbt-prod-guard': True}}, {'extra_skills': ['x']},
                                   {'frictions': 'off', 'hooks': {'dbt-prod-guard': False}, 'disabled_skills': ['y']},
                                   {'managed_schema': 1, 'hooks': {'locked': ['protected-paths'], 'dbt-prod-guard': True}})
        self.assertEqual(origin, {'disabled_skills': 'you', 'extra_skills': 'team', 'frictions': 'you', 'hooks.dbt-prod-guard': 'IT'})
        self.assertEqual(config.provenance({}, {}, {'frictions': 'off'}, {'managed_schema': 1, 'frictions': {'capture': 'auto'}})['frictions'], 'IT')


if __name__ == '__main__':
    unittest.main()
