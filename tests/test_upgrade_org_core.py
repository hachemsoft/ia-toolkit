"""4.24.1: the installer of a release ZIP never replaces an organization's Core; a prerelease is older than its final
version; a dry run reads the person's Git settings; the Core a ZIP ships is read in a temporary folder and checked like any
other; ai-kit sync and team are never locked out by a Core that cannot be read; a cached tag that no longer points to the
locked commit is refused. Local repositories and bundles only: no network, no model."""
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from installer import bootstrap, cli, sources, sync
from installer.toml_files import dump_toml, read_toml
from test_git_sources import Base, remove_repository, run_git
import test_lifecycle_hardening
from test_lifecycle_hardening import GIT_ENV

NewerZip = test_lifecycle_hardening.NewerZipTests.__dict__  # its helpers, without collecting its tests here


class OlderTagTests(unittest.TestCase):
    def test_a_prerelease_is_older_than_its_final_version(self):
        self.assertTrue(cli.older_tag('v4.24.0-rc.1', '4.24.0'))
        self.assertTrue(cli.older_tag('v4.23.9', '4.24.0'))
        self.assertFalse(cli.older_tag('v4.24.0', '4.24.0'))
        self.assertFalse(cli.older_tag('v4.24.1-rc.1', '4.24.0'))
        self.assertFalse(cli.older_tag('v5.0.0', '4.24.0'))
        self.assertFalse(cli.older_tag('', '4.24.0'))
        self.assertFalse(cli.older_tag('main', '4.24.0'))


