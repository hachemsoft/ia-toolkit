"""4.24.1: what IT writes in managed.toml holds on every path. teams.allow_unknown is not bypassed by a URL the person
gives; teams.allowed and git.allowed_hosts match a URL however it is written; a managed.toml that is a broken link, a
reparse point or replaceable by the current user is refused, and an elevated administrator is not; [frictions.tracker] is
validated as soon as the file is read; a lock file left empty does not block every command; a Team skill may require a Core
skill; the release check runs Git like every other source; a pending backup is put back only from a folder the kit made,
inside the home folder. Temporary folders and local repositories only: no network, no model."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from installer import commit, config, doctor, sources, sync, validate
from installer.core import KitError
from installer.toml_files import dump_toml, read_toml
import test_team_use

TRUSTED = 'S-1-5-32-544'
SKILL = ('---\nname: data-check\ndescription: "Check a data change. Triggers: data check."\nmetadata:\n  aikit-version: "1.0.0"\n'
         '  aikit-origin: "team"\n  aikit-category: "domain"\n  aikit-requires: "{requires}"\n---\n\n# data-check\n\nCheck it.\n')


class UnknownTeamTests(unittest.TestCase):
    setUp, commit_tag, use = (test_team_use.TeamTests.setUp, test_team_use.TeamTests.commit_tag, test_team_use.TeamTests.use)

    def state(self):
        return json.loads((self.kit/'state.json').read_text(encoding='utf-8'))

    def forbid_unknown(self):
        self.managed.write_text(dump_toml({'managed_schema': 1, 'teams': {'allow_unknown': False}}), encoding='utf-8')

    def test_a_url_on_the_command_line_does_not_bypass_allow_unknown(self):
        self.forbid_unknown()
        with self.assertRaises(sources.SourceError) as caught:
            self.use('data', self.url)
        self.assertEqual(caught.exception.kind, 'refused-origin')
        self.assertIn('allow_unknown', str(caught.exception))
        self.assertFalse((self.kit/'lock.toml').exists())

    def test_a_url_in_aikit_toml_does_not_bypass_allow_unknown(self):
        self.forbid_unknown()
        (self.kit/'aikit.toml').write_text(dump_toml({'schema': 1, 'teams': {'data': {'repo': self.url}}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError) as caught:
            self.use('data')
        self.assertIn('allow_unknown', str(caught.exception))
        self.assertFalse((self.kit/'lock.toml').exists())

    def test_a_team_already_known_stays_usable(self):
        self.use('data', self.url)
        self.use('none')
        self.forbid_unknown()
        self.use('data')
        self.assertEqual(read_toml(self.kit/'lock.toml')['sources']['team']['name'], 'data')

    def test_a_team_skill_may_require_a_core_skill(self):
        (self.work/'skills/data-check/SKILL.md').write_text(SKILL.format(requires='tdd'), encoding='utf-8')
        self.commit_tag('v1.1.0', push=True)
        self.assertEqual([p for p in validate.problems(self.work, '99.0.0') if 'requires' in p], [])
        self.use('data', self.url)
        self.assertIn('data-check', self.state()['installed']['skills'])

    def test_a_team_skill_that_requires_a_skill_nobody_has_is_still_refused(self):
        (self.work/'skills/data-check/SKILL.md').write_text(SKILL.format(requires='no-such-skill'), encoding='utf-8')
        self.commit_tag('v1.1.0', push=True)
        self.assertTrue([p for p in validate.problems(self.work, '99.0.0') if 'no-such-skill' in p])
        with self.assertRaises(KitError) as caught:
            self.use('data', self.url)
        self.assertIn('no-such-skill', str(caught.exception))


class AllowListTests(unittest.TestCase):
    def allowed(self, url, entries):
        try:
            sync.check_team_allowed(url, {'teams': {'allowed': entries}})
            return True
        except sources.SourceError:
            return False

    def test_teams_allowed_matches_a_url_however_it_is_written(self):
        https, ssh = 'https://git.example.org/teams/data.git', 'ssh://git@git.example.org/teams/data.git'
        for entry in ('https://git.example.org/teams/data.git', 'https://git.example.org/teams/data', 'https://git.example.org/teams/data/',
                      'https://GIT.Example.org/teams/', 'https://git.example.org/teams', ' https://git.example.org/teams/data.git '):
            self.assertTrue(self.allowed(https, [entry]), entry)
        for entry in ('git@git.example.org:teams/data.git', 'git@git.example.org:teams/data', 'git@git.example.org:teams', 'ssh://git@git.example.org/teams/'):
            self.assertTrue(self.allowed(ssh, [entry]), entry)
        for entry in ('https://git.example.org/teams/dat', 'https://git.example.org/team', 'https://git.example.org.evil.test/teams/',
                      'git@git.example.org:teams/data', 'https://other.example.org/teams/data.git'):
            self.assertFalse(self.allowed(https, [entry]), entry)
        self.assertFalse(self.allowed(https, []))

    def test_allowed_hosts_ignore_case(self):
        sources.authorize('https://git.example.org/group/core.git', {'allowed_hosts': ['Git.Example.ORG'], 'allowed_groups': None})
        with self.assertRaises(sources.SourceError):
            sources.authorize('https://git.example.org/group/core.git', {'allowed_hosts': ['Other.Example.ORG'], 'allowed_groups': None})


class ManagedFileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name).resolve()
        self.path = self.folder/'managed.toml'

    def test_a_broken_link_is_refused_not_read_as_not_administered(self):
        try:
            os.symlink(self.folder/'gone.toml', self.path)
        except (OSError, NotImplementedError):
            self.skipTest('no symbolic link on this system')
        with self.assertRaises(config.ManagedConfigError):
            config.load_managed(self.path)

    def windows(self, elevated=False, links=(), openable=(), owners=None):
        """windows_file_problem with the workstation's answers given: the paths that are reparse points, the (path, right)
        the current user can open, the owner of each path."""
        owners = owners or {self.path: TRUSTED, self.folder: TRUSTED}
        with mock.patch.object(config, 'windows_reparse_point', lambda p: Path(p) in links), \
                mock.patch.object(config, 'windows_elevated', lambda: elevated), \
                mock.patch.object(config, 'windows_can_open', lambda p, right: (Path(p), right) in openable), \
                mock.patch.object(config, 'windows_owner', lambda p: owners.get(Path(p))):
            return config.windows_file_problem(self.path)

    def test_windows_refuses_a_link_and_a_file_the_current_user_can_replace(self):
        self.assertIsNone(self.windows())
        self.assertIn('link', self.windows(links=[self.path]))
        self.assertIn('folder', self.windows(links=[self.folder]))
        self.assertIn('write', self.windows(openable=[(self.path, 'write')]))
        self.assertIn('delete', self.windows(openable=[(self.path, 'delete')]))
        problem = self.windows(openable=[(self.folder, 'delete-child')])
        self.assertIn('folder', problem)
        self.assertIn('delete', problem)
        self.assertIn('owned by', self.windows(owners={self.path: 'S-1-5-21-1-2-3-1001', self.folder: TRUSTED}))  # attrib +R is not ownership
        self.assertIn('folder is owned by', self.windows(owners={self.path: TRUSTED, self.folder: 'S-1-5-21-1-2-3-1001'}))

    def test_windows_does_not_block_an_elevated_administrator(self):
        everything = [(self.path, 'write'), (self.path, 'delete'), (self.folder, 'delete-child')]
        self.assertIsNone(self.windows(elevated=True, openable=everything))
        self.assertIn('link', self.windows(elevated=True, links=[self.path]))  # a link is refused for everyone
        self.assertIn('owned by', self.windows(elevated=True, owners={self.path: 'S-1-5-21-1-2-3-1001', self.folder: TRUSTED}))

    def test_the_friction_tracker_is_validated_when_the_file_is_read(self):
        cases = ({'kind': 'jira', 'project': 'group/project'}, {'kind': 'gitlab'}, {'kind': 'gitlab', 'project': 'https://x/group/project'},
                 {'kind': 'gitlab', 'project': 'group/project', 'host': 'https://gitlab.example.org'},
                 {'kind': 'gitlab', 'project': 'group/project', 'labels': 'friction'}, {'kind': 'gitlab', 'project': 'group/project', 'sources': []})
        with mock.patch.object(config, 'ownership_problem', return_value=None):
            for tracker in cases:
                self.path.write_text(dump_toml({'managed_schema': 1, 'frictions': {'tracker': tracker}}), encoding='utf-8')
                with self.assertRaises(config.ManagedConfigError, msg=str(tracker)) as caught:
                    config.load_managed(self.path)
                self.assertIn('frictions.tracker', str(caught.exception))
            self.path.write_text(dump_toml({'managed_schema': 1, 'frictions': {'tracker': {'kind': 'gitlab', 'project': 'group/project'}}}), encoding='utf-8')
            self.assertEqual(config.load_managed(self.path)['frictions']['tracker']['kind'], 'gitlab')


class EngineLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.kit = Path(temp.name).resolve()
        self.lock = self.kit/'engine.lock'

    def test_an_empty_lock_left_behind_is_taken_over(self):
        for content in ('', '0', '-4'):
            self.lock.write_text(content, encoding='utf-8')
            old = time.time() - 120
            os.utime(self.lock, (old, old))
            with mock.patch.object(sources.os, 'kill', side_effect=AssertionError('a pid of 0 or less must never be probed')):
                with sources.EngineLock(self.kit):
                    self.assertEqual(self.lock.read_text(encoding='utf-8'), str(os.getpid()))
            self.assertFalse(self.lock.exists())

    def test_a_lock_just_created_and_not_yet_written_is_not_stolen(self):
        self.lock.write_text('', encoding='utf-8')  # another command is between creating the file and writing its pid
        with self.assertRaises(KitError):
            with sources.EngineLock(self.kit):
                pass
        self.assertTrue(self.lock.exists())


class ReleaseCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home, self.clone = self.base/'home', self.base/'kit'
        (self.clone/'.git').mkdir(parents=True)
        (self.clone/'VERSION').write_text('1.0.0\n', encoding='utf-8')
        self.calls = []

    def check(self, origin, managed=None):
        """release_check with Git answered by a stand-in: the origin's URL, then its tags. Returns what was printed."""
        def run(command, **options):
            self.calls.append((command, options.get('env') or {}))
            out = b''
            if 'remote.origin.url' in command:
                out = origin.encode()+b'\n'
            elif '--get-url' in command:
                out = command[-1].encode()+b'\n'
            elif 'ls-remote' in command:
                out = b'aaa\trefs/tags/v1.0.0\nbbb\trefs/tags/v1.10.0\nccc\trefs/tags/v1.10.0^{}\nddd\trefs/tags/not-a-version\n'
            return subprocess.CompletedProcess(command, 0, stdout=out, stderr=b'')
        managed_file = self.base/'managed.toml'
        if managed:
            managed_file.write_text(dump_toml(managed), encoding='utf-8')
        out = io.StringIO()
        with mock.patch.object(doctor, 'source_folder', return_value=self.clone), mock.patch.object(doctor.shutil, 'which', return_value='/usr/bin/git'), \
                mock.patch.object(sources.subprocess, 'run', side_effect=run), mock.patch.object(config, 'ownership_problem', return_value=None), \
                mock.patch.dict(os.environ, {'GIT_SSH_COMMAND': 'ssh -o ProxyCommand=evil', 'GIT_CONFIG_GLOBAL': '/tmp/evil.gitconfig'}), \
                contextlib.redirect_stdout(out):
            doctor.release_check(self.home, managed_file)
        return out.getvalue()

    def test_git_runs_with_the_neutral_environment_of_every_source(self):
        said = self.check('https://git.example.org/group/ai-kit.git')
        self.assertIn('AI Kit 1.10.0 is published', said)
        self.assertTrue(any('ls-remote' in command for command, _ in self.calls))
        for command, env in self.calls:
            self.assertNotIn('GIT_SSH_COMMAND', env, command)
            self.assertNotEqual(env.get('GIT_CONFIG_GLOBAL'), '/tmp/evil.gitconfig', command)
            self.assertNotIn('fetch', command)  # a fetch writes the clone and runs what its configuration names

    def test_an_origin_it_does_not_allow_is_not_contacted(self):
        said = self.check('https://git.example.org/group/ai-kit.git', {'managed_schema': 1, 'git': {'allowed_hosts': ['git.allowed.example']}})
        self.assertEqual(said, '')
        self.assertFalse([command for command, _ in self.calls if 'ls-remote' in command])
        self.calls.clear()
        self.assertEqual(self.check('ext::sh -c "touch /tmp/x"'), '')  # not an https or ssh URL: never handed to Git
        self.assertFalse([command for command, _ in self.calls if 'ls-remote' in command])


class ResumeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base/'home'
        self.kit = self.home/'.ai-kit'
        (self.kit/'backups').mkdir(parents=True)
        (self.kit/'lock.toml').write_text('current = 1\n', encoding='utf-8')

    def pending(self, name, files, created=()):
        backup = self.kit/'backups'/name
        for rel, text in files.items():
            (backup/rel).parent.mkdir(parents=True, exist_ok=True)
            (backup/rel).write_text(text, encoding='utf-8')
        backup.mkdir(parents=True, exist_ok=True)
        (backup/'manifest.json').write_text(json.dumps({'status': 'pending', 'created': list(created)}), encoding='utf-8')
        return backup

    def test_a_folder_the_kit_did_not_make_is_never_put_back(self):
        self.pending('zzz-planted', {'.ai-kit/lock.toml': 'planted = 1\n'})  # sorts after every dated backup
        self.assertIsNone(commit.resume_pending(self.home, self.kit))
        self.assertEqual((self.kit/'lock.toml').read_text(encoding='utf-8'), 'current = 1\n')
        backup = self.pending('20261122T101500000000-ab12cd34', {'.ai-kit/lock.toml': 'previous = 1\n'})
        self.assertEqual(commit.resume_pending(self.home, self.kit), backup)
        self.assertEqual((self.kit/'lock.toml').read_text(encoding='utf-8'), 'previous = 1\n')

    def test_a_created_path_outside_the_home_folder_is_not_removed(self):
        outside = self.base/'outside.txt'
        outside.write_text('mine', encoding='utf-8')
        self.pending('20261122T101500000000-ab12cd34', {'.ai-kit/lock.toml': 'previous = 1\n'}, created=['../outside.txt'])
        with self.assertRaises(KitError):
            commit.resume_pending(self.home, self.kit)
        self.assertEqual(outside.read_text(encoding='utf-8'), 'mine')
        self.assertEqual((self.kit/'lock.toml').read_text(encoding='utf-8'), 'current = 1\n')  # checked before any write

    def test_a_link_in_a_path_to_put_back_stops_the_restoration(self):
        elsewhere = self.base/'elsewhere'
        elsewhere.mkdir()
        try:
            os.symlink(elsewhere, self.home/'.claude', target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('no symbolic link on this system')
        self.pending('20261122T101500000000-ab12cd34', {'.claude/settings.json': '{"planted": true}\n', '.ai-kit/lock.toml': 'previous = 1\n'})
        with self.assertRaises(KitError):
            commit.resume_pending(self.home, self.kit)
        self.assertFalse((elsewhere/'settings.json').exists())
        self.assertEqual((self.kit/'lock.toml').read_text(encoding='utf-8'), 'current = 1\n')


if __name__ == '__main__':
    unittest.main()
