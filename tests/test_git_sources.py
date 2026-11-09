"""V2 slice 2 (ADR 0016, docs/v2/git-sync.md): Git sources, lock.toml, sync, rollback, resume. Local bare repositories only:
installer.sources.LOCAL_FOR_TESTS lets file:// through, by patching, never from the environment. No network."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, sources, sync
from installer.core import ROOT, KitError
from installer.toml_files import dump_toml, read_toml

CONTENT = ('skills', 'agents', 'commands', 'context', 'templates')
GIT_ENV = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.org',
           'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@example.org'}
HAS_GIT = shutil.which('git') is not None


def remove_repository(path):
    """shutil.rmtree for a Git repository: on Windows, Git leaves its object files read-only, which rmtree cannot delete."""
    def writable(function, target, _):
        os.chmod(target, stat.S_IWRITE)
        function(target)
    shutil.rmtree(path, onexc=writable) if sys.version_info >= (3, 12) else shutil.rmtree(path, onerror=writable)


def run_git(*args, cwd):
    return subprocess.run(['git', '-c', 'init.defaultBranch=main', '-c', 'core.autocrlf=false', *args], cwd=cwd, env=GIT_ENV, check=True,
                          capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(HAS_GIT, 'git not installed')
class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base/'home'
        self.kit = self.home/'.ai-kit'
        self.kit.mkdir(parents=True)
        self.work = self.base/'core-work'
        for name in CONTENT:
            (shutil.copytree if (ROOT/name).is_dir() else shutil.copy2)(ROOT/name, self.work/name)
        (self.work/'aikit.toml').write_text('schema = 1\nname = "core"\nkind = "core"\nmin_engine = "2.0.0"\n', encoding='utf-8')
        run_git('init', '-q', cwd=self.work)
        self.release('v1.0.0', 'Marker v1.0.0.')
        self.bare = self.base/'core.git'
        run_git('clone', '-q', '--bare', str(self.work), str(self.bare), cwd=self.base)
        self.url = 'file://'+self.bare.resolve().as_posix()
        for patcher in (mock.patch.object(sources, 'LOCAL_FOR_TESTS', True), mock.patch('installer.config.ownership_problem', return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.kit/'aikit.toml').write_text(dump_toml({'schema': 1, 'core': {'repo': self.url}}), encoding='utf-8')
        self.managed = self.base/'managed.toml'
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'claude', managed_file=self.managed)

    def release(self, tag, marker, push=False):
        skill = self.work/'skills/internal/common/tdd/SKILL.md'
        text = skill.read_text(encoding='utf-8').split('\nMarker ')[0]
        skill.write_text(text+'\n'+marker+'\n', encoding='utf-8')
        run_git('add', '-A', cwd=self.work)
        run_git('commit', '-q', '-m', tag, cwd=self.work)
        run_git('tag', '-a', tag, '-m', tag, cwd=self.work)
        if push:
            run_git('push', '-q', str(self.bare), 'main', tag, cwd=self.work)

    def run_action(self, action, dry_run=False, confirm=True, team=None, url=None):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with sync.activation(self.home, action, dry_run, (lambda q: confirm), managed_file=self.managed, team_name=team, team_url=url) as act:
                cli.apply('general', self.home, dry_run, None, 'claude', act.team, extra_writes=act.writes, managed_file=self.managed)
        return out.getvalue()

    def installed(self):
        return (self.home/'.claude/skills/ai-kit-tdd/SKILL.md').read_text(encoding='utf-8')

    def lock(self):
        return read_toml(self.kit/'lock.toml', {})


class SyncTests(Base):
    def test_sync_installs_the_tag_and_update_keeps_it(self):
        out = self.run_action('sync')
        self.assertIn('Core v1.0.0', out)
        self.assertIn('Marker v1.0.0.', self.installed())
        core = self.lock()['sources']['core']
        self.assertEqual((core['tag'], core['url']), ('v1.0.0', self.url))
        self.assertEqual(len(core['commit']), 40)
        state = json.loads((self.kit/'state.json').read_text(encoding='utf-8'))
        self.assertEqual(len(state['lock']), 64)
        self.run_action('update')
        self.assertIn('Marker v1.0.0.', self.installed())  # update reads the locked Core, not the package

    def test_a_plain_reapply_keeps_the_locked_core(self):
        # The guided installer and the re-apply after /me call apply() directly: they must not fall back to the package content.
        self.run_action('sync')
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'claude', managed_file=self.managed)
        self.assertIn('Marker v1.0.0.', self.installed())

    def test_init_installs_then_syncs_the_core(self):
        home = self.base/'fresh'
        (home/'.ai-kit').mkdir(parents=True)
        (home/'.ai-kit/aikit.toml').write_text(dump_toml({'schema': 1, 'core': {'repo': self.url}}), encoding='utf-8')
        self.managed.write_text(dump_toml({'managed_schema': 1, 'enterprise': {'core': self.url}}), encoding='utf-8')
        with mock.patch('installer.config.managed_path', return_value=self.managed), contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli.main(['init', '--home', str(home), '--target', 'claude', '--user', 'a@example.org'])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn('Marker v1.0.0.', (home/'.claude/skills/ai-kit-tdd/SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((home/'.ai-kit/state.json').read_text(encoding='utf-8'))['profile'], 'core')  # 2.2: no profiles

    def test_sync_from_the_command_line_and_offline(self):
        # ADR 0025: sync takes the highest tag; without network it fails and changes nothing; sync --offline re-applies.
        self.run_action('sync')
        self.release('v1.1.0', 'Marker v1.1.0.', push=True)
        base = ['--home', str(self.home), '--target', 'claude']
        with mock.patch('installer.config.managed_path', return_value=self.managed), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['sync', *base]), 0)
        self.assertIn('Marker v1.1.0.', self.installed())
        remove_repository(self.bare)
        with mock.patch('installer.config.managed_path', return_value=self.managed), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['sync', *base]), 1)
            self.assertEqual(cli.main(['sync', '--offline', *base]), 0)
        self.assertIn('Error:', err.getvalue())
        self.assertIn('Marker v1.1.0.', self.installed())

    def test_status_says_a_newer_core_was_seen(self):
        self.run_action('sync')
        (self.work/'aikit.toml').write_text('schema = 1\nname = "core"\nmin_engine = "99.0.0"\n', encoding='utf-8')
        self.release('v1.2.0', 'Marker v1.2.0.', push=True)
        with self.assertRaises(KitError):
            self.run_action('sync')  # refused, but the tag was seen
        from installer.status import status
        with mock.patch('installer.config.managed_path', return_value=self.managed), contextlib.redirect_stdout(io.StringIO()) as out:
            status(self.home)
        self.assertIn('A newer version was seen at the last sync: Core v1.2.0', out.getvalue())

    @unittest.skipUnless(shutil.which('ssh-keygen'), 'ssh-keygen not installed')
    def test_signed_tags_when_it_lists_signers(self):
        key = self.base/'release-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        public = (self.base/'release-key.pub').read_text(encoding='utf-8').strip()
        skill = self.work/'skills/internal/common/tdd/SKILL.md'
        skill.write_text(skill.read_text(encoding='utf-8')+'\nSigned release.\n', encoding='utf-8')
        run_git('commit', '-q', '-am', 'signed', cwd=self.work)
        run_git('-c', 'gpg.format=ssh', '-c', 'user.signingkey='+str(key)+'.pub', 'tag', '-s', 'v1.1.0', '-m', 'v1.1.0', cwd=self.work)
        run_git('push', '-q', str(self.bare), 'main', 'v1.1.0', cwd=self.work)
        self.managed.write_text(dump_toml({'managed_schema': 1, 'enterprise': {'core': self.url}, 'git': {'signers': [public]}}), encoding='utf-8')
        self.run_action('sync', confirm=False)
        self.assertIn('Signed release.', self.installed())
        self.release('v1.2.0', 'Marker v1.2.0.', push=True)  # not signed
        with self.assertRaises(sources.SourceError) as caught:
            self.run_action('sync', confirm=False)
        self.assertIn('not signed by a key IT lists', str(caught.exception))
        self.assertIn('Signed release.', self.installed())

    def test_a_branch_is_never_followed(self):
        self.run_action('sync')
        skill = self.work/'skills/internal/common/tdd/SKILL.md'
        skill.write_text(skill.read_text(encoding='utf-8')+'\nOn main only.\n', encoding='utf-8')
        run_git('commit', '-q', '-am', 'untagged', cwd=self.work)
        run_git('push', '-q', str(self.bare), 'main', cwd=self.work)
        self.assertIn('already active', self.run_action('sync'))
        self.assertNotIn('On main only.', self.installed())

    def test_new_tag_then_rollback_without_network_and_back(self):
        self.run_action('sync')
        self.release('v1.1.0', 'Marker v1.1.0.', push=True)
        self.run_action('sync')
        self.assertIn('Marker v1.1.0.', self.installed())
        self.assertEqual(self.lock()['previous']['sources']['core']['tag'], 'v1.0.0')
        remove_repository(self.bare)  # no remote any more: rollback uses the cache only
        self.run_action('rollback')
        self.assertIn('Marker v1.0.0.', self.installed())
        self.assertEqual((self.lock()['sources']['core']['tag'], self.lock()['previous']['sources']['core']['tag']), ('v1.0.0', 'v1.1.0'))
        self.run_action('rollback')
        self.assertIn('Marker v1.1.0.', self.installed())

    def test_a_moved_tag_blocks_and_changes_nothing(self):
        self.run_action('sync')
        before, lock = self.installed(), (self.kit/'lock.toml').read_bytes()
        run_git('tag', '-d', 'v1.0.0', cwd=self.work)
        skill = self.work/'skills/internal/common/tdd/SKILL.md'
        skill.write_text(skill.read_text(encoding='utf-8')+'\nRewritten.\n', encoding='utf-8')
        run_git('commit', '-q', '-am', 'rewrite', cwd=self.work)
        run_git('tag', '-a', 'v1.0.0', '-m', 'moved', cwd=self.work)
        run_git('push', '-q', '--force', str(self.bare), 'v1.0.0', cwd=self.work)
        with self.assertRaises(sources.SourceError) as caught:
            self.run_action('sync')
        self.assertEqual(caught.exception.kind, 'tag-moved')
        self.assertEqual((self.installed(), (self.kit/'lock.toml').read_bytes()), (before, lock))

    def test_a_failing_validation_changes_nothing(self):
        self.run_action('sync')
        before, lock = self.installed(), (self.kit/'lock.toml').read_bytes()
        (self.work/'aikit.toml').write_text('schema = 1\nname = "core"\nmin_engine = "99.0.0"\n', encoding='utf-8')
        self.release('v1.2.0', 'Marker v1.2.0.', push=True)
        with self.assertRaises(KitError) as caught:
            self.run_action('sync')
        self.assertIn('needs AI Kit 99.0.0', str(caught.exception))
        self.assertEqual((self.installed(), (self.kit/'lock.toml').read_bytes()), (before, lock))

    def test_dry_run_and_unconfirmed_first_use_write_nothing(self):
        self.run_action('sync', dry_run=True)
        self.assertFalse((self.kit/'lock.toml').exists())
        with self.assertRaises(KitError) as caught:
            self.run_action('sync', confirm=False)
        self.assertIn('needs your confirmation', str(caught.exception))
        self.assertFalse((self.kit/'lock.toml').exists())

    def test_managed_core_needs_no_confirmation_and_revocation_blocks_rollback(self):
        self.managed.write_text(dump_toml({'managed_schema': 1, 'enterprise': {'core': self.url}}), encoding='utf-8')
        self.run_action('sync', confirm=False)  # anchored by IT: no first-use question
        first = self.lock()['sources']['core']['commit']
        self.release('v1.1.0', 'Marker v1.1.0.', push=True)
        self.run_action('sync', confirm=False)
        self.managed.write_text(dump_toml({'managed_schema': 1, 'enterprise': {'core': self.url}, 'git': {'revoked': [first]}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError) as caught:
            self.run_action('rollback')
        self.assertEqual(caught.exception.kind, 'revoked')

    def test_an_origin_forbidden_since_is_refused(self):
        self.run_action('sync')
        self.managed.write_text(dump_toml({'managed_schema': 1, 'git': {'allowed_schemes': ['https']}}), encoding='utf-8')
        with mock.patch.object(sources, 'LOCAL_FOR_TESTS', False), self.assertRaises(sources.SourceError) as caught:
            self.run_action('update')
        self.assertEqual(caught.exception.kind, 'refused-origin')

    def test_an_interrupted_activation_is_put_back_at_the_next_start(self):
        self.run_action('sync')
        lock = (self.kit/'lock.toml').read_bytes()
        backup = self.kit/'backups'/'99991231T235959-cut'
        (backup/'.ai-kit').mkdir(parents=True)
        (backup/'.ai-kit/lock.toml').write_bytes(lock)
        (backup/'manifest.json').write_text(json.dumps({'status': 'pending', 'created': ['.ai-kit/half-written.txt']}), encoding='utf-8')
        (self.kit/'lock.toml').write_text('garbage = 1\n', encoding='utf-8')  # the cut happened mid-way
        (self.kit/'half-written.txt').write_text('x', encoding='utf-8')
        out = self.run_action('update')
        self.assertIn('was interrupted', out)
        self.assertEqual((self.kit/'lock.toml').read_bytes(), lock)
        self.assertFalse((self.kit/'half-written.txt').exists())
        self.assertEqual(json.loads((backup/'manifest.json').read_text(encoding='utf-8'))['status'], 'restored')

    def test_one_command_at_a_time_and_a_dead_lock_is_taken_over(self):
        with sources.EngineLock(self.kit):
            with self.assertRaises(KitError) as caught:
                self.run_action('update')
            self.assertIn('Another ai-kit command', str(caught.exception))
        (self.kit/'engine.lock').write_text('999999999', encoding='utf-8')  # no such process
        if os.name != 'nt':
            self.run_action('update')
            self.assertFalse((self.kit/'engine.lock').exists())


class ExtractionTests(Base):
    def extract_from(self, prepare):
        repo = self.base/'evil'
        repo.mkdir()
        run_git('init', '-q', cwd=repo)
        prepare(repo)
        run_git('add', '-A', cwd=repo)
        run_git('commit', '-q', '-m', 'x', cwd=repo)
        commit = run_git('rev-parse', 'HEAD', cwd=repo)
        return sources.extract(self.kit, repo/'.git', commit, self.base/'out')

    def test_a_symbolic_link_is_refused(self):
        if os.name == 'nt':
            self.skipTest('symbolic links need a privilege on Windows')
        with self.assertRaises(sources.SourceError) as caught:
            self.extract_from(lambda r: os.symlink('/etc/passwd', r/'link'))
        self.assertIn('symbolic link', str(caught.exception))

    def test_unsafe_paths_are_refused(self):
        seen = {}
        for path in ('a/../b', 'x/.GIT/config', 'aux.txt', 'c:/x', 'a\\b', 'trailing.', 'con'):
            with self.subTest(path=path), self.assertRaises(sources.SourceError):
                sources.safe_path(path, {})
        sources.safe_path('Skills/a.md', seen)
        with self.assertRaises(sources.SourceError):
            sources.safe_path('skills/b.md', seen)  # case collision

    def test_digest_is_the_same_from_the_tree_and_from_the_folder(self):
        digest = self.extract_from(lambda r: (r/'a.txt').write_text('hello\r\n', encoding='utf-8'))
        self.assertEqual(digest, sources.tree_digest(self.base/'out'))


class OriginTests(unittest.TestCase):
    def test_canonical_urls(self):
        c = sources.canonical_url
        self.assertEqual(c('https://GitLab.Example.org:443/ai-toolkit/core.git/'), 'https://gitlab.example.org/ai-toolkit/core.git')
        self.assertEqual(c('git@gitlab.example.org:ai-toolkit/core'), 'ssh://git@gitlab.example.org/ai-toolkit/core.git')
        for url in ('file:///tmp/x', 'git://h/a', 'ext::sh -c x', 'https://u:p@h/a', 'https://h/a/../b', 'https://h//a', 'ssh://bob@h/a', 'https://h/a?x=1', '/local/path'):
            with self.subTest(url=url), self.assertRaises(sources.SourceError):
                c(url)
        with self.assertRaises(sources.SourceError):
            c('ssh://git@h/a', schemes=('https',))

    def test_hosts_and_full_group_prefixes(self):
        git = {'allowed_hosts': ['gitlab.example.org'], 'allowed_groups': ['ai-toolkit/']}
        sources.authorize('https://gitlab.example.org/ai-toolkit/core.git', git)
        for url in ('https://evil.example.org/ai-toolkit/core.git', 'https://gitlab.example.org/ai-toolkit-evil/core.git'):
            with self.subTest(url=url), self.assertRaises(sources.SourceError):
                sources.authorize(url, git)

    def test_tag_choice(self):
        tags = {t: {} for t in ('v1.2.0', 'v1.10.0', 'v2.0.0-rc.1', 'v1.9.9')}
        self.assertEqual(sources.choose_tag(tags), 'v1.10.0')
        self.assertEqual(sources.choose_tag(tags, allow_prerelease=True), 'v2.0.0-rc.1')
        with self.assertRaises(sources.SourceError):
            sources.choose_tag({'v1.0.0': {}}, locked='v1.2.0')
        with self.assertRaises(sources.SourceError):
            sources.choose_tag({'main': {}, 'v1': {}})

    def test_credential_helper_from_a_closed_list(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home)/'.gitconfig'
            for value, expected in (('osxkeychain', 'osxkeychain'), ('manager', 'manager'), ('!f() { cat ~/.ssh/id; }; f', None), ('/tmp/evil', None)):
                config.write_text('[credential]\n\thelper = '+value+'\n', encoding='utf-8')
                self.assertEqual(sources.credential_helper(Path(home)), expected, value)

    @unittest.skipUnless(HAS_GIT, 'git not installed')
    def test_git_runs_without_the_person_s_global_config(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home)/'.gitconfig').write_text('[url "https://evil.example.org/"]\n\tinsteadOf = https://gitlab.example.org/\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'HOME': home, 'USERPROFILE': home}):
                out = sources.git(['config', '--global', '--list'], Path(home)/'.ai-kit', home=Path(home))
        self.assertEqual(out.strip(), b'')


if __name__ == '__main__':
    unittest.main()
