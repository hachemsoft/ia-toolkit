"""doctor --live on every CLI: one call through a stand-in for the CLI (no model is ever called here), the same output
reading (network first, then the CLI's own causes), and a fix that points to the CLI, never to overrides.json."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from installer.adapters import agy, claude, codex


def answered(code, out='', err=''):
    return lambda command, timeout, **kw: subprocess.CompletedProcess(command, code, out, err)


class LiveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def live(self, adapter, runner):
        out = io.StringIO()
        with mock.patch('installer.core.run_timed', side_effect=runner) as run, contextlib.redirect_stdout(out):
            code = adapter.live(self.home)
        return code, out.getvalue(), run.call_args[0][0]

    def test_each_cli_answers(self):
        for adapter, start in ((agy, ['agy', '-p']), (codex, ['codex', 'exec']), (claude, ['claude', '-p'])):
            with self.subTest(adapter.NAME):
                code, out, command = self.live(adapter, answered(0, 'OK\n'))
                self.assertEqual(code, 0)
                self.assertIn('[OK] Real call to the model', out)
                self.assertEqual(command[:2], start)

    def test_codex_runs_read_only_and_ephemeral(self):
        command = self.live(codex, answered(0, 'OK'))[2]
        self.assertIn('--ephemeral', command)
        self.assertEqual(command[command.index('-s')+1], 'read-only')

    def test_causes_read_from_the_output(self):
        cases = ((codex, 'Error: Not logged in. Run codex login', 'codex login'),
                 (claude, 'Invalid API key · Please run /login', '/login'),
                 (claude, 'API Error: 529 overloaded', 'Try again'),
                 (agy, 'Error: please log in to continue', 'sign in'),
                 (agy, 'RESOURCE_EXHAUSTED: quota exceeded', 'quota'),
                 (codex, 'error sending request: dns error', 'HTTPS_PROXY'),
                 (claude, 'SELF_SIGNED_CERT_IN_CHAIN', 'Never disable certificate checks'))
        for adapter, output, fix in cases:
            with self.subTest(output):
                code, out, _ = self.live(adapter, answered(1, '', output))
                self.assertEqual(code, 1)
                self.assertIn(fix, out)
                self.assertNotIn('overrides.json', out)

    def test_unknown_failure_and_timeout(self):
        code, out, _ = self.live(agy, answered(3, '', 'something odd'))
        self.assertEqual(code, 1)
        self.assertIn('code 3', out)
        def slow(command, timeout, **kw):
            raise subprocess.TimeoutExpired(command, timeout, output=b'', stderr=b'')
        code, out, _ = self.live(codex, slow)
        self.assertEqual(code, 1)
        self.assertIn('did not answer in time', out)


if __name__ == '__main__':
    unittest.main()
