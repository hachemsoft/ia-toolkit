"""4.24.1: the evaluation runner. The fixture repository is always on main (whatever init.defaultBranch says); cases 47 and
48 also watch .git/HEAD; an error word in a successful answer is not an infrastructure failure; a turn's other CLI is
looked for before the first (billed) turn is sent, and never receives the first CLI's --model."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_evals_runner

evals_run, ROOT = test_evals_runner.evals_run, test_evals_runner.ROOT


class FixtureTests(unittest.TestCase):
    def test_the_fixture_repository_is_on_main_whatever_the_persons_default_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, config = Path(tmp)/'repo', Path(tmp)/'gitconfig'
            repo.mkdir()
            (repo/'a.txt').write_text('a', encoding='utf-8')
            config.write_text('[init]\n\tdefaultBranch = trunk\n', encoding='utf-8')
            with mock.patch.dict('os.environ', {'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1'}):
                evals_run.prepare_git(repo, {})
                branch = subprocess.run(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()
            self.assertEqual(branch, 'main')
            self.assertTrue((repo/'.git/refs/heads/main').is_file())

    def test_a_git_without_the_branch_option_still_gives_main(self):
        real = subprocess.run

        def old_git(command, *args, **kwargs):  # git before 2.28: init knows no -b
            if 'init' in command and ('-b' in command or any(str(c).startswith('--initial-branch') for c in command)):
                raise subprocess.CalledProcessError(129, command)
            return real(command, *args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)/'repo'
            repo.mkdir()
            (repo/'a.txt').write_text('a', encoding='utf-8')
            with mock.patch.object(evals_run.subprocess, 'run', old_git):
                evals_run.prepare_git(repo, {})
            self.assertEqual(real(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip(), 'main')

    def test_the_cross_cli_cases_watch_the_branch_the_repository_is_on(self):
        for name in ('47-claude-to-codex-resumes-the-work', '48-codex-to-claude-resumes-the-work'):
            case = json.loads((ROOT/'evals/cases'/(name+'.json')).read_text(encoding='utf-8'))
            for expect in [case['expect']] + [turn['expect'] for turn in case['turns']]:
                self.assertIn('.git/HEAD', expect['unchanged'], name)
                self.assertIn('.git/refs/heads/main', expect['unchanged'], name)


class ApiErrorTests(unittest.TestCase):
    def test_a_successful_answer_that_speaks_of_an_error_is_not_an_infrastructure_failure(self):
        for answer in ('The endpoint answers 429 Too Many Requests: a quota error to handle.', 'It returns 503 on a billing error; I added a retry.',
                       'The README says: Not logged in. Run codex login, then retry on error.', 'The test covers the "usage limit" message.',
                       "You've hit your usage limit is the text the client shows."):
            self.assertIsNone(evals_run.api_error(0, answer), answer)
            self.assertIsNone(evals_run.api_error(0, answer+'\n--- stderr ---\nwarning: slow start\n'), answer)
        for stderr in ('429 Too Many Requests: quota exceeded error', 'Error: Not logged in. Run codex login', "You've hit your usage limit"):
            self.assertIsNotNone(evals_run.api_error(0, 'Partial answer.\n--- stderr ---\n'+stderr+'\n'), stderr)
            self.assertIsNotNone(evals_run.api_error(1, stderr), stderr)


class OtherCliTests(unittest.TestCase):
    CASE = {'name': 'x', 'cli': 'claude', 'prompt': 'start', 'expect': {'contains': ['ok']},
            'turns': [{'cli': 'codex', 'prompt': 'go on', 'expect': {'contains': ['ok']}}]}

    def run_case(self, which, model='claude-model'):
        sent = []

        def turn(command, run_dir, env, timeout, cli, expect):
            sent.append((cli, command))
            return 'ok', []
        with tempfile.TemporaryDirectory() as home, mock.patch.object(evals_run, 'run_turn', turn), mock.patch.object(evals_run.shutil, 'which', which):
            output, failures, turns = evals_run.run_case(self.CASE, Path(home), 60, model, 'default', 'claude', '/bin/claude')
        return sent, failures, turns

    def test_a_missing_second_cli_is_found_before_the_first_turn_is_sent(self):
        sent, failures, turns = self.run_case(lambda name: None)
        self.assertEqual(sent, [], 'turn 1 was sent (and billed) although turn 2 cannot run')
        self.assertEqual(turns, 0)
        self.assertTrue(failures and failures[0].startswith('ERROR') and 'codex' in failures[0], failures)

    def test_the_model_of_the_first_cli_is_not_given_to_another_cli(self):
        sent, failures, turns = self.run_case(lambda name: '/bin/'+name)
        self.assertEqual((failures, turns, [cli for cli, _ in sent]), ([], 2, ['claude', 'codex']))
        self.assertIn('claude-model', sent[0][1])
        self.assertEqual(sent[1][1][0], '/bin/codex')
        self.assertNotIn('claude-model', sent[1][1])
        self.assertNotIn('-m', sent[1][1])


if __name__ == '__main__':
    unittest.main()
