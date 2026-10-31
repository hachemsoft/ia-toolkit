"""organization.json: organization defaults merged with each person's overrides, team as its own dimension, update that pulls."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import cli
from installer.cli import apply, doctor, merge_settings, setting_differences
import wheelhouse
from installer.core import KitError, ROOT, read_json

IDENTITY = {'email': 'first.last@example.com', 'source': 'test'}


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def organization(self, org):
        """Run with this organization.json instead of the kit's."""
        real = cli.read_json
        def patched(path, default=None):
            return org if Path(path).name == 'organization.json' else real(path, default)
        return mock.patch.object(cli, 'read_json', side_effect=patched)

    def install(self, profile='general', team=None):
        with contextlib.redirect_stdout(io.StringIO()):
            apply(profile, self.home, False, IDENTITY, 'gemini', team)
        return read_json(self.home/'.ai-kit/state.json')

    def personal(self, overrides):
        (self.home/'.ai-kit').mkdir(parents=True, exist_ok=True)
        (self.home/'.ai-kit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')

    def test_merge_adds_lists_combines_objects_person_wins(self):
        org = {'extra_skills': ['a'], 'hooks': {'dbt-prod-guard': True}, 'model': 'm1', '_doc': 'x'}
        person = {'extra_skills': ['b', 'a'], 'hooks': {'protected-paths': False}, 'model': 'm2', '_doc': 'y'}
        self.assertEqual(merge_settings(org, person),
                         {'extra_skills': ['a', 'b'], 'hooks': {'dbt-prod-guard': True, 'protected-paths': False}, 'model': 'm2'})
        self.assertEqual(setting_differences(org, merge_settings(org, person)), ['model'])

    def test_organization_defaults_survive_a_personal_file(self):
        # The defect this release fixes: a personal overrides.json used to replace the organization defaults wholesale.
        self.personal({'extra_skills': ['teach']})
        with self.organization({'defaults': {'hooks': {'dbt-prod-guard': True}}}):
            state = self.install()
        self.assertIn('dbt-prod-guard', state['hooks'])
        self.assertIn('protected-paths', state['hooks'])

    def test_person_can_turn_off_an_organization_default(self):
        self.personal({'hooks': {'dbt-prod-guard': False}})
        with self.organization({'defaults': {'hooks': {'dbt-prod-guard': True}}}):
            state = self.install()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                doctor(self.home)
        self.assertNotIn('dbt-prod-guard', state['hooks'])
        self.assertIn('Your overrides.json changes organization or team defaults: hooks.dbt-prod-guard', out.getvalue())

    def test_team_selects_its_practices_whatever_the_profile(self):
        team_file = ROOT/'practices/20-kit-test-team.md'
        team_file.write_text('# Test team practices\n- Rule of the test team.\n', encoding='utf-8')
        self.addCleanup(team_file.unlink)
        state = self.install('java-developer', team='kit-test-team')
        self.assertEqual(state['team'], 'kit-test-team')
        self.assertTrue((self.home/'.gemini/20_KIT_TEST_TEAM.md').is_file())
        self.assertFalse((self.home/'.gemini/20_TEAM.md').exists())
        # Kept for update, without --team.
        self.assertEqual(self.install('java-developer')['team'], 'kit-test-team')

    def test_team_none_leaves_the_team(self):
        team_file = ROOT/'practices/20-kit-test-team.md'
        team_file.write_text('# Test team practices\n', encoding='utf-8')
        self.addCleanup(team_file.unlink)
        self.install('general', team='kit-test-team')
        state = self.install('general', team='none')
        self.assertIsNone(state['team'])
        self.assertTrue((self.home/'.gemini/20_TEAM.md').is_file())
        self.assertFalse((self.home/'.gemini/20_KIT_TEST_TEAM.md').exists())

    def test_unknown_team_refused(self):
        with self.assertRaises(KitError):
            self.install(team='no-such-team')

    def test_json_error_says_where_and_what(self):
        bad = self.home/'overrides.json'
        bad.write_text('{\n  "extra_skills": ["a", "b",]\n}\n', encoding='utf-8')
        with self.assertRaises(KitError) as ctx:
            read_json(bad)
        message = str(ctx.exception)
        self.assertRegex(message, r'line 2, column 2[89]')  # the column moved by one in Python 3.13
        self.assertIn('a comma is left before } or ]', message)
        self.assertIn('"extra_skills": ["a", "b",]', message)


    def test_every_usual_json_mistake_is_explained(self):
        # Each Python version words these errors its own way (3.13 changed the trailing comma): all must get a plain hint.
        from installer.core import JSON_HINTS
        plain = {hint for _, hint in JSON_HINTS}
        for text in ('{"a": 1 "b": 2}', '{"a": [1, 2,]}', '{"a": 1,}', "{'a': 1}", '{"a" 1}', '{"a": "x}', '{"p": "C:\\Users"}',
                     '{"a": 1} {"b": 2}', '{"a": }', '{"a": "x\ny"}'):
            bad = self.home/'bad.json'
            bad.write_text(text, encoding='utf-8')
            with self.assertRaises(KitError) as ctx:
                read_json(bad)
            first = str(ctx.exception).splitlines()[0]
            self.assertTrue(any(h in first for h in plain), text + ' -> ' + first)

    def test_schema_lists_exactly_the_keys_the_installer_reads(self):
        import re
        code = ''.join(f.read_text(encoding='utf-8') for f in (ROOT/'installer').rglob('*.py'))
        read = set(re.findall(r"(?:overrides|personal)(?:\.get\(|\[)'([a-z_]+)'", code))
        schema = read_json(ROOT/'schemas/overrides.schema.json')
        declared = {k for k in schema['properties'] if not k.startswith('$')}
        self.assertEqual(read, declared)
        self.assertEqual(set(schema['properties']['hooks']['properties']), set(read_json(ROOT/'runtime/hooks/hooks.json')['hooks']))

    def test_shipped_files_follow_the_schemas(self):
        org = read_json(ROOT/'organization.json')
        self.assertTrue((ROOT/org['$schema']).is_file())
        known = set(read_json(ROOT/'schemas/organization.schema.json')['properties'])
        self.assertEqual([k for k in org if not k.startswith('_') and k not in known], [])
        self.assertEqual(cli.unknown_keys(org.get('defaults', {})), [])
        self.assertEqual(cli.unknown_keys(read_json(ROOT/'templates/user-overrides.json')), [])

    def test_personal_file_points_to_the_schema_and_typos_are_reported(self):
        self.install()
        personal = read_json(self.home/'.ai-kit/overrides.json')
        from urllib.parse import urlparse, unquote
        target = Path(unquote(urlparse(personal['$schema']).path.lstrip('/') if os.name == 'nt' else unquote(urlparse(personal['$schema']).path)))
        self.assertTrue(target.is_file(), personal['$schema'])
        self.personal({**personal, 'extra_skill': ['teach']})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            doctor(self.home)
        self.assertIn('unknown: extra_skill', out.getvalue())
        self.assertEqual(merge_settings({}, {'$schema': 'x', 'model': 'm'}), {'model': 'm'})

