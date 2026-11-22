"""The evaluation runner, against a stand-in CLI: no model is called. A real run needs --confirm-paid-run."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evals_run_cases', ROOT/'evals/run.py')
evals_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evals_run)

# Stand-in CLI: answers STAND_IN_ANSWER, exits with STAND_IN_CODE, writes STAND_IN_WRITE (relative to its folder),
# and counts its calls in STAND_IN_LOG.
STAND_IN = '''import os, sys
from pathlib import Path
with open(os.environ['STAND_IN_LOG'], 'a', encoding='utf-8') as log:
    log.write(' '.join(sys.argv[1:2]) + '\\n')
if sys.argv[1:2] == ['--version']:
    print('9.9.9-stand-in'); raise SystemExit(0)
if os.environ.get('STAND_IN_GIT'):
    import subprocess; print(subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout)
if os.environ.get('STAND_IN_WRITE'):
    target = Path.cwd() / os.environ['STAND_IN_WRITE']; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('x', encoding='utf-8')
print(os.environ.get('STAND_IN_ANSWER', 'Which customers count as active?'))
if os.environ.get('STAND_IN_STDERR'):
    sys.stderr.write(os.environ['STAND_IN_STDERR'])
raise SystemExit(int(os.environ.get('STAND_IN_CODE', '0')))
'''


@unittest.skipIf(sys.platform == 'win32', 'the stand-in is a script with a shebang')
class RunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.stand_in = self.base/'cli'
        self.stand_in.write_text('#!'+sys.executable+'\n'+STAND_IN, encoding='utf-8')
        self.stand_in.chmod(0o755)
        self.log = self.base/'calls.log'
        self.home = self.base/'home'
        (self.home/'.ai-kit').mkdir(parents=True)
        (self.home/'.ai-kit/state.json').write_text(json.dumps({'version': '0', 'profile': 'general', 'installed': {'commands': ['intent'], 'skills': []}}), encoding='utf-8')
        self.cases = self.base/'cases'
        self.cases.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ('AI_KIT_NO_LIVE',)}
        env['STAND_IN_LOG'] = str(self.log)
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def case(self, name='asks', **extra):
        data = {'name': name, 'prompt': '/intent active customers', 'expect': {'regex': ['\\?'], 'files_absent': ['intent.md']}, **extra}
        (self.cases/(name+'.json')).write_text(json.dumps(data), encoding='utf-8')

    def run_cases(self, *args, **env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = evals_run.main(['--cases', str(self.cases), '--home', str(self.home), '--report', str(self.base/'r.json'), *args])
        return code, out.getvalue()

    def calls(self):
        return [c for c in (self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []) if c != '--version']

    def test_checks_tell_good_answers_from_bad_ones(self):
        """Cases with samples: each "pass" answer passes check(), each "fail" answer fails it. No model call."""
        cases = [c for c in evals_run.load_cases(ROOT/'evals'/'cases') if c.get('samples')]
        self.assertGreaterEqual(len(cases), 4)
        for case in cases:
            for answer in case['samples'].get('pass', []):
                with self.subTest(case=case['name'], answer=answer):
                    self.assertEqual(evals_run.check(answer, case['expect']), [])
            for answer in case['samples'].get('fail', []):
                with self.subTest(case=case['name'], answer=answer):
                    self.assertNotEqual(evals_run.check(answer, case['expect']), [])

    def test_tokens_are_read_before_the_output_is_cut(self):
        # Codex writes its token count last, on stderr; the report keeps it even when the output is cut to 12,000 characters.
        self.case(expect={'regex': ['active']})
        code, out = self.run_cases('--stand-in', str(self.stand_in), STAND_IN_ANSWER='Which customers count as active? ' + 'x' * 13000,
                                   STAND_IN_STDERR='codex\nDone.\ntokens used\n7\u202f615\n')
        report = json.loads((self.base/'r.json').read_text(encoding='utf-8'))
        self.assertEqual(report['results'][0]['tokens'], 7615, out)
        self.assertIn('7615 tokens', out)

    def test_tokens_are_null_when_the_cli_does_not_print_them(self):
        self.case(expect={'regex': ['active']})
        self.run_cases('--stand-in', str(self.stand_in))
        self.assertIsNone(json.loads((self.base/'r.json').read_text(encoding='utf-8'))['results'][0]['tokens'])

    def test_not_regex_forbids_a_pattern(self):
        expect = {'not_regex': ['(?i)important[^\\n]{0,40}error_if']}
        self.assertEqual(evals_run.check('- Minor: error_if raised, as the spec asks', expect), [])
        self.assertEqual(evals_run.check('- **Important** · Tests: error_if relaxed', expect), ['forbidden pattern: (?i)important[^\\n]{0,40}error_if'])

    def test_real_run_needs_explicit_consent(self):
        self.case()
        code, out = self.run_cases()
        self.assertEqual(code, 2)
        self.assertIn('--confirm-paid-run', out)
        self.assertEqual(self.calls(), [])

    def test_no_live_refuses_even_with_consent(self):
        self.case()
        code, out = self.run_cases('--confirm-paid-run', AI_KIT_NO_LIVE='1')
        self.assertEqual(code, 2)
        self.assertIn('AI_KIT_NO_LIVE', out)

    def test_dry_run_calls_nothing(self):
        self.case()
        code, out = self.run_cases('--dry-run')
        self.assertEqual(code, 0)
        self.assertIn('no model called', out)
        self.assertEqual(self.calls(), [])

    def test_passing_case(self):
        self.case()
        code, out = self.run_cases('--stand-in', str(self.stand_in))
        self.assertEqual(code, 0, out)
        report = json.loads((self.base/'r.json').read_text(encoding='utf-8'))
        self.assertEqual(report['results'][0]['status'], 'OK')
        self.assertEqual(report['meta']['cli_version'], '9.9.9-stand-in')
        self.assertTrue(report['meta']['simulated'])
        self.assertIn('kit', report['meta'])

    def test_baseline_refuses_a_home_with_the_kit(self):
        self.case()
        code, out = self.run_cases('--stand-in', str(self.stand_in), '--baseline')
        self.assertEqual(code, 2)
        self.assertIn('the kit is installed', out)
        self.assertEqual(self.calls(), [])

    def test_baseline_runs_cases_that_require_the_kit_and_compares(self):
        self.case('needs-kit', requires={'commands': ['intent', 'spec']})
        code, out = self.run_cases('--stand-in', str(self.stand_in))
        self.assertIn('[SKIP]', out)
        self.case('needs-kit', requires={'commands': ['intent']})
        self.run_cases('--stand-in', str(self.stand_in))
        with_kit = self.base/'with.json'
        (self.base/'r.json').rename(with_kit)
        bare = self.base/'bare'
        bare.mkdir()
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'STAND_IN_ANSWER': 'Done.'}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            evals_run.main(['--cases', str(self.cases), '--home', str(bare), '--report', str(self.base/'without.json'), '--stand-in', str(self.stand_in), '--baseline'])
        without = json.loads((self.base/'without.json').read_text(encoding='utf-8'))
        self.assertTrue(without['meta']['baseline'])
        self.assertEqual(without['results'][0]['status'], 'FAIL')
        spec = importlib.util.spec_from_file_location('evals_compare', ROOT/'evals/compare.py')
        compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(compare.main([str(with_kit), str(self.base/'without.json')]), 0)
        self.assertIn('passed only with the kit: 1 (needs-kit)', out.getvalue())
        self.assertIn('simulated, not a measure', out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(compare.main([str(self.base/'without.json'), str(with_kit)]), 2)

    def test_nonzero_exit_is_an_execution_failure_whatever_the_output(self):
        self.case()
        code, out = self.run_cases('--stand-in', str(self.stand_in), STAND_IN_CODE='1')
        self.assertEqual(code, 2)
        self.assertIn('[ERROR]', out)
        self.assertIn('exited with code 1', out)

    def test_artifact_checked_where_commands_write_it(self):
        self.case()
        code, out = self.run_cases('--stand-in', str(self.stand_in), STAND_IN_WRITE='docs/sdlc/2026-01-01-active/intent.md')
        self.assertEqual(code, 1)
        self.assertIn('[FAIL]', out)
        self.assertIn('docs/sdlc/2026-01-01-active/intent.md', out)

    def test_expected_file_present(self):
        self.case(expect={'files_present': ['intent.md']})
        code, out = self.run_cases('--stand-in', str(self.stand_in))
        self.assertIn('expected file not written: intent.md', out)

    def test_git_case_has_a_real_repository_with_uncommitted_changes(self):
        self.case(cwd='py-api-mini', git={'commit': True, 'uncommitted': {'orders.py': 'changed\n'}}, expect={'contains': [' M orders.py']})
        code, out = self.run_cases('--stand-in', str(self.stand_in), STAND_IN_GIT='1')
        self.assertEqual(code, 0, out)

    def test_git_case_can_delete_a_committed_file(self):
        self.case(cwd='py-api-mini', git={'commit': True, 'uncommitted': {'tests/test_orders.py': None}}, expect={'contains': [' D tests/test_orders.py']})
        code, out = self.run_cases('--stand-in', str(self.stand_in), STAND_IN_GIT='1')
        self.assertEqual(code, 0, out)

    def test_every_prepared_case_is_valid_and_its_fixture_exists(self):
        cases = evals_run.load_cases(ROOT/'evals/cases')
        self.assertGreaterEqual(len(cases), 12)
        for case in cases:
            self.assertIn('requires', case, case['name'])
            if case.get('cwd'):
                self.assertTrue((ROOT/'evals/fixtures'/case['cwd']).is_dir(), case['name'])
            for kind in ('contains', 'not_contains', 'regex', 'not_regex', 'files_absent', 'files_present'):
                self.assertIsInstance(case['expect'].get(kind, []), list, case['name'])

    def test_unmet_precondition_skips_without_calling(self):
        self.case(requires={'skills': ['sql-review'], 'commands': ['intent']})  # an optional skill not installed
        code, out = self.run_cases('--stand-in', str(self.stand_in))
        self.assertIn('[SKIP]', out)
        self.assertIn('sql-review', out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(code, 2)

    def test_retries_are_bounded_and_only_on_infrastructure_errors(self):
        self.case()
        self.run_cases('--stand-in', str(self.stand_in), '--retries', '1', STAND_IN_CODE='1')
        self.assertEqual(len(self.calls()), 2)
        self.log.unlink()
        self.run_cases('--stand-in', str(self.stand_in), '--retries', '2', STAND_IN_ANSWER='no question here')
        self.assertEqual(len(self.calls()), 1)  # a behaviour failure is not retried
        with self.assertRaises(SystemExit):
            self.run_cases('--stand-in', str(self.stand_in), '--retries', '5')


class WorkflowTests(unittest.TestCase):
    def test_paid_evals_never_trigger_on_their_own(self):
        text = (ROOT/'.github/workflows/agent-evals.yml').read_text(encoding='utf-8')
        triggers = text.split('\non:', 1)[1].split('\npermissions:', 1)[0]
        for event in ('pull_request', 'push', 'schedule'):
            self.assertNotIn(event, triggers)
        self.assertIn('workflow_dispatch', triggers)
        self.assertRegex(triggers, r'confirm_paid_run:[^\n]*\n(\s+[a-z].*\n)*?\s+default: false')
        self.assertIn("inputs.confirm_paid_run == true", text)
        self.assertIn('--confirm-paid-run', text)

    def test_model_free_ci_calls_no_model(self):
        text = (ROOT/'.github/workflows/portability.yml').read_text(encoding='utf-8')
        for word in ('GEMINI_API_KEY', 'evals/run.py', 'doctor --live', 'OPENAI_API_KEY'):
            self.assertNotIn(word, text)


class EvalCasesPageTests(unittest.TestCase):
    """docs/evals.md lists every case: a new case without its row fails here."""
    def test_every_case_has_a_section(self):
        root = Path(__file__).resolve().parents[1]
        page = (root/'docs/evals.md').read_text(encoding='utf-8')
        names = [json.loads(p.read_text(encoding='utf-8'))['name'] for p in sorted((root/'evals/cases').glob('*.json'))]
        missing = [n for n in names if '`' + n + '`' not in page]
        self.assertEqual(missing, [], 'add a row to the cases table of docs/evals.md')

if __name__ == '__main__':
    unittest.main()


class RequiredAgentsTests(unittest.TestCase):
    """4.14.0: a case can require an optional agent; the state records agents with the kit's prefix."""

    def test_a_missing_agent_is_a_precondition(self):
        case = {'requires': {'commands': ['review'], 'agents': ['silent-failure-hunter']}}
        state = {'installed': {'commands': ['review'], 'agents': ['ai-kit-doubter']}}
        self.assertEqual(evals_run.unmet_preconditions(case, state), ['agent silent-failure-hunter not installed'])
        state['installed']['agents'].append('ai-kit-silent-failure-hunter')
        self.assertEqual(evals_run.unmet_preconditions(case, state), [])


