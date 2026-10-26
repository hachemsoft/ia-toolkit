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
        self.assertIn('Your overrides.json changes organization defaults: hooks.dbt-prod-guard', out.getvalue())

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
        read = set(re.findall(r"overrides(?:\.get\(|\[)'([a-z_]+)'", code))
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

@unittest.skipIf(os.name == 'nt' or not shutil.which('git'), 'POSIX launcher and git required')
class UpdatePullsTests(unittest.TestCase):
    def git(self, *args, cwd):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)

    def test_update_fetches_the_new_version_and_respects_local_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # A fresh repository built from the current files: independent of how CI checked the kit out
            # (a tag gives a detached HEAD with a single commit, which cannot be pushed as is).
            dev = base/'dev'
            files = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
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
            run = lambda action, *extra: subprocess.run(['sh', str(base/'kit/scripts/bootstrap.sh'), action, *extra, '--home', str(home), '--no-live'],
                                                        capture_output=True, text=True, encoding='utf-8', cwd=base)
            self.assertEqual(run('setup', '--profile', 'general', '--user', 'a@example.org').returncode, 0)
            proc = run('update')
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((base/'kit/NEW_FILE.md').is_file())
            # A local change in the kit folder: no pull, the update still runs.
            (base/'kit/README.md').write_text('changed\n', encoding='utf-8')
            proc = run('update')
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('Local changes in the kit folder', proc.stderr)


if __name__ == '__main__':
    unittest.main()
