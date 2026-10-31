"""The evaluation runner, against a stand-in CLI: no model is called. A real run needs --confirm-paid-run."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
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

    def test_every_prepared_case_is_valid_and_its_fixture_exists(self):
        cases = evals_run.load_cases(ROOT/'evals/cases')
        self.assertGreaterEqual(len(cases), 12)
        for case in cases:
            self.assertIn('requires', case, case['name'])
            if case.get('cwd'):
                self.assertTrue((ROOT/'evals/fixtures'/case['cwd']).is_dir(), case['name'])
            for kind in ('contains', 'not_contains', 'regex', 'files_absent', 'files_present'):
                self.assertIsInstance(case['expect'].get(kind, []), list, case['name'])

    def test_unmet_precondition_skips_without_calling(self):
        self.case(requires={'profile': 'data-analyst', 'commands': ['intent']})
        code, out = self.run_cases('--stand-in', str(self.stand_in))
        self.assertIn('[SKIP]', out)
        self.assertIn('profile data-analyst', out)
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


if __name__ == '__main__':
    unittest.main()