STAND_IN_ARGV = '''import json, os, sys
if sys.argv[1:2] == ['--version']:
    print('9.9.9-stand-in'); raise SystemExit(0)
with open(os.environ['STAND_IN_ARGV'], 'a', encoding='utf-8') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('STAND_IN_GIT'):
    import subprocess; print(subprocess.run(['git', 'branch', '--list'], capture_output=True, text=True).stdout)
answers = os.environ.get('STAND_IN_ANSWERS', 'Which customers count as active?').split('||')
calls = sum(1 for _ in open(os.environ['STAND_IN_ARGV'], encoding='utf-8'))
print(answers[min(calls, len(answers)) - 1])
'''


@unittest.skipIf(sys.platform == 'win32', 'the stand-in is a script with a shebang')
class MultiTurnTests(unittest.TestCase):
    """Increment 0 of docs/sdlc/2026-11-21-loop-and-resume: a case may hold several turns, resumed in the same session or
    started afresh, with external changes between them and assertions on the files; no model is called."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.stand_in = self.base/'cli'
        self.stand_in.write_text('#!'+sys.executable+'\n'+STAND_IN_ARGV, encoding='utf-8')
        self.stand_in.chmod(0o755)
        self.argv_log = self.base/'argv.log'
        self.home = self.base/'home'
        (self.home/'.ai-kit').mkdir(parents=True)
        (self.home/'.ai-kit/state.json').write_text(json.dumps({'version': '0', 'installed': {'commands': ['build'], 'skills': []}}), encoding='utf-8')
        self.cases = self.base/'cases'
        self.cases.mkdir()
        env = {k: v for k, v in os.environ.items() if k != 'AI_KIT_NO_LIVE'}
        env['STAND_IN_ARGV'] = str(self.argv_log)
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def case(self, turns, **extra):
        data = {'name': 'multi', 'prompt': '/build add a discount', 'cwd': 'py-api-mini', 'git': {'commit': True},
                'expect': {'regex': ['\\?']}, 'turns': turns, **extra}
        (self.cases/'multi.json').write_text(json.dumps(data), encoding='utf-8')

    def run_cases(self, cli, **env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = evals_run.main(['--cases', str(self.cases), '--home', str(self.home), '--report', str(self.base/'r.json'),
                                   '--cli', cli, '--stand-in', str(self.stand_in)])
        report = json.loads((self.base/'r.json').read_text(encoding='utf-8')) if (self.base/'r.json').exists() else None
        return code, out.getvalue(), report

    def argv(self):
        return [json.loads(line) for line in self.argv_log.read_text(encoding='utf-8').splitlines()] if self.argv_log.exists() else []

    def test_claude_resumes_the_session_for_the_next_turn(self):
        self.case([{'prompt': 'The tests are approved, go on.', 'expect': {'contains': ['done']}}])
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(code, 0, out)
        calls = self.argv()
        self.assertEqual(len(calls), 2, 'the second turn was not sent')
        first, second = calls
        self.assertNotIn('-c', first)
        self.assertIn('-c', second)
        self.assertIn('The tests are approved, go on.', second)
        self.assertEqual(report['results'][0].get('turns'), 2)

    def test_codex_keeps_the_session_and_resumes_the_last_one(self):
        self.case([{'prompt': 'The tests are approved, go on.', 'expect': {'contains': ['done']}}])
        code, out, _ = self.run_cases('codex', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(code, 0, out)
        calls = self.argv()
        self.assertEqual(len(calls), 2, 'the second turn was not sent')
        first, second = calls
        self.assertEqual(first[0], 'exec')
        self.assertNotIn('--ephemeral', first)  # a multi-turn case needs a session to resume
        self.assertEqual(second[:3], ['exec', 'resume', '--last'])
        self.assertEqual(second[-1], 'The tests are approved, go on.')

    def test_a_new_session_does_not_resume(self):
        self.case([{'new_session': True, 'prompt': 'Pick up where we left off.', 'expect': {'contains': ['done']}}])
        self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        calls = self.argv()
        self.assertEqual(len(calls), 2)
        self.assertNotIn('-c', calls[1])
        self.argv_log.unlink()
        self.run_cases('codex', STAND_IN_ANSWERS='Which discount? ||done')
        calls = self.argv()
        self.assertEqual(len(calls), 2)
        self.assertNotIn('resume', calls[1])

    def test_a_change_between_turns_is_caught_by_unchanged(self):
        self.case([{'between': {'write': {'tests/test_orders.py': 'def test_rewritten(): pass\n'}},
                    'prompt': 'Go on.', 'expect': {'unchanged': ['tests/test_orders.py', 'orders.py']}}])
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(code, 1, out)
        self.assertEqual(report['results'][0]['status'], 'FAIL')
        self.assertIn('changed: tests/test_orders.py', out)
        self.assertNotIn('changed: orders.py', out)

    def test_file_regex_reads_the_file_after_the_turn(self):
        self.case([{'between': {'write': {'orders.py': 'DISCOUNT = 0.1\n'}}, 'prompt': 'Go on.',
                    'expect': {'file_regex': {'orders.py': ['DISCOUNT'], 'tests/test_orders.py': ['discount']}}}])
        code, out, _ = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(code, 1, out)
        self.assertIn('tests/test_orders.py', out)
        self.assertNotIn("orders.py: pattern not found: DISCOUNT", out)

    def test_a_failing_turn_stops_the_case(self):
        self.case([{'prompt': 'Go on.', 'expect': {'contains': ['done']}}])
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='I changed the code.||done')  # turn 1 asks nothing
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.argv()), 1)  # the second turn would be billed: never sent
        self.assertEqual(report['results'][0].get('turns'), 1)

    def test_gemini_and_agy_multi_turn_cases_are_skipped_without_a_call(self):
        self.case([{'prompt': 'Go on.', 'expect': {}}])
        for cli in ('gemini', 'agy'):
            with self.subTest(cli=cli):
                code, out, report = self.run_cases(cli)
                self.assertEqual(report['results'][0]['status'], 'SKIP', out)
                self.assertIn('resume', report['results'][0]['failures'][0])
                self.assertEqual(self.argv(), [])

    def test_a_malformed_turn_is_refused_when_the_cases_load_before_any_call(self):
        """Review of increment 0: a bad turn found halfway through a paid run lost the report of the cases already billed."""
        for turns, reason in (([{'prompt': 'Go on.', 'expect': {}, 'between': {'git': [['branch', 'x']]}}], 'git branch x'),
                              ([{'prompt': 'Go on.'}], 'needs a prompt'),
                              ([{'prompt': 'Go on.', 'expect': {}, 'between': {'write': {'../outside.py': 'x'}}}], '../outside.py'),
                              ([{'prompt': 'Go on.', 'expect': {'unchanged': ['/etc/hosts']}}], '/etc/hosts')):
            with self.subTest(reason=reason):
                self.case(turns)
                with self.assertRaises(SystemExit) as refused:
                    self.run_cases('claude')
                self.assertIn(reason, str(refused.exception))
                self.assertEqual(self.argv(), [])

    def test_a_case_level_between_prepares_the_repository_before_the_first_turn(self):
        """The state a previous session left (a branch, a commit, a file changed since) is built without a billed turn."""
        self.case([], between={'git': [['checkout', '-b', 'feature/discount']], 'write': {'tests/test_discount.py': 'def test_d(): pass\n'}},
                  expect={'contains': ['feature/discount'], 'files_present': ['tests/test_discount.py']})
        code, out, report = self.run_cases('claude', STAND_IN_GIT='1')
        self.assertEqual(code, 0, out)
        self.assertEqual(report['results'][0].get('turns'), 1)
        self.assertEqual(len(self.argv()), 1)

    def test_between_steps_run_in_order(self):
        """A list of steps: write and commit yesterday's test, then change it again, uncommitted."""
        self.case([], between=[{'write': {'tests/test_discount.py': 'approved\n'}, 'git': [['add', '-A'], ['commit', '-m', 'approved']]},
                               {'write': {'tests/test_discount.py': 'changed since\n'}}],
                  expect={'regex': ['\\?'], 'file_regex': {'tests/test_discount.py': ['changed since']}})
        code, out, report = self.run_cases('claude')
        self.assertEqual(code, 0, out)
        self.assertEqual(report['results'][0]['status'], 'OK')

    def test_the_setup_between_is_not_a_change_of_the_agent(self):
        """Paid runs of 2026-11-21: a case-level between wrote yesterday's files, and unchanged blamed the agent for them."""
        self.case([], between={'write': {'tests/test_discount.py': 'approved\n'}}, expect={'regex': ['\\?'], 'unchanged': ['tests/test_discount.py']})
        code, out, report = self.run_cases('claude')
        self.assertEqual(report['results'][0]['status'], 'OK', out)

    def test_a_case_level_between_is_checked_when_the_cases_load(self):
        self.case([], between={'git': [['push']]})
        with self.assertRaises(SystemExit) as refused:
            self.run_cases('claude')
        self.assertIn('git push', str(refused.exception))
        self.assertEqual(self.argv(), [])

    def test_a_turn_may_switch_cli_and_then_starts_a_new_session(self):
        """Resume across CLIs (mission, level C): the case sets turn 1's CLI, a later turn names another; no conversation
        crosses CLIs, so that turn starts afresh in the other CLI, in the same repository."""
        self.case([{'cli': 'codex', 'prompt': 'I approved the test yesterday. Go on.', 'expect': {'contains': ['done']}}], cli='claude')
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(code, 0, out)
        calls = self.argv()
        self.assertEqual(len(calls), 2, out)
        self.assertEqual(calls[0][0], '-p')
        self.assertEqual(calls[1][:2], ['exec', '--skip-git-repo-check'])
        self.assertNotIn('resume', calls[1])
        self.assertEqual(report['results'][0].get('turns'), 2)

    def test_a_case_that_sets_its_cli_runs_only_with_that_cli(self):
        self.case([], cli='claude')
        code, out, report = self.run_cases('codex')
        self.assertEqual(report['results'][0]['status'], 'SKIP', out)
        self.assertIn('--cli claude', report['results'][0]['failures'][0])
        self.assertEqual(self.argv(), [])

    def test_an_unknown_cli_in_a_turn_is_refused_when_the_cases_load(self):
        self.case([{'cli': 'cursor', 'prompt': 'Go on.', 'expect': {}}], cli='claude')
        with self.assertRaises(SystemExit) as refused:
            self.run_cases('claude')
        self.assertIn('cursor', str(refused.exception))

    def test_a_between_the_runner_cannot_do_is_an_error_not_a_crash(self):
        self.case([{'between': {'git': [['checkout', 'no-such-branch']]}, 'prompt': 'Go on.', 'expect': {}}])
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done')
        self.assertEqual(report['results'][0]['status'], 'ERROR', out)
        self.assertIn('could not prepare', report['results'][0]['failures'][0])
        self.assertEqual(len(self.argv()), 1)

    def test_unchanged_passes_on_an_untouched_file_and_fails_on_a_deleted_one(self):
        self.case([{'prompt': 'Go on.', 'expect': {'unchanged': ['orders.py']}},
                   {'between': {'delete': ['orders.py']}, 'prompt': 'Again.', 'expect': {'unchanged': ['orders.py']}}])
        code, out, report = self.run_cases('claude', STAND_IN_ANSWERS='Which discount? ||done||done')
        self.assertEqual(report['results'][0]['turns'], 3, out)
        self.assertIn('turn 3: changed: orders.py', out)

    def test_single_turn_command_lines_are_exactly_the_previous_ones(self):
        plain = {'prompt': '/build x'}
        self.assertEqual(evals_run.cli_command('codex', 'codex', plain, 60, None, 'default'),
                         ['codex', 'exec', '--skip-git-repo-check', '--color', 'never', '-s', 'read-only', '$build x'])
        # 2026-11-22, contract changed on purpose: a read-only case lets the agent read git (status, branch, log, diff), as
        # Codex's read-only sandbox and Antigravity's --sandbox do; writes stay disallowed.
        self.assertEqual(evals_run.cli_command('claude', 'claude', plain, 60, None, 'default'),
                         ['claude', '-p', '/build x', '--disallowedTools', 'Write,Edit,NotebookEdit',
                          '--allowedTools', 'Bash(git status:*)', 'Bash(git branch:*)', 'Bash(git log:*)', 'Bash(git diff:*)'])

    def test_a_writable_claude_case_may_run_the_tests_and_git_only(self):
        """Increment 2 (correction loop): the agent must run the checks itself; print mode cannot ask, so the writable case
        allows the test runner and git, and nothing else of the shell (decided 2026-11-21)."""
        command = evals_run.cli_command('claude', 'claude', {'prompt': '/build x', 'sandbox': 'workspace-write'}, 60, None, 'default')
        self.assertIn('--allowedTools', command)
        allowed = command[command.index('--allowedTools') + 1:]
        allowed = allowed[:next((i for i, a in enumerate(allowed) if a.startswith('--')), len(allowed))]
        # 4.24, contract changed on purpose: the kit's proof script too, which the verifier runs (case 31); nothing else of the shell.
        self.assertEqual(sorted(allowed), ['Bash(git:*)', 'Bash(python -m pytest:*)', 'Bash(python ~/.ai-kit/bin/prove_test.py:*)',
                                           'Bash(python3 -m pytest:*)', 'Bash(python3 ~/.ai-kit/bin/prove_test.py:*)'])
        plain = evals_run.cli_command('claude', 'claude', {'prompt': '/build x'}, 60, None, 'default')
        # A read-only case reads git only (contract changed on purpose 2026-11-22): no test runner, no write.
        self.assertFalse([a for a in plain if 'pytest' in a], plain)
        self.assertIn('Write,Edit,NotebookEdit', plain)

    def test_gemini_may_read_git_and_nothing_else_of_the_shell(self):
        """2026-11-22, Gemini CLI 0.65.0, four paid probes: a global deny of run_shell_command removes the tool (an allow rule
        is never reached); a [[rule]] with commandPrefix and decision = "allow" runs git status and git branch, and refuses
        touch, and git status && touch."""
        policy = (ROOT/'evals/policy.toml').read_text(encoding='utf-8')
        self.assertNotRegex(policy, r'name = "Deny shell"')
        self.assertIn('commandPrefix = ["git status", "git branch", "git log", "git diff"]', policy)
        self.assertIn('decision = "allow"', policy)
        for denied in ('write_file', 'replace'):
            self.assertRegex(policy, r'action = "deny"\ntoolName = "' + denied + '"')

    def test_agy_runs_every_case_in_its_sandbox(self):
        """2026-11-21, agy 1.5.14: print mode refuses every shell command the person has not approved word for word, and
        drops the whole answer; --sandbox lets them run (the plan mode refuses them too). agy may then write in the case's copy."""
        for case in ({'prompt': '/build x'}, {'prompt': '/build x', 'sandbox': 'workspace-write'}):
            command = evals_run.cli_command('agy', 'agy', case, 60, None, 'default')
            self.assertIn('--sandbox', command)
            self.assertNotIn('--dangerously-skip-permissions', command)
            self.assertNotIn('--mode', command)

    def test_a_writable_claude_case_accepts_file_edits(self):
        """Print mode cannot answer a permission prompt: without it, a case that must write fails for a reason that is not the kit."""
        command = evals_run.cli_command('claude', 'claude', {'prompt': '/build x', 'sandbox': 'workspace-write'}, 60, None, 'default')
        self.assertEqual(command[command.index('--permission-mode') + 1], 'acceptEdits')

    def test_the_samples_of_later_turns_are_checked_too(self):
        """A turn's samples, like a case's: the "pass" answers pass check(), the "fail" ones fail it. No model call."""
        turns = [(c['name'], t) for c in evals_run.load_cases(ROOT/'evals'/'cases') for t in c.get('turns', []) if t.get('samples')]
        self.assertGreaterEqual(len(turns), 1)
        for name, turn in turns:
            for answer in turn['samples'].get('pass', []):
                with self.subTest(case=name, answer=answer):
                    self.assertEqual(evals_run.check(answer, turn['expect']), [])
            for answer in turn['samples'].get('fail', []):
                with self.subTest(case=name, answer=answer):
                    self.assertNotEqual(evals_run.check(answer, turn['expect']), [])

    def test_a_single_turn_case_keeps_its_command_and_reports_turns_and_duration(self):
        plain = {'prompt': '/build x'}
        # 2026-11-22, contract changed on purpose: an ephemeral Codex session cannot start a sub-agent ("collab spawn failed:
        # ... no rollout found for thread id"), so no case runs ephemeral; the kit's reviewers then run as for a person.
        self.assertNotIn('--ephemeral', evals_run.cli_command('codex', 'codex', plain, 60, None, 'default'))
        self.assertNotIn('-c', evals_run.cli_command('claude', 'claude', plain, 60, None, 'default'))
        (self.cases/'single.json').write_text(json.dumps({'name': 'single', 'prompt': '/build x', 'expect': {'regex': ['\\?']}}), encoding='utf-8')
        code, out, report = self.run_cases('claude')
        self.assertEqual(code, 0, out)
        self.assertEqual(report['results'][0].get('turns'), 1)
        self.assertIsInstance(report['results'][0].get('duration_s'), float)


