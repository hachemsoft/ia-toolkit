"""Gemini CLI on Windows runs every hook through PowerShell -Command, the command followed by
'; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }' (read in its source, 0.65): a quoted program needs the call operator &,
else PowerShell stops on 'Unexpected token -I' and the hook fails at each session start (issue 15)."""
import contextlib, io, shutil, subprocess, tempfile, unittest
from pathlib import Path
from unittest import mock
from installer.cli import doctor
from installer.core import read_json
from installer.adapters import gemini
from presets import apply_as  # noqa: E402

GEMINI_SUFFIX = '; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }'
POWERSHELL = shutil.which('pwsh') or shutil.which('powershell')


def powershell_parse_errors(command):
    """PowerShell's own parser on the script Gemini CLI hands it: the errors, empty when it parses."""
    script = (command+GEMINI_SUFFIX).replace("'", "''")
    probe = "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseInput('"+script+"',[ref]$null,[ref]$e); $e | ForEach-Object { $_.Message }"
    return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', probe], capture_output=True, text=True).stdout.strip()


class GeminiWindowsHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.home = Path(self.temp.name)
        patcher = mock.patch.object(gemini, 'WINDOWS', True); patcher.start(); self.addCleanup(patcher.stop)

    def sync(self):
        with contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', self.home, False, None, 'gemini')

    def commands(self):
        hooks = read_json(self.home/'.gemini/settings.json')['hooks']
        return [h['command'] for groups in hooks.values() for g in groups for h in g['hooks'] if h['name'].startswith('ai-kit-')]

    def test_every_kit_hook_command_runs_under_powershell(self):
        self.sync()
        commands = self.commands()
        self.assertTrue(any('whats-new.py' in c for c in commands), commands)
        for c in commands:
            self.assertTrue(c.startswith('& '), c)
            if POWERSHELL:
                self.assertEqual(powershell_parse_errors(c), '', c)

    def test_second_sync_and_doctor_accept_the_powershell_form(self):
        self.sync(); first = self.commands()
        self.sync()  # raised 'Kit guardrail modified' if the comparison used the stored form
        self.assertEqual(self.commands(), first)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            doctor(self.home)
        self.assertIn('Hook configured in settings.json: whats-new', out.getvalue())
        self.assertNotIn('[FAIL] Hook configured in settings.json', out.getvalue())
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(gemini.changed_blocks(self.home, state), [])

    def test_a_settings_file_written_before_the_fix_is_taken_back(self):
        with mock.patch.object(gemini, 'WINDOWS', False):
            self.sync()
        self.assertFalse(any(c.startswith('& ') for c in self.commands()))
        self.sync()  # the former form is the kit's own: replaced, not reported as edited by hand
        self.assertTrue(all(c.startswith('& ') for c in self.commands()))


if __name__ == '__main__':
    unittest.main()