class TeamToolsTests(unittest.TestCase):
    """A team in organization.json brings its tools (same keys as overrides.json), between the organization and the person."""
    ORG = {'defaults': {'extra_skills': ['teach'], 'mcp': {'dbt': {'server': {'command': 'dbt-mcp'}},
                                                          'github': {'server': {'command': 'gh-mcp'}}}},
           'teams': {'data-platform': {'extra_skills': ['prototype'], 'extra_commands': ['ask'], 'mcp': {'dbt': True},
                                       'hooks': {'dbt-prod-guard': True}}}}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self, team=None, personal=None, profile='general'):
        if personal is not None:
            (self.home/'.ai-kit').mkdir(parents=True, exist_ok=True)
            (self.home/'.ai-kit/overrides.json').write_text(json.dumps(personal), encoding='utf-8')
        real = cli.read_json
        with mock.patch.object(cli, 'read_json', side_effect=lambda p, d=None: self.ORG if Path(p).name == 'organization.json' else real(p, d)), \
             contextlib.redirect_stdout(io.StringIO()):
            apply(profile, self.home, False, IDENTITY, 'gemini', team)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                doctor(self.home)
        return read_json(self.home/'.ai-kit/state.json'), out.getvalue()

    def test_team_brings_skills_commands_guardrails_and_mcp(self):
        state, out = self.install('data-platform')
        skills = self.home/'.gemini/skills'
        self.assertTrue((skills/'teach').is_dir())       # organization
        self.assertTrue((skills/'prototype').is_dir())   # team
        self.assertTrue((self.home/'.gemini/commands/ask.toml').is_file())
        self.assertIn('dbt-prod-guard', state['hooks'])
        self.assertEqual(list(state['mcp']), ['ai-kit-dbt'])
        # No practices/20-data-platform.md: the shared team practices stay, the team is kept for update.
        self.assertEqual(state['team'], 'data-platform')
        self.assertIn('team', state['practices'])
        self.assertIn('[Info] Team: data-platform (organization.json teams.data-platform)', out)
        self.assertIn('organization.json teams.data-platform: only known keys', out)

    def test_without_the_team_nothing_of_it(self):
        state, _ = self.install()
        self.assertFalse((self.home/'.gemini/skills/prototype').exists())
        self.assertEqual(state['mcp'], {})

    def test_the_person_still_has_the_last_word(self):
        state, out = self.install('data-platform', {'mcp': {'dbt': False, 'github': True}, 'disabled_skills': ['prototype']})
        self.assertEqual(list(state['mcp']), ['ai-kit-github'])
        self.assertFalse((self.home/'.gemini/skills/prototype').exists())

    def test_team_listed_at_setup_and_unknown_team_refused(self):
        real = cli.read_json
        with mock.patch.object(cli, 'read_json', side_effect=lambda p, d=None: self.ORG if Path(p).name == 'organization.json' else real(p, d)):
            self.assertIn('data-platform', cli.team_ids())
            with self.assertRaises(KitError):
                apply('general', self.home, False, IDENTITY, 'gemini', 'no-such-team')


