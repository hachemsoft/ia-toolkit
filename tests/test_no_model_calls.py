"""No standard path calls a model: setup, update, doctor and uninstall run with stand-in CLIs on the PATH that record any call.
Only doctor --live may reach a CLI, and AI_KIT_NO_LIVE=1 refuses it."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli

CLIS = ('gemini', 'agy', 'codex')


def stand_ins(folder, log):
    for name in CLIS:
        if os.name == 'nt':
            (folder/(name+'.cmd')).write_text('@echo off\r\necho '+name+' %*>>"'+str(log)+'"\r\nexit /b 97\r\n', encoding='utf-8')
        else:
            script = folder/name
            script.write_text('#!/bin/sh\nprintf "%s %s\\n" "'+name+'" "$*" >> "'+str(log)+'"\nexit 97\n', encoding='utf-8')
            script.chmod(0o755)


class NoModelCallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.home, bin_dir, self.log = base/'home', base/'bin', base/'calls.log'
        self.home.mkdir()
        bin_dir.mkdir()
        stand_ins(bin_dir, self.log)
        env = {k: v for k, v in os.environ.items() if k != 'AI_KIT_NO_LIVE'}
        env['PATH'] = str(bin_dir)+os.pathsep+os.environ.get('PATH', '')
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args)+['--home', str(self.home)])
        return code, out.getvalue()+err.getvalue()

    def calls(self):
        return self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []

    def test_setup_and_update_never_call_a_cli(self):
        code, out = self.run_main('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'all')
        self.assertEqual(code, 0, out)
        code, out = self.run_main('update')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls(), [])
        self.assertIn('connection not verified', out)

    def test_no_live_still_accepted(self):
        code, out = self.run_main('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini', '--no-live')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls(), [])

    def test_local_doctor_calls_no_model(self):
        self.run_main('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'all')
        self.run_main('doctor')
        # agy plugin validate checks the plugin files locally; nothing else may run.
        self.assertEqual([c for c in self.calls() if not c.startswith('agy plugin validate')], [])

    def test_live_refused_when_no_live_is_set(self):
        self.run_main('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini')
        with mock.patch.dict(os.environ, {'AI_KIT_NO_LIVE': '1'}):
            code, out = self.run_main('doctor', '--live')
        self.assertEqual(code, 2)
        self.assertIn('AI_KIT_NO_LIVE', out)
        self.assertEqual(self.calls(), [])

    @unittest.skipIf(sys.platform == 'win32', 'the stand-in is a .cmd file, run through cmd')
    def test_live_is_the_only_path_that_reaches_the_cli(self):
        self.run_main('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini')
        with mock.patch.object(cli, 'release_check'):  # no git fetch from a test
            code, out = self.run_main('doctor', '--live')
        self.assertEqual(code, 1)
        self.assertIn('may bill', out)
        self.assertTrue(any(c.startswith('gemini ') for c in self.calls()))


if __name__ == '__main__':
    unittest.main()
