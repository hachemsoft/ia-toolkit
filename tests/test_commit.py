import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import commit
from installer.commit import commit_changes, prune_backups


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.kit = self.home/'.ai-kit'
        self.kit.mkdir()
        self.kept = self.kit/'overrides.toml'
        self.kept.write_text('before\n', encoding='utf-8')
        self.gone = self.kit/'old.md'
        self.gone.write_text('old\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_error_in_the_middle_puts_every_file_back(self):
        new = self.kit/'new.md'
        writes = {self.kept: b'after\n', new: b'new\n', self.kit/'third.md': b'x'}
        real = commit.atomic_write
        calls = []

        def failing(path, data):
            calls.append(path)
            if len(calls) == 3:
                raise OSError('disk full')
            real(path, data)
        with mock.patch.object(commit, 'atomic_write', side_effect=failing), self.assertRaises(OSError):
            commit_changes(self.home, self.kit, writes, [self.gone])
        self.assertEqual(self.kept.read_text(encoding='utf-8'), 'before\n')
        self.assertFalse(new.exists())
        self.assertFalse((self.kit/'third.md').exists())
        self.assertEqual(self.gone.read_text(encoding='utf-8'), 'old\n')

    def test_ctrl_c_during_the_removals_puts_every_file_back(self):
        with mock.patch.object(Path, 'unlink', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            commit_changes(self.home, self.kit, {self.kept: b'after\n'}, [self.gone])
        self.assertEqual(self.kept.read_text(encoding='utf-8'), 'before\n')
        self.assertTrue(self.gone.exists())

    @unittest.skipIf(not hasattr(signal, 'SIGTERM') or os.name == 'nt', 'POSIX signal delivery')
    def test_sigterm_during_the_writes_puts_every_file_back(self):
        new = self.kit/'new.md'
        real = commit.atomic_write
        calls = []

        def killed(path, data):
            calls.append(path)
            real(path, data)
            if len(calls) == 1:
                os.kill(os.getpid(), signal.SIGTERM)  # a stopped process, after the first file landed
        before = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(commit, 'atomic_write', side_effect=killed), self.assertRaises(commit.Stopped):
            commit_changes(self.home, self.kit, {self.kept: b'after\n', new: b'new\n'}, [self.gone])
        self.assertEqual(self.kept.read_text(encoding='utf-8'), 'before\n')
        self.assertFalse(new.exists())
        self.assertTrue(self.gone.exists())
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)  # the previous handler is back

    def test_success_keeps_a_backup_of_what_changed(self):
        changed, backup = commit_changes(self.home, self.kit, {self.kept: b'after\n'}, [self.gone])
        self.assertEqual((backup/'.ai-kit/overrides.toml').read_text(encoding='utf-8'), 'before\n')
        self.assertEqual((backup/'.ai-kit/old.md').read_text(encoding='utf-8'), 'old\n')
        self.assertFalse(self.gone.exists())

    def test_only_the_newest_dated_backups_are_kept(self):
        backups = self.kit/'backups'
        for i in range(5):
            (backups/('2026010%dT000000-abcd' % i)).mkdir(parents=True)
        (backups/'kept-by-hand').mkdir()
        prune_backups(self.kit, keep=2)
        self.assertEqual(sorted(p.name for p in backups.iterdir()), ['20260103T000000-abcd', '20260104T000000-abcd', 'kept-by-hand'])


if __name__ == '__main__':
    unittest.main()