class ReportAndSandboxTests(unittest.TestCase):
    """4.15.1: the report keeps the end of a long answer; a case may ask for a sandbox the agent can write in."""

    def test_the_report_keeps_the_start_and_the_end(self):
        self.assertTrue(hasattr(evals_run, 'kept_output'), 'the runner has no kept_output')
        long = 'START' + 'x' * 30000 + 'FINAL ANSWER'
        kept = evals_run.kept_output(long)
        self.assertLessEqual(len(kept), 12100)
        self.assertTrue(kept.startswith('START'))
        self.assertTrue(kept.endswith('FINAL ANSWER'))
        self.assertIn('characters cut', kept)
        self.assertEqual(evals_run.kept_output('short'), 'short')

    def test_a_case_can_ask_for_a_writable_sandbox(self):
        plain = {'prompt': '/build x'}
        writable = {'prompt': '/build x', 'sandbox': 'workspace-write'}
        codex = evals_run.cli_command('codex', 'codex', plain, 60, None, 'default')
        self.assertIn('read-only', codex)
        codex = evals_run.cli_command('codex', 'codex', writable, 60, None, 'default')
        self.assertNotIn('read-only', codex)
        self.assertIn('workspace-write', codex)
        claude = evals_run.cli_command('claude', 'claude', writable, 60, None, 'default')
        self.assertNotIn('--disallowedTools', claude)
        self.assertIn('--disallowedTools', evals_run.cli_command('claude', 'claude', plain, 60, None, 'default'))

    def test_the_proof_case_asks_for_it(self):
        case = json.loads((ROOT/'evals/cases/31-build-proves-the-acceptance-test.json').read_text(encoding='utf-8'))
        self.assertEqual(case.get('sandbox'), 'workspace-write')


