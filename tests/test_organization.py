"""The settings layers (AI Kit 3, no organization.toml): the Core's MCP servers (mcp/servers.toml), a Team's [defaults], the
person's aikit.toml on top (lists add up, objects combine, the person wins), the team as its own dimension."""
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import cli, settings
from installer.cli import doctor, merge_settings, setting_differences
from installer.config import load_aikit, to_overrides
from installer.core import KitError, ROOT, read_json
from installer.toml_files import read_toml
from personal import write_personal
from presets import apply_as  # noqa: E402

IDENTITY = {'email': 'first.last@example.com', 'source': 'test'}


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def team(self, name, defaults):
        """Run with this Team [defaults] (teams/<name>.toml of the content the Team is overlaid on)."""
        real = settings.read_toml
        def patched(path, default=None):
            return defaults if Path(path).name == name+'.toml' and Path(path).parent.name == 'teams' else real(path, default)
        return mock.patch.object(settings, 'read_toml', side_effect=patched)

    def install(self, profile='general', team=None):
        with contextlib.redirect_stdout(io.StringIO()):
            apply_as(profile, self.home, False, IDENTITY, 'gemini', team)
        return read_json(self.home/'.ai-kit/state.json')

    def personal(self, overrides):
        write_personal(self.home, overrides)

    def test_merge_adds_lists_combines_objects_person_wins(self):
        org = {'extra_skills': ['a'], 'hooks': {'dbt-prod-guard': True}, 'model': 'm1', '_doc': 'x'}
        person = {'extra_skills': ['b', 'a'], 'hooks': {'protected-paths': False}, 'model': 'm2', '_doc': 'y'}
        self.assertEqual(merge_settings(org, person),
                         {'extra_skills': ['a', 'b'], 'hooks': {'dbt-prod-guard': True, 'protected-paths': False}, 'model': 'm2'})
        self.assertEqual(setting_differences(org, merge_settings(org, person)), ['model'])

    def test_team_defaults_survive_a_personal_file(self):
        # A personal file never replaces the layers below it wholesale.
        self.personal({'extra_skills': ['teach']})
        with self.team('data-platform', {'hooks': {'dbt-prod-guard': True}}):
            state = self.install(team='data-platform')
        self.assertIn('dbt-prod-guard', state['hooks'])
        self.assertIn('protected-paths', state['hooks'])

    def test_person_can_turn_off_a_team_default(self):
        self.personal({'hooks': {'dbt-prod-guard': False}})
        with self.team('data-platform', {'hooks': {'dbt-prod-guard': True}}):
            state = self.install(team='data-platform')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                doctor(self.home)
        self.assertNotIn('dbt-prod-guard', state['hooks'])
        self.assertIn('Your aikit.toml changes the Core or Team defaults: hooks.dbt-prod-guard', out.getvalue())

    def test_team_selects_its_practices_whatever_the_profile(self):
        team_file = ROOT/'context/20-kit-test-team.md'
        team_file.write_text('# Test team practices\n- Rule of the test team.\n', encoding='utf-8')
        self.addCleanup(team_file.unlink)
        state = self.install('java-developer', team='kit-test-team')
        self.assertEqual(state['team'], 'kit-test-team')
        self.assertTrue((self.home/'.gemini/20_KIT_TEST_TEAM.md').is_file())
        self.assertFalse((self.home/'.gemini/20_TEAM.md').exists())
        # Kept for update, without --team.
        self.assertEqual(self.install('java-developer')['team'], 'kit-test-team')

    def test_team_none_leaves_the_team(self):
        team_file = ROOT/'context/20-kit-test-team.md'
        team_file.write_text('# Test team practices\n', encoding='utf-8')
        self.addCleanup(team_file.unlink)
        self.install('general', team='kit-test-team')
        state = self.install('general', team='none')
        self.assertIsNone(state['team'])
        self.assertTrue((self.home/'.gemini/20_TEAM.md').is_file())
        self.assertFalse((self.home/'.gemini/20_KIT_TEST_TEAM.md').exists())

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

    def test_the_installer_reads_exactly_the_keys_aikit_toml_gives(self):
        code = ''.join(f.read_text(encoding='utf-8') for f in (ROOT/'installer').rglob('*.py'))
        read = set(re.findall(r"(?:overrides|personal)(?:\.get\(|\[)'([a-z_]+)'", code))
        lists = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
        full = {'schema': 1, 'user': {**{k: ['x'] for k in lists}, 'skill_prefix': 'ai-kit-'}, 'hooks': {'dbt-prod-guard': True},
                'mcp': {'enabled': ['docs']}, 'frictions': {'capture': 'off', 'publication': 'disabled'}}
        self.assertEqual(read, set(to_overrides(full)))
        self.assertEqual(cli.unknown_keys(to_overrides(full)), [])

    def test_shipped_files_follow_the_schemas(self):
        self.assertFalse((ROOT/'organization.toml').exists())  # not in the Core (managed.toml, mcp/servers.toml, Team repos)
        template = (ROOT/'templates/user-aikit.toml').read_text(encoding='utf-8')
        self.assertTrue((ROOT/'templates'/re.search(r'(?m)^#:schema (.+)$', template).group(1).strip()).is_file())
        self.assertEqual(read_toml(ROOT/'templates/user-aikit.toml'), {'schema': 1})  # nothing set for the person
        # Every example of the template, uncommented, is a valid setting without a warning.
        examples = '\n'.join(line[2:] for line in template.splitlines() if line.startswith('# ') and ('=' in line or line.startswith('# [')))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'aikit.toml'
            path.write_text('schema = 1\n'+examples+'\n', encoding='utf-8')
            data, warnings = load_aikit(path)
        self.assertEqual(warnings, [])
        self.assertTrue(data.get('user') and data.get('hooks') and data.get('mcp') and data.get('frictions') and data.get('core'), data)

    def test_personal_file_points_to_the_schema_and_typos_are_reported(self):
        self.install()
        uri = re.search(r'(?m)^#:schema (.+)$', (self.home/'.ai-kit/aikit.toml').read_text(encoding='utf-8')).group(1).strip()
        from urllib.parse import urlparse, unquote
        target = Path(unquote(urlparse(uri).path.lstrip('/') if os.name == 'nt' else unquote(urlparse(uri).path)))
        self.assertTrue(target.is_file(), uri)
        (self.home/'.ai-kit/aikit.toml').write_text('schema = 1\n[user]\nextra_skill = ["teach"]\n', encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            doctor(self.home)
        self.assertIn('unknown key user.extra_skill', out.getvalue())
        self.assertEqual(merge_settings({}, {'$schema': 'x', 'model': 'm'}), {'model': 'm'})

class TeamToolsTests(unittest.TestCase):
    """A Team's [defaults] brings its tools (same keys as aikit.toml), between the Core and the person; the Core's
    mcp/servers.toml says how to reach each server."""
    SERVERS = {'servers': {'dbt': {'command': 'dbt-mcp'}, 'github': {'command': 'gh-mcp'}}}
    TEAM = {'extra_skills': ['prototype'], 'extra_commands': ['ask'], 'mcp': {'dbt': True}, 'hooks': {'dbt-prod-guard': True}}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def layers(self, path, default=None, real=settings.read_toml):
        path = Path(path)
        if path.name == 'servers.toml' and path.parent.name == 'mcp':
            return self.SERVERS
        if path.name == 'data-platform.toml' and path.parent.name == 'teams':
            return self.TEAM
        return real(path, default)

    def install(self, team=None, personal=None, profile='general'):
        if personal is not None:
            write_personal(self.home, personal)
        with mock.patch.object(settings, 'read_toml', side_effect=self.layers), contextlib.redirect_stdout(io.StringIO()):
            apply_as(profile, self.home, False, IDENTITY, 'gemini', team)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                doctor(self.home)
        return read_json(self.home/'.ai-kit/state.json'), out.getvalue()

    def test_team_brings_skills_commands_guardrails_and_mcp(self):
        state, out = self.install('data-platform')
        skills = self.home/'.gemini/skills'
        self.assertTrue((skills/'prototype').is_dir())   # team
        self.assertTrue((self.home/'.gemini/commands/ask.toml').is_file())
        self.assertIn('dbt-prod-guard', state['hooks'])
        self.assertEqual(list(state['mcp']), ['ai-kit-dbt'])
        # No context/20-data-platform.md: the shared team practices stay, the team is kept for the next run.
        self.assertEqual(state['team'], 'data-platform')
        self.assertIn('team', state['practices'])
        self.assertIn('[Info] Team: data-platform ([defaults])', out)
        self.assertIn('Team data-platform [defaults]: only known keys', out)

    def test_without_the_team_nothing_of_it(self):
        state, _ = self.install()
        self.assertFalse((self.home/'.gemini/skills/prototype').exists())
        self.assertEqual(state['mcp'], {})

    def test_the_person_still_has_the_last_word(self):
        state, out = self.install('data-platform', {'mcp': {'dbt': False, 'github': True}, 'disabled_skills': ['prototype']})
        self.assertEqual(list(state['mcp']), ['ai-kit-github'])
        self.assertFalse((self.home/'.gemini/skills/prototype').exists())


class McpTests(unittest.TestCase):
    """mcp/servers.toml says how to reach a server (enabled = true: for everyone), the Team and the person turn one on or off."""
    ORG = {'bigquery': {'server': {'httpUrl': 'https://bq.example.org/mcp'}},
           'dbt': {'server': {'command': 'dbt-mcp'}},
           'github': {'server': {'command': 'docker', 'args': ['run', '-i', '--rm', 'ghcr.io/github/github-mcp-server:1.0.0']}},
           'docs': {'enabled': True, 'server': {'httpUrl': 'https://docs.example.org/mcp'}}}

    def resolve(self, profile, personal=None):
        return cli.resolve_mcp(self.ORG, profile, personal or {})

    def test_a_selection_chooses_among_the_core_servers(self):
        servers, undefined = self.resolve(['bigquery', 'dbt'])
        self.assertEqual(sorted(servers), ['bigquery', 'dbt', 'docs'])  # docs: "enabled": true, for every profile
        self.assertEqual(undefined, [])

    def test_the_person_turns_servers_on_and_off(self):
        servers, _ = self.resolve(['bigquery', 'dbt'], {'dbt': False, 'github': True, 'docs': False})
        self.assertEqual(sorted(servers), ['bigquery', 'github'])
        self.assertEqual(servers['github']['command'], 'docker')  # "github": true keeps the organization's definition

    def test_a_name_without_definition_is_reported_not_installed(self):
        servers, undefined = cli.resolve_mcp({}, ['bigquery'], {'github': True})
        self.assertEqual((servers, undefined), ({}, ['bigquery', 'github']))

    def test_invalid_entries_refused(self):
        for org, profile, personal in (({'x': True}, [], {}), ({}, {'recommended': []}, {}), ({}, [], {'x': 'yes'}),
                                       ({}, [], {'x': {'server': {'httpUrl': 'http://plain.example.org'}}})):
            with self.assertRaises(KitError):
                cli.resolve_mcp(org, profile, personal)

    def test_installed_from_the_core_servers_and_aikit_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # no profile turns bigquery on; the person does.
            write_personal(home, {'mcp': {'bigquery': True, 'dbt': False, 'github': True}})
            real = settings.read_toml
            servers = {'servers': {n: {**{k: v for k, v in e.items() if k != 'server'}, **e['server']} for n, e in self.ORG.items()}}
            with mock.patch.object(settings, 'read_toml', side_effect=lambda p, d=None: servers if Path(p).name == 'servers.toml' else real(p, d)), \
                 contextlib.redirect_stdout(io.StringIO()):
                apply_as('data-analyst', home, False, IDENTITY, 'gemini')
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    doctor(home)
            installed = read_json(home/'.gemini/settings.json')['mcpServers']
            self.assertEqual(sorted(installed), ['ai-kit-bigquery', 'ai-kit-docs', 'ai-kit-github'])
            self.assertIn('[Info] MCP servers: bigquery, docs, github', out.getvalue())
            self.assertNotIn('changes the Core or Team defaults', out.getvalue())


if __name__ == '__main__':
    unittest.main()
