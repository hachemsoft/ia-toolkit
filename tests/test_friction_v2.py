"""V2 slice 7 (ADR 0023): the local friction upkeep (purge after the retention, waiting count) at session start and in engine
commands; the same friction published once with its occurrences; personal data redacted; user edit."""
import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import ROOT

spec = importlib.util.spec_from_file_location('friction_v2', ROOT/'runtime/friction.py')
friction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(friction)
TRACKER = {'kind': 'gitlab', 'project': 'tools/ai-kit', 'labels': ['friction'], 'sources': ['agent'], 'publication': 'approval'}


class FrictionUpkeepTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        (self.home/'.ai-kit').mkdir()
        self.write_state()

    def write_state(self, **extra):
        (self.home/'.ai-kit/state.json').write_text(json.dumps({'version': '2.1.0', 'friction_tracker': TRACKER, **extra}), encoding='utf-8')

    def log(self, text, days_ago=0, source='agent'):
        path, entry = friction.record('docs', text, '/build', 'claude', source, home=str(self.home))
        if days_ago:
            lines = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
            lines[-1]['ts'] = (datetime.now(timezone.utc)-timedelta(days=days_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')
            Path(path).write_text(''.join(json.dumps(e)+'\n' for e in lines), encoding='utf-8')
        return entry

    def test_personal_data_is_redacted_before_it_is_stored(self):
        entry = self.log('jane.doe@example.org saw it in /Users/jane/repo on build.corp')
        self.assertEqual(entry['text'], '[email] saw it in ~/repo on [host]')

    def test_the_same_friction_is_one_issue_with_its_count(self):
        self.log('The plan step is too long 1')
        self.log('the plan step is too long 2')
        self.log('Another problem')
        pending = friction.unsent(str(self.home))
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]['occurrences'], 2)
        sent = {pending[0]['id']: {'url': 'u', 'fingerprint': pending[0]['fingerprint']}}
        (self.home/'.ai-kit/frictions-sent.json').write_text(json.dumps(sent), encoding='utf-8')
        self.log('The plan step is too long 3')  # published once already: not again
        self.assertEqual([e['text'] for e in friction.unsent(str(self.home))], ['Another problem'])

    def test_housekeep_purges_old_entries_and_counts_the_waiting_ones(self):
        self.log('old one', days_ago=40)
        self.log('recent one', days_ago=2)
        self.assertEqual(friction.housekeep(str(self.home)), {'purged': 1, 'waiting': 1})
        self.assertEqual([e['text'] for e in friction.entries(str(self.home))[1]], ['recent one'])
        if os.name != 'nt':
            self.assertEqual(os.stat(self.home/'.ai-kit/frictions.jsonl').st_mode & 0o777, 0o600)
        self.log('another old', days_ago=10)
        self.assertEqual(friction.housekeep(str(self.home), retention_days=5)['purged'], 1)

    def test_a_held_lock_skips_the_rewrite(self):
        self.log('old one', days_ago=40)
        (self.home/'.ai-kit/frictions.jsonl.lock').write_text('', encoding='utf-8')
        self.assertEqual(friction.housekeep(str(self.home))['purged'], 0)
        self.assertEqual(len(friction.entries(str(self.home))[1]), 1)

    def test_the_session_hook_says_how_many_wait_and_never_to_send_them(self):
        shutil.copy2(ROOT/'runtime/friction.py', (self.home/'.ai-kit/bin').mkdir() or self.home/'.ai-kit/bin/friction.py')
        self.write_state(news={'check_remote': False})
        self.log('waiting one')
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        proc = subprocess.run([sys.executable, str(ROOT/'runtime/hooks/whats-new.py')], input=json.dumps({'source': 'startup'}),
                              capture_output=True, text=True, env=env, timeout=60)
        context = json.loads(proc.stdout).get('hookSpecificOutput', {}).get('additionalContext', '')
        self.assertIn('1 friction(s) logged here wait for the person', context)
        self.assertIn('Never run it yourself', context)

    def test_analyze_groups_the_same_friction(self):
        self.log('The plan step is too long 1')
        self.log('the plan step is too long 2')
        self.log('Another problem')
        lines = friction.analyze(str(self.home))
        self.assertEqual(lines[0], '2 distinct friction(s), the most frequent first:')
        self.assertTrue(lines[1].startswith('  2x [docs] /build: The plan step is too long 1'))

    def test_status_reports_the_waiting_frictions(self):
        self.log('waiting one')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            from installer.status import status
            status(self.home)
        self.assertIn('1 friction(s) wait for your approval', out.getvalue())


class UserEditTests(unittest.TestCase):
    def test_off_a_terminal_it_prints_the_path(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            with contextlib.redirect_stdout(io.StringIO()):
                cli.apply('general', home, False, None, 'claude')
            with mock.patch('installer.cli.interactive', return_value=False), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(['user', 'edit', '--home', str(home)]), 0)
            self.assertTrue(out.getvalue().strip().endswith('USER.md'))


if __name__ == '__main__':
    unittest.main()