class RescoreTests(unittest.TestCase):
    """evals/rescore.py replays the current criteria of a case on answers already recorded, turn by turn, without a model:
    a widened criterion must keep the earlier verdicts (AGENTS.md)."""

    def test_each_turn_of_a_recorded_answer_is_judged_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cases = base/'cases'
            cases.mkdir()
            (cases/'resume.json').write_text(json.dumps({'name': 'resume', 'prompt': '/build x', 'expect': {'regex': ['\\?']},
                                                         'turns': [{'prompt': 'Go on.', 'expect': {'contains': ['3 passed']}}]}), encoding='utf-8')
            output = ('=== turn 1 ===\nApprove this test?\n--- stderr ---\nnoise\n'
                      '=== turn 2 ===\npytest: 2 passed\n--- stderr ---\nquoted 3 passed in stderr only\n')
            report = base/'run.json'
            report.write_text(json.dumps({'meta': {'cli': 'claude'}, 'results': [
                {'name': 'resume', 'status': 'OK', 'output': output},
                {'name': 'gone', 'status': 'OK', 'output': 'x'}]}), encoding='utf-8')
            proc = subprocess.run([sys.executable, str(ROOT/'evals/rescore.py'), '--cases', str(cases), str(report)],
                                  capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertRegex(out, r'resume .*recorded OK')
            self.assertRegex(out, r'turn 1: OK')
            self.assertRegex(out, r'turn 2: FAIL .*3 passed')  # stderr is not the answer
            self.assertIn('gone', out)
            self.assertIn('no such case', out)
            self.assertIn('files not re-checked', out)
