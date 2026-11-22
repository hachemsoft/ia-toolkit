"""Lifecycle reliability: uninstall ends whatever the person edited, takes the engine lock and resumes an interrupted
activation first; the installer of a newer ZIP moves the locked Core; the commands that repair an installation run when the
locked Core cannot be read; a failed commit that put everything back is not replayed at the next start. Temporary homes and
local git bundles only: no network, no model."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from installer import bootstrap, cli, command, commit, lifecycle
from installer.core import ROOT, KitError, read_json
from installer.toml_files import read_toml
from test_git_sources import remove_repository  # Windows: Git's object files are read-only

GIT_ENV = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.org',
           'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@example.org'}
POSIX = os.name != 'nt'


def quiet(function, *args, **kwargs):
    """(result, standard output, standard error) of a call."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        result = function(*args, **kwargs)
    return result, out.getvalue(), err.getvalue()


def edit_block(path):
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    lines.insert(2, 'edited by hand\n')
    path.write_text(''.join(lines), encoding='utf-8')


class InstalledHome(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.kit = self.home/'.ai-kit'
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        quiet(cli.apply, self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'all')


class UninstallTests(InstalledHome):
    def test_an_edited_kit_block_does_not_stop_uninstall_and_leaves_no_kit_entry_behind(self):
        for rel in ('.claude/CLAUDE.md', '.codex/AGENTS.md'):
            edit_block(self.home/rel)
        code, out, _ = quiet(cli.uninstall, self.home, True)  # the dry run names them and changes nothing
        self.assertEqual(code, 0)
        self.assertIn('edited by hand', (self.home/'.claude/CLAUDE.md').read_text(encoding='utf-8'))
        code, out, _ = quiet(cli.uninstall, self.home)
        self.assertEqual(code, 0)
        checks = [line for line in out.splitlines() if line.startswith('[Check]')]
        for label in ('~/.claude/CLAUDE.md', '~/.codex/AGENTS.md'):
            self.assertTrue(any(label in line and 'backups' in line for line in checks), (label, checks))
        self.assertFalse(any('restored' in line for line in checks), checks)  # uninstall removes, it does not restore
        # Nothing of the kit stays in the CLIs' own files: no hook pointing to a removed script, no block importing removed files.
        self.assertNotIn('.ai-kit', (self.home/'.claude/settings.json').read_text(encoding='utf-8'))
        for rel in ('.claude/CLAUDE.md', '.codex/AGENTS.md'):
            if (self.home/rel).exists():
                self.assertNotIn('.ai-kit', (self.home/rel).read_text(encoding='utf-8'), rel)
        self.assertFalse((self.kit/'state.json').exists())
        # The edited copies are in the backup of this run.
        backup = max((self.kit/'backups').iterdir(), key=lambda p: p.name)
        for rel in ('.claude/CLAUDE.md', '.codex/AGENTS.md'):
            self.assertIn('edited by hand', (backup/rel).read_text(encoding='utf-8'), rel)

    def test_uninstall_waits_for_another_kit_command(self):
        (self.kit/'engine.lock').write_text(str(os.getpid()), encoding='utf-8')  # a live process holds the lock
        (self.kit/'engine.lock').touch()
        before = sorted(p for p in self.home.rglob('*') if p.is_file())
        with self.assertRaises(KitError) as caught:
            quiet(cli.uninstall, self.home)
        self.assertIn('Another ai-kit command', str(caught.exception))
        self.assertEqual(sorted(p for p in self.home.rglob('*') if p.is_file()), before)
        self.assertEqual(quiet(cli.uninstall, self.home, True)[0], 0)  # a dry run writes nothing: no lock needed

    def test_uninstall_first_puts_back_an_interrupted_activation(self):
        rel = next(r for r in read_json(self.kit/'state.json')['files'] if r.startswith('.ai-kit/hooks/'))
        target = self.home/rel
        backup = self.kit/'backups'/'29990101T000000000000-deadbeef'  # the last activation: stopped by a power cut
        (backup/rel).parent.mkdir(parents=True)
        (backup/rel).write_bytes(target.read_bytes())
        (backup/'manifest.json').write_text(json.dumps({'status': 'pending', 'created': []}), encoding='utf-8')
        target.write_bytes(b'half written')
        code, out, _ = quiet(cli.uninstall, self.home)
        self.assertEqual(code, 0)
        self.assertFalse(target.exists(), out)  # put back, so recognised as the kit's and removed
        self.assertNotIn('modified since the kit installed it', out)
        self.assertEqual(json.loads((backup/'manifest.json').read_text(encoding='utf-8'))['status'], 'restored')

    def test_a_registry_refusal_at_uninstall_is_said_not_raised(self):
        state = read_json(self.kit/'state.json')
        state['command'] = {**(state.get('command') or {}), 'registry': True}
        (self.kit/'state.json').write_text(json.dumps(state), encoding='utf-8')
        with mock.patch.object(lifecycle, 'os', SimpleNamespace(name='nt')), mock.patch.object(lifecycle.kit_command, 'real_home', return_value=True), \
                mock.patch.object(lifecycle.kit_command, 'registry_entry', side_effect=PermissionError('access denied')):
            code, out, _ = quiet(cli.uninstall, self.home)
        self.assertEqual(code, 0)
        self.assertIn('[Check] The user PATH could not be cleaned', out)
        self.assertFalse((self.kit/'state.json').exists())


class Registry:
    """winreg stand-in: one user PATH value."""
    HKEY_CURRENT_USER, KEY_READ, KEY_SET_VALUE, REG_EXPAND_SZ, REG_SZ = 1, 1, 2, 2, 1

    def __init__(self, value):
        self.value = value

    @contextlib.contextmanager
    def OpenKey(self, *_):
        yield self

    def QueryValueEx(self, key, name):
        return self.value, self.REG_EXPAND_SZ

    def SetValueEx(self, key, name, _, kind, value):
        self.value = value


class RegistryPathTests(unittest.TestCase):
    def test_an_entry_written_with_the_profile_folder_expanded_is_the_kits_too(self):
        with mock.patch.dict(os.environ, {'USERPROFILE': r'C:\Users\me'}):
            for present in (r'C:\Users\me\.ai-kit\bin', r'c:\users\ME\.ai-kit\bin' + '\\', r'"C:\Users\me\.ai-kit\bin"'):
                reg = Registry(r'C:\tools;'+present)
                self.assertFalse(command.registry_entry(True, reg), present)  # already there: no second entry
                self.assertEqual(reg.value, r'C:\tools;'+present)
                self.assertTrue(command.registry_entry(False, reg), present)
                self.assertEqual(reg.value, r'C:\tools')
            other = Registry(r'C:\Users\someone-else\.ai-kit\bin')
            self.assertFalse(command.registry_entry(False, other))  # another profile's folder is not the kit's entry here


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class NewerZipTests(unittest.TestCase):
    """The package holds only the engine (as installed from a release ZIP): ROOT is made to look empty of content, and
    AI_KIT_SOURCE_DIR is the extracted ZIP folder with its core/ai-kit-core.bundle."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base/'home'
        (self.home/'.ai-kit').mkdir(parents=True)
        self.work = self.base/'core-work'
        for name in ('skills', 'agents', 'commands', 'context', 'templates'):
            shutil.copytree(ROOT/name, self.work/name)
        (self.work/'aikit.toml').write_text('schema = 1\nname = "core"\nkind = "core"\nmin_engine = "2.0.0"\n', encoding='utf-8')
        self.git('init', '-q')
        self.version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
        self.old, self.new = self.zip_folder('v1.0.0'), self.zip_folder('v'+self.version)
        real = bootstrap.has_content
        for patcher in (mock.patch.object(bootstrap, 'has_content', lambda folder: Path(folder) != ROOT and real(folder)),
                        mock.patch('installer.config.managed_path', return_value=self.base/'managed.toml'),
                        mock.patch('shutil.which', return_value=None), mock.patch.object(Path, 'home', return_value=self.base/'own-home')):
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.run(['git', '-c', 'init.defaultBranch=main', '-c', 'core.autocrlf=false', *args], cwd=self.work, env=GIT_ENV, check=True,
                              capture_output=True, text=True).stdout.strip()

    def zip_folder(self, tag):
        with (self.work/'skills/internal/common/tdd/SKILL.md').open('a', encoding='utf-8') as skill:
            skill.write('\nMarker '+tag+'.\n')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', tag)
        self.git('tag', '-a', tag, '-m', tag)
        folder = self.base/('zip-'+tag)
        (folder/'core').mkdir(parents=True)
        self.git('bundle', 'create', '--quiet', str(folder/'core/ai-kit-core.bundle'), 'refs/tags/'+tag)
        return folder

    def run_kit(self, folder, *argv):
        env = {'AI_KIT_SOURCE_DIR': str(folder)} if folder else {}
        clean = {k: v for k, v in os.environ.items() if k != 'AI_KIT_SOURCE_DIR'}
        with mock.patch.dict(os.environ, {**clean, **env}, clear=True):
            return quiet(cli.main, list(argv))

    def installer(self, folder):
        return self.run_kit(folder, 'init', '--home', str(self.home), '--target', 'claude', '--user', 'ci@example.org', '--command-on-path', 'no', '--plain')

    def core_tag(self):
        return read_toml(self.home/'.ai-kit/lock.toml', {})['sources']['core']['tag']

    def files(self):
        return {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file() and '/backups/' not in p.as_posix()}

    def test_the_installer_of_a_newer_zip_moves_the_locked_core(self):
        self.assertEqual(self.installer(self.old)[0], 0)
        self.assertEqual(self.core_tag(), 'v1.0.0')
        code, out, err = self.installer(self.new)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.core_tag(), 'v'+self.version, out)
        self.assertIn('Marker v'+self.version+'.', (self.home/'.claude/skills/ai-kit-tdd/SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual(read_toml(self.home/'.ai-kit/lock.toml', {})['previous']['sources']['core']['tag'], 'v1.0.0')  # rollback comes back
        before = self.files()
        self.assertEqual(self.installer(self.new)[0], 0)  # a second run changes nothing
        self.assertEqual(self.files(), before)
        self.assertEqual(self.installer(self.old)[0], 0)  # the installer of an older ZIP never moves the Core back
        self.assertEqual(self.core_tag(), 'v'+self.version)

    def test_repair_commands_run_when_the_locked_core_cannot_be_read(self):
        self.installer(self.old)
        remove_repository(self.home/'.ai-kit/sources')  # the cache is gone: the locked Core cannot be extracted
        code, out, err = self.run_kit(self.new, 'status', '--home', str(self.home))
        self.assertNotEqual(code, 0)  # a command that needs the content still says why it cannot run
        self.assertIn('not in the local cache', err)
        code, out, err = self.run_kit(self.new, '--version')
        self.assertEqual((code, err), (0, ''))
        code, out, err = self.run_kit(self.new, 'uninstall', '--dry-run', '--home', str(self.home))
        self.assertEqual(code, 0, err)
        self.assertIn('Dry run: nothing changed.', out)
        code, out, err = self.run_kit(self.new, 'validate', '--path', str(self.work))
        self.assertNotIn('not in the local cache', err)
        code, out, err = self.run_kit(self.new, 'rollback', '--home', str(self.home))
        self.assertEqual(code, 1)  # the command itself answers (exit 1, nothing changed), not the start-up (exit 2)
        self.assertIn('Nothing to roll back to', err)
        code, out, err = self.run_kit(self.new, 'sync', '--from-bundle', str(self.new/'core/ai-kit-core.bundle'), '--home', str(self.home))
        self.assertEqual(code, 0, err)  # the way out the error message gives
        self.assertEqual(self.core_tag(), 'v'+self.version)
        self.assertEqual(self.run_kit(self.new, 'status', '--home', str(self.home))[0], 0)

    def test_the_installer_of_a_newer_zip_repairs_a_locked_core_that_cannot_be_read(self):
        self.installer(self.old)
        remove_repository(self.home/'.ai-kit/sources')
        self.assertNotEqual(self.run_kit(self.old, 'status', '--home', str(self.home))[0], 0)  # only the installer repairs
        code, out, err = self.installer(self.old)  # the same ZIP ships the locked tag: the cache is filled again
        self.assertEqual(code, 0, err)
        self.assertEqual(self.core_tag(), 'v1.0.0')
        self.assertEqual(self.run_kit(self.old, 'status', '--home', str(self.home))[0], 0)
        remove_repository(self.home/'.ai-kit/sources')
        code, out, err = self.installer(self.new)  # a newer ZIP: its Core is activated
        self.assertEqual(code, 0, err)
        self.assertEqual(self.core_tag(), 'v'+self.version)
        self.assertEqual(self.run_kit(self.new, 'status', '--home', str(self.home))[0], 0)

    def test_rollback_is_the_way_out_of_a_core_revoked_by_it(self):
        self.installer(self.old)
        self.installer(self.new)
        commit_id = read_toml(self.home/'.ai-kit/lock.toml', {})['sources']['core']['commit']
        (self.base/'managed.toml').write_text('managed_schema = 1\n[git]\nrevoked = ["'+commit_id+'"]\n', encoding='utf-8')
        with mock.patch('installer.config.ownership_problem', return_value=None):
            code, out, err = self.run_kit(self.new, 'status', '--home', str(self.home))
            self.assertNotEqual(code, 0)
            self.assertIn('revoked', err)
            self.assertEqual(self.run_kit(self.new, 'uninstall', '--dry-run', '--home', str(self.home))[0], 0)
            code, out, err = self.installer(self.new)  # the installer of the same ZIP does not put a revoked Core back
            self.assertNotEqual(code, 0)
            self.assertIn('revoked', err)
            self.assertEqual(self.core_tag(), 'v'+self.version)
            code, out, err = self.run_kit(self.new, 'rollback', '--home', str(self.home))
            self.assertEqual(code, 0, err)
            self.assertEqual(self.core_tag(), 'v1.0.0')
            self.assertEqual(self.run_kit(self.new, 'status', '--home', str(self.home))[0], 0)

    def test_version_needs_no_content_and_writes_nothing(self):
        code, out, err = self.run_kit(None, '--version')  # no kit folder, no Core: only the engine
        self.assertEqual((code, err), (0, ''))
        self.assertIn(self.version, out)
        code, out, err = self.run_kit(self.new, '--version')  # from a ZIP folder: its bundle is not fetched into the home
        self.assertEqual(code, 0)
        self.assertFalse((self.base/'own-home').exists())


class CommitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.kit = self.home/'.ai-kit'
        self.kit.mkdir()
        self.first, self.second = self.kit/'a.toml', self.kit/'b.toml'
        self.first.write_text('a before\n', encoding='utf-8')
        self.second.write_text('b before\n', encoding='utf-8')

    def failing_commit(self, at, after=None, deletes=()):
        """A commit whose write number `at` fails; after(call number) runs once each later write landed."""
        real, calls = commit.atomic_write, []

        def flaky(path, data, *args, **kwargs):
            calls.append(path)
            if len(calls) == at:
                raise OSError('disk full')
            real(path, data, *args, **kwargs)
            if after:
                after(len(calls))
        with mock.patch.object(commit, 'atomic_write', side_effect=flaky):
            commit.commit_changes(self.home, self.kit, {self.first: b'a after\n', self.second: b'b after\n', self.kit/'c.toml': b'c'}, list(deletes))

    def test_a_failed_commit_put_back_is_not_replayed_at_the_next_start(self):
        with self.assertRaises(OSError):
            self.failing_commit(at=3)
        manifest = next((self.kit/'backups').glob('*/manifest.json'))
        self.assertEqual(json.loads(manifest.read_text(encoding='utf-8'))['status'], 'restored')
        self.first.write_text('edited later by the person\n', encoding='utf-8')
        self.assertIsNone(commit.resume_pending(self.home, self.kit))
        self.assertEqual(self.first.read_text(encoding='utf-8'), 'edited later by the person\n')

    @unittest.skipUnless(POSIX and hasattr(signal, 'SIGTERM'), 'POSIX signal delivery')
    def test_a_stop_signal_during_the_restoration_does_not_leave_it_half_done(self):
        def stop(call):
            if call == 4:  # the restoration's first file is back: the process is told to stop
                os.kill(os.getpid(), signal.SIGTERM)
        before = signal.getsignal(signal.SIGTERM)
        try:
            self.failing_commit(at=3, after=stop)
        except OSError:
            pass  # the first error is the one reported
        except commit.Stopped:
            pass  # the files below tell whether the restoration went to its end
        else:
            self.fail('the commit did not fail')
        self.assertEqual((self.first.read_text(encoding='utf-8'), self.second.read_text(encoding='utf-8')), ('a before\n', 'b before\n'))
        self.assertFalse((self.kit/'c.toml').exists())
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    @unittest.skipUnless(POSIX, 'POSIX file modes')
    def test_the_file_mode_survives_a_write_a_restoration_and_a_resume(self):
        shim = self.kit/'bin'/'ai-kit'
        shim.parent.mkdir()
        shim.write_bytes(b'#!/bin/sh\n')
        shim.chmod(0o755)
        self.first.chmod(0o644)

        def mode(path):
            return stat.S_IMODE(path.stat().st_mode)
        commit.atomic_write(shim, b'#!/bin/sh\n# again\n')
        self.assertEqual(mode(shim), 0o755)
        commit.commit_changes(self.home, self.kit, {self.first: b'a after\n'}, [])
        self.assertEqual(mode(self.first), 0o644)  # a file of the person's (a shell startup file) keeps its mode
        with self.assertRaises(OSError):  # the shim removed, then the error: put back with its mode
            real_unlink = Path.unlink

            def unlink(path, *args, **kwargs):
                real_unlink(path, *args, **kwargs)
                if path == shim:
                    raise OSError('disk full')
            with mock.patch.object(Path, 'unlink', unlink):
                commit.commit_changes(self.home, self.kit, {}, [shim])
        self.assertEqual((shim.read_bytes(), mode(shim)), (b'#!/bin/sh\n# again\n', 0o755))
        # A machine stop during the writes: the next start puts the file back from the backup, with its mode.
        changed, backup = commit.commit_changes(self.home, self.kit, {}, [shim])
        manifest = json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
        (backup/'manifest.json').write_text(json.dumps({**manifest, 'status': 'pending'}), encoding='utf-8')
        self.assertEqual(commit.resume_pending(self.home, self.kit), backup)
        self.assertEqual(mode(shim), 0o755)
        self.assertEqual(mode(backup/'.ai-kit/bin/ai-kit'), 0o600)  # the backup copies stay private

    def test_backup_folders_sort_in_the_order_they_were_made(self):
        names = []
        hexes = iter(['ffffffff', '00000000', '88888888'])
        with mock.patch.object(commit.uuid, 'uuid4', side_effect=lambda: SimpleNamespace(hex=next(hexes)+'0'*24)):
            for text in (b'1', b'2', b'3'):  # within the same second
                names.append(commit.commit_changes(self.home, self.kit, {self.first: text}, [])[1].name)
        self.assertEqual(sorted(names), names)
        self.assertRegex(names[0], r'^\d{8}T\d{12}-[0-9a-f]{8}$')
        commit.prune_backups(self.kit, keep=1)
        self.assertEqual([p.name for p in (self.kit/'backups').iterdir()], names[-1:])  # still recognised as dated backups


class ConsoleWithoutRichTests(unittest.TestCase):
    def test_the_console_tests_skip_without_rich_instead_of_failing(self):
        code = ("import sys, unittest\nsys.modules['rich'] = None\nsys.modules['rich.console'] = None\n"
                "unittest.main(module=None, argv=['x', 'discover', '-s', 'tests', '-p', 'test_console.py'])\n")
        proc = subprocess.run([os.sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-600:])
        self.assertTrue(re.search(r'OK \(skipped=\d+\)', proc.stderr), proc.stderr[-300:])


if __name__ == '__main__':
    unittest.main()
