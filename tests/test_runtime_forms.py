"""4.24.1: the helper scripts on forms they missed. A proof refuses a production target given with -t; a friction never
keeps the body of a private key pasted over several lines; the purge of old frictions keeps an entry written while it
waited for the lock; the review page is written through a temporary file of its own, readable by the person only."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

import test_review_html
import test_runtime_helpers

friction, prove_test = test_runtime_helpers.friction, test_runtime_helpers.prove_test
KEY = '-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj\nMzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNbvJZHtCSuYEvu\n-----END PRIVATE KEY-----'


class ProofTargetTests(unittest.TestCase):
    def resolve(self, *command):
        with mock.patch.object(prove_test.shutil, 'which', lambda name: '/bin/'+name), mock.patch.dict(os.environ, {'AI_KIT_PROD_TARGETS': ''}):
            return prove_test.resolve_command(list(command))

    def test_a_production_target_given_with_the_short_option_is_refused(self):
        for command in (('dbt', 'test', '--target', 'dev', '-t', 'prod'), ('dbt', 'test', '-t', 'prod'), ('dbt', 'build', '-t=production'),
                        ('dbt', 'build', '-tprd'), ('dbt', '-t', 'PROD', 'test'), ('uv', 'run', 'dbt', 'test', '-t', 'prod')):
            with self.assertRaises(prove_test.Unsupported, msg=command) as caught:
                self.resolve(*command)
            self.assertIn('production target', str(caught.exception))
        for command in (('dbt', 'test', '-t', 'dev'), ('dbt', 'test', '--target', 'dev', '-s', 'tag:prod'), ('dbt', 'build', '-tdev')):
            self.assertEqual(self.resolve(*command)[1:], list(command[1:]))
        with self.assertRaises(prove_test.Unsupported) as caught:
            self.resolve('dbt', 'test', '-s', 'orders')
        self.assertIn('--target', str(caught.exception))


class FrictionTests(test_runtime_helpers.FrictionLockTests):
    def test_a_private_key_over_several_lines_is_never_kept(self):
        path, entry = friction.record('other', 'the deploy failed with this key:\n'+KEY+'\nand then stopped', home=str(self.home))
        stored = Path(path).read_text(encoding='utf-8')
        for piece in ('MIIEvQIBADANBg', 'MzEfYyjiWA4R4', 'END PRIVATE KEY'):
            self.assertNotIn(piece, stored)
        self.assertIn('the deploy failed with this key: [redacted] and then stopped', entry['text'])
        path, entry = friction.record('other', 'cut key: -----BEGIN RSA PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC', home=str(self.home))
        self.assertNotIn('MIIEvQIBADANBg', entry['text'])

    def test_an_entry_written_while_the_purge_waited_for_the_lock_is_kept(self):
        real = friction.take_lock

        def slow_lock(lock):
            friction.record('other', 'written by another session meanwhile', home=str(self.home))
            return real(lock)
        with mock.patch.object(friction, 'take_lock', slow_lock):
            self.assertEqual(friction.housekeep(str(self.home))['purged'], 1)
        self.assertEqual(self.kept(), ['a recent friction', 'written by another session meanwhile'])


class ReviewPageTests(unittest.TestCase):
    def test_the_page_is_written_through_a_temporary_file_of_its_own(self):
        repo = test_review_html.Repo()
        self.addCleanup(repo.cleanup)
        guide = repo.change()
        victim = repo.path/'victim.txt'
        victim.write_text('mine', encoding='utf-8')
        planted = guide.parent/'.review.html.tmp'  # the name the script used: whoever plants it chooses where the page goes
        try:
            planted.symlink_to(victim)
        except OSError:
            planted.write_text('planted', encoding='utf-8')
        proc = repo.run('--guide', str(guide))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = Path(proc.stdout.strip())
        self.assertIn('<html', out.read_text(encoding='utf-8'))
        self.assertEqual(victim.read_text(encoding='utf-8'), 'mine')
        self.assertTrue(os.path.lexists(planted))
        self.assertEqual([p.name for p in guide.parent.iterdir() if p.name.endswith('.tmp') and p != planted], [])
        if sys.platform != 'win32':
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)  # the page holds the diff: the person's only


if __name__ == '__main__':
    unittest.main()
