"""scripts/offline_tests.py runs the test files in parallel (one process per file), and reports as unittest does, so that
the CI annotations and the "no model call" guard keep working. 2026-11-21: the Windows jobs took about 7 minutes of a
9-minute run, one process for 872 tests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Each test writes when it starts and ends; two files that overlap in time ran at the same time.
TIMED = '''
import os, time, unittest
from pathlib import Path

class Timed(unittest.TestCase):
    def {name}(self):
        log = Path(os.environ['TIMES'])/'{file}'
        log.write_text(str(time.time()) + '\\n', encoding='utf-8')
        time.sleep(1.5)
        with log.open('a', encoding='utf-8') as out:
            out.write(str(time.time()) + '\\n')
{extra}'''


class ParallelRunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.suite = self.base/'suite'
        self.suite.mkdir()
        self.times = self.base/'times'
        self.times.mkdir()
        (self.suite/'test_alpha.py').write_text(TIMED.format(name='test_alpha_passes', file='alpha', extra=''), encoding='utf-8')
        failing = textwrap.indent(textwrap.dedent('''
            def test_beta_fails(self):
                self.assertEqual(1, 2)
            '''), '    ')
        (self.suite/'test_beta.py').write_text(TIMED.format(name='test_beta_passes', file='beta', extra=failing), encoding='utf-8')

    def run_suite(self, **env):
        environment = {**os.environ, 'TIMES': str(self.times), **env}
        proc = subprocess.run([sys.executable, str(ROOT/'scripts'/'offline_tests.py'), 'discover', '-s', str(self.suite), '-v'],
                              capture_output=True, text=True, encoding='utf-8', env=environment, cwd=ROOT, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def spans(self):
        return [tuple(float(x) for x in (self.times/name).read_text(encoding='utf-8').split()) for name in ('alpha', 'beta')]

    def test_test_files_run_at_the_same_time(self):
        code, out = self.run_suite(AI_KIT_TEST_JOBS='2')
        (a_start, a_end), (b_start, b_end) = self.spans()
        self.assertTrue(a_start < b_end and b_start < a_end, 'the two files ran one after the other:\n' + out)

    def test_the_report_reads_like_unittest_for_the_ci_annotations(self):
        code, out = self.run_suite(AI_KIT_TEST_JOBS='2')
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r'(?m)^FAIL: test_beta_fails ')
        self.assertRegex(out, r'(?m)^Ran 3 tests in ')
        self.assertRegex(out, r'(?m)^FAILED \(failures=1\)$')
        self.assertIn('No call to gemini, agy, codex or claude during the tests.', out)

    def test_output_the_console_cannot_encode_does_not_stop_the_run(self):
        """CI of c00ffb5 on Windows: a test printed a character cp1252 cannot encode and the runner died rewriting it."""
        (self.suite/'test_gamma.py').write_text('import unittest\n\nclass Text(unittest.TestCase):\n'
                                               '    def test_prints(self):\n        print("\u2713 \u2260 \u2192")\n', encoding='utf-8')
        code, out = self.run_suite(AI_KIT_TEST_JOBS='2', PYTHONIOENCODING='cp1252')
        self.assertNotIn('UnicodeEncodeError', out)
        self.assertRegex(out, r'(?m)^Ran 4 tests in ')
        self.assertEqual(code, 1, out)  # test_beta_fails, and nothing else

    def test_one_job_runs_the_files_one_after_the_other(self):
        code, out = self.run_suite(AI_KIT_TEST_JOBS='1')
        (a_start, a_end), (b_start, b_end) = self.spans()
        self.assertTrue(a_end <= b_start or b_end <= a_start, 'the files overlapped with one job:\n' + out)
        self.assertEqual(code, 1, out)


if __name__ == '__main__':
    unittest.main()
