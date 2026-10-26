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
        self.assertIn('line 2, column 29', message)
        self.assertIn('a comma is left before } or ]', message)
        self.assertIn('"extra_skills": ["a", "b",]', message)


@unittest.skipIf(os.name == 'nt' or not shutil.which('git'), 'POSIX launcher and git required')
class UpdatePullsTests(unittest.TestCase):
    def git(self, *args, cwd):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)

    def test_update_fetches_the_new_version_and_respects_local_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.git('clone', '--quiet', '--bare', str(ROOT), str(base/'remote.git'), cwd=base)
            self.git('clone', '--quiet', str(base/'remote.git'), str(base/'dev'), cwd=base)
            self.git('config', 'user.email', 'test@example.org', cwd=base/'dev')
            self.git('config', 'user.name', 'Test', cwd=base/'dev')
            # The launcher under test is the current one, committed or not: publish it first.
            shutil.copy(ROOT/'scripts/bootstrap.sh', base/'dev/scripts/bootstrap.sh')
            self.git('commit', '--quiet', '--allow-empty', '-am', 'current launcher', cwd=base/'dev')
            self.git('push', '--quiet', 'origin', 'HEAD', cwd=base/'dev')
            self.git('clone', '--quiet', str(base/'remote.git'), str(base/'kit'), cwd=base)
            (base/'dev/NEW_FILE.md').write_text('new\n', encoding='utf-8')
            self.git('add', 'NEW_FILE.md', cwd=base/'dev')
            self.git('commit', '--quiet', '-m', 'new', cwd=base/'dev')
            self.git('push', '--quiet', 'origin', 'HEAD', cwd=base/'dev')
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