class McpTests(unittest.TestCase):
    """organization.json says how to reach a server, the profile which ones are on, overrides.json the person's exceptions."""
    ORG = {'bigquery': {'server': {'httpUrl': 'https://bq.example.org/mcp'}},
           'dbt': {'server': {'command': 'dbt-mcp'}},
           'github': {'server': {'command': 'docker', 'args': ['run', '-i', '--rm', 'ghcr.io/github/github-mcp-server:1.0.0']}},
           'docs': {'enabled': True, 'server': {'httpUrl': 'https://docs.example.org/mcp'}}}

    def resolve(self, profile, personal=None):
        return cli.resolve_mcp(self.ORG, profile, personal or {})

    def test_the_profile_chooses_among_the_organization_servers(self):
        servers, undefined = self.resolve(['bigquery', 'dbt'])
        self.assertEqual(sorted(servers), ['bigquery', 'dbt', 'docs'])  # docs: "enabled": true, for every profile
        self.assertEqual(undefined, [])

    def test_the_person_turns_servers_on_and_off(self):
        servers, _ = self.resolve(['bigquery', 'dbt'], {'dbt': False, 'github': True, 'docs': False})
        self.assertEqual(sorted(servers), ['bigquery', 'github'])
        self.assertEqual(servers['github']['command'], 'docker')  # "github": true keeps the organization's definition

    def test_the_person_adds_a_server_of_their_own(self):
        servers, _ = self.resolve([], {'mine': {'server': {'command': 'my-mcp', 'env': {'TOKEN': '${MY_TOKEN}'}}}})
        self.assertEqual(servers['mine']['command'], 'my-mcp')
        servers, _ = self.resolve([], {'mine': {'enabled': False, 'server': {'command': 'my-mcp'}}})
        self.assertNotIn('mine', servers)

    def test_older_personal_format_still_works(self):
        servers, _ = self.resolve([], {'dbt': {'enabled': True}, 'old': {'enabled': True, 'server': {'command': 'x'}}})
        self.assertEqual(sorted(servers), ['dbt', 'docs', 'old'])

    def test_a_name_without_definition_is_reported_not_installed(self):
        servers, undefined = cli.resolve_mcp({}, ['bigquery'], {'github': True})
        self.assertEqual((servers, undefined), ({}, ['bigquery', 'github']))

    def test_invalid_entries_refused(self):
        for org, profile, personal in (({'x': True}, [], {}), ({}, {'recommended': []}, {}), ({}, [], {'x': 'yes'}),
                                       ({}, [], {'x': {'server': {'httpUrl': 'http://plain.example.org'}}})):
            with self.assertRaises(KitError):
                cli.resolve_mcp(org, profile, personal)

    def test_installed_from_the_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home/'.ai-kit').mkdir()
            (home/'.ai-kit/overrides.json').write_text(json.dumps({'mcp': {'dbt': False, 'github': True}}), encoding='utf-8')
            real = cli.read_json
            org = {'defaults': {'mcp': self.ORG}}
            with mock.patch.object(cli, 'read_json', side_effect=lambda p, d=None: org if Path(p).name == 'organization.json' else real(p, d)), \
                 contextlib.redirect_stdout(io.StringIO()):
                apply('data-analyst', home, False, IDENTITY, 'gemini')
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    doctor(home)
            installed = read_json(home/'.gemini/settings.json')['mcpServers']
            self.assertEqual(sorted(installed), ['ai-kit-bigquery', 'ai-kit-docs', 'ai-kit-github'])
            self.assertIn('[Info] MCP servers: bigquery, docs, github', out.getvalue())
            self.assertNotIn('changes organization defaults', out.getvalue())