class OrganizationCoreTests(unittest.TestCase):
    """The NewerZipTests home (an engine-only package, ZIP folders with their bundle), plus an organization's own Core
    repository whose versions are its own (v1.2.0)."""
    git, zip_folder, run_kit, installer, core_tag = (NewerZip['git'], NewerZip['zip_folder'], NewerZip['run_kit'], NewerZip['installer'], NewerZip['core_tag'])

    def setUp(self):
        NewerZip['setUp'](self)
        self.org = self.base/'org.git'
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.work), str(self.org)], env=GIT_ENV, check=True, capture_output=True)
        subprocess.run(['git', 'tag', '-d', 'v1.0.0', 'v'+self.version], cwd=self.org, env=GIT_ENV, check=True, capture_output=True)
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'tag', '-a', 'v1.2.0', '-m', 'org', 'HEAD'], cwd=self.org, env=GIT_ENV, check=True, capture_output=True)
        self.org_url = 'file://'+self.org.resolve().as_posix()
        for patcher in (mock.patch.object(sources, 'LOCAL_FOR_TESTS', True), mock.patch('installer.config.ownership_problem', return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def impose(self, url, **git):
        (self.base/'managed.toml').write_text(dump_toml({'managed_schema': 1, 'enterprise': {'core': url}, **({'git': git} if git else {})}), encoding='utf-8')

    def core(self):
        return read_toml(self.home/'.ai-kit/lock.toml', {})['sources']['core']

    def test_the_installer_of_a_newer_zip_never_replaces_an_organization_core(self):
        self.impose(self.org_url)
        self.assertEqual(self.installer(self.old)[0], 0)
        code, out, err = self.run_kit(self.old, 'sync', '--home', str(self.home), '--plain')
        self.assertEqual(code, 0, err)
        organization = self.core()
        self.assertEqual((organization['tag'], organization['url']), ('v1.2.0', self.org_url))
        code, out, err = self.installer(self.new)  # the kit's 4.x ZIP: v1.2.0 is the organization's numbering, not an older kit
        self.assertEqual(code, 0, err)
        self.assertEqual(self.core(), organization)

    def test_sync_is_never_locked_out_by_a_core_that_cannot_be_read(self):
        self.assertEqual(self.installer(self.old)[0], 0)  # the Core the ZIP ships, under the kit's own URL
        self.impose(self.org_url)  # IT now imposes its Core: the locked one is refused at every start
        code, out, err = self.run_kit(self.old, 'status', '--home', str(self.home))
        self.assertNotEqual(code, 0)
        self.assertIn('enterprise.core', err)
        code, out, err = self.run_kit(self.old, 'sync', '--home', str(self.home), '--plain')  # the way out the message gives
        self.assertEqual(code, 0, err)
        self.assertEqual((self.core()['tag'], self.core()['url']), ('v1.2.0', self.org_url))
        remove_repository(self.home/'.ai-kit/sources')  # the cache is gone
        code, out, err = self.run_kit(self.old, 'team', 'list', '--home', str(self.home))
        self.assertEqual(code, 0, err)
        code, out, err = self.run_kit(self.old, 'sync', '--home', str(self.home), '--plain')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.run_kit(self.old, 'status', '--home', str(self.home))[0], 0)
        self.impose(self.org_url, revoked=[self.core()['commit']])  # IT revokes the locked commit: sync still starts, and says why
        code, out, err = self.run_kit(self.old, 'sync', '--home', str(self.home), '--plain')
        self.assertEqual(code, 1)  # the command's own answer (nothing changed), not a refusal to start (2)
        self.assertIn('revoked', err)

    def test_the_shipped_core_is_read_in_a_temporary_folder(self):
        code, out, err = self.run_kit(self.new, 'status', '--home', str(self.home))  # a ZIP folder, nothing installed yet
        self.assertFalse((self.home/'.ai-kit/sources').exists(), 'reading the shipped Core wrote under ~/.ai-kit/sources')

    def test_the_shipped_core_is_checked_against_what_it_revokes_and_signs(self):
        bundle = self.new/'core/ai-kit-core.bundle'
        managed = self.base/'it.toml'
        with sync.shipped_core(self.home, bundle, managed_file=managed) as folder:  # not administered: read as it is
            self.assertTrue((folder/'aikit.toml').is_file())
        commit = self.git('rev-parse', 'v'+self.version+'^{commit}')
        managed.write_text(dump_toml({'managed_schema': 1, 'git': {'revoked': [commit]}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError) as caught:
            with sync.shipped_core(self.home, bundle, managed_file=managed):
                pass
        self.assertEqual(caught.exception.kind, 'revoked')
        managed.write_text(dump_toml({'managed_schema': 1, 'git': {'signers': ['ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHRoaXMgaXMgbm90IGEgcmVhbCBrZXkgYXQgYWxs it']}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError) as caught:
            with sync.shipped_core(self.home, bundle, managed_file=managed):
                pass
        self.assertEqual(caught.exception.kind, 'invalid')
        self.assertIn('not signed', str(caught.exception))
        self.assertFalse((self.home/'.ai-kit/sources').exists())

    def test_sync_and_team_start_without_the_locked_content(self):
        def args(*argv):
            return cli.command_parser().parse_args(list(argv))
        self.assertTrue(bootstrap.needs_content(args('status')))
        self.assertTrue(bootstrap.needs_content(args('init')))
        for argv in (('sync',), ('sync', '--dry-run'), ('team', 'list'), ('team', 'use', 'data')):
            self.assertTrue(bootstrap.tolerates_unreadable_core(args(*argv)), argv)
        for argv in (('status',), ('doctor',), ('init',)):
            self.assertFalse(bootstrap.tolerates_unreadable_core(args(*argv)), argv)


class DryRunAndCacheTests(Base):
    def test_a_dry_run_reads_the_git_settings_of_the_real_home(self):
        seen = []
        real = sources.git

        def recording(args, kit, *rest, **options):
            if args[0] in ('ls-remote', 'fetch'):
                seen.append((args[0], options.get('home')))
            return real(args, kit, *rest, **options)
        with mock.patch.object(sources, 'git', recording):
            self.run_action('sync', dry_run=True)
        self.assertTrue(seen)
        for command, home in seen:
            self.assertEqual(home and Path(home), self.home, command+' ran without the home that holds ~/.gitconfig')

    def test_a_cached_tag_that_no_longer_points_to_the_locked_commit_is_refused(self):
        self.run_action('sync')
        self.release('v1.1.0', 'Marker v1.1.0.', push=True)
        self.run_action('sync')
        lock = self.lock()
        cache = sources.cache_dir(self.kit, self.url)
        old_tag = lock['previous']['sources']['core']['tag_object']
        run_git('--git-dir', str(cache), 'update-ref', 'refs/tags/v1.1.0', old_tag, cwd=self.base)
        with self.assertRaises(sources.SourceError) as caught:
            self.run_action('update')
        self.assertEqual(caught.exception.kind, 'invalid')
        self.assertIn('v1.1.0', str(caught.exception))
        self.assertEqual(self.lock(), lock)


if __name__ == '__main__':
    unittest.main()
