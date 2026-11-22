"""scripts/vm_tests.py: the model-free suite on a Windows virtual machine, from the Mac, in one command (optional tool, for
a maintainer with a UTM VM). 2026-11-22: the VM found two Windows bugs the CI did not, after three hand-made attempts (a
bundle cloned without its branch, a script without CRLF). Only the parts that need no VM are tested here."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'scripts/vm_tests.py'


def module():
    spec = importlib.util.spec_from_file_location('vm_tests', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class GuestScriptTests(unittest.TestCase):
    def test_the_guest_script_clones_the_branch_and_ends_with_the_exit_code(self):
        self.assertTrue(SCRIPT.is_file(), 'scripts/vm_tests.py is missing')
        text = module().guest_script(r'C:\Python\python.exe', 'main')
        self.assertIn('git clone -q -b main', text)  # without -b the bundle clones nothing
        self.assertIn(r'"C:\Python\python.exe" scripts\offline_tests.py discover -s tests -v', text)
        self.assertIn('EXIT=%ERRORLEVEL%', text)
        self.assertTrue(all(line.endswith('\r') for line in text.split('\n')[:-1]), 'cmd.exe needs CRLF line endings')

    def test_the_log_gives_the_exit_code_and_the_lines_that_matter(self):
        self.assertTrue(SCRIPT.is_file(), 'scripts/vm_tests.py is missing')
        log = ('Python 3.15.2\r\ntest_a (test_x.T.test_a) ... ok\r\nFAIL: test_b (test_x.T.test_b)\r\n'
               'Ran 946 tests in 159.3s (91 files, 4 at a time)\r\nFAILED (failures=1)\r\nEXIT=1 \r\n')
        code, lines = module().summary(log)
        self.assertEqual(code, 1)
        self.assertIn('FAIL: test_b (test_x.T.test_b)', lines)
        self.assertIn('FAILED (failures=1)', lines)
        self.assertNotIn('test_a (test_x.T.test_a) ... ok', lines)
        self.assertEqual(module().summary('Python 3.15.2\r\n'), (None, []))  # still running


if __name__ == '__main__':
    unittest.main()