@unittest.skipIf(os.name == 'nt' or not shutil.which('git') or not wheelhouse.AVAILABLE, 'POSIX launcher, git and a local wheelhouse required')
class UpdatePullsTests(unittest.TestCase):
    def git(self, *args, cwd):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)

    def test_update_fetches_the_new_version_and_respects_local_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # A fresh repository built from the current files: independent of how CI checked the kit out
            # (a tag gives a detached HEAD with a single commit, which cannot be pushed as is).
            dev = base/'dev'
            files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
            for rel in files:
                if (ROOT/rel).is_file():
                    (dev/rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT/rel, dev/rel)
            self.git('init', '--quiet', '-b', 'main', cwd=dev)
            self.git('config', 'user.email', 'test@example.org', cwd=dev)
            self.git('config', 'user.name', 'Test', cwd=dev)
            self.git('add', '-A', cwd=dev)
            self.git('commit', '--quiet', '-m', 'kit', cwd=dev)
            self.git('init', '--quiet', '--bare', '-b', 'main', str(base/'remote.git'), cwd=base)
            self.git('remote', 'add', 'origin', str(base/'remote.git'), cwd=dev)
            self.git('push', '--quiet', 'origin', 'main', cwd=dev)
            self.git('clone', '--quiet', str(base/'remote.git'), str(base/'kit'), cwd=base)
            (base/'dev/NEW_FILE.md').write_text('new\n', encoding='utf-8')
            self.git('add', 'NEW_FILE.md', cwd=base/'dev')
            self.git('commit', '--quiet', '-m', 'new', cwd=base/'dev')
            self.git('push', '--quiet', 'origin', 'main', cwd=base/'dev')
            home = base/'home'
            env = {**{k: v for k, v in os.environ.items() if not k.startswith('PIP_')}, **wheelhouse.pip_env()}
            run = lambda action, *extra: subprocess.run(['sh', str(base/'kit/scripts/bootstrap.sh'), action, *extra, '--home', str(home), '--no-live'],
                                                        capture_output=True, text=True, encoding='utf-8', cwd=base, env=env)
            self.assertEqual(run('setup', '--profile', 'general', '--user', 'a@example.org').returncode, 0)
            proc = run('update')
            self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)
            self.assertTrue((base/'kit/NEW_FILE.md').is_file())
            # A local change in the kit folder: no pull, the configuration is reapplied, and the update is reported
            # incomplete (0.34: before, it ended with code 0 as if the new version had been fetched).
            (base/'kit/README.md').write_text('changed\n', encoding='utf-8')
            proc = run('update')
            self.assertEqual(proc.returncode, 1, proc.stdout+proc.stderr)
            self.assertIn('local changes', proc.stdout)
            self.assertIn('Update incomplete', proc.stdout)
            self.assertEqual((base/'kit/README.md').read_text(encoding='utf-8'), 'changed\n')


if __name__ == '__main__':
    unittest.main()
