"""scripts/cli_drift.py, against stand-in CLIs: no real CLI and no model is called."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cli_drift', ROOT/'scripts/cli_drift.py')
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


@unittest.skipIf(sys.platform == 'win32', 'stand-ins are shell scripts')
class DriftTests(unittest.TestCase):
    def stand_in(self, folder, name, version, help_text):
        path = Path(folder)/name
        path.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "' + version + '"; else echo "' + help_text + '"; fi\n', encoding='utf-8')
        path.chmod(0o755)

    def run_drift(self, folder):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'PATH': folder}), contextlib.redirect_stdout(out):
            code = drift.main([])
        return code, out.getvalue()

    def test_an_option_gone_fails_and_a_newer_version_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            self.stand_in(folder, 'claude', '9.0.0 (Claude Code)', '-p, --print  --model <m>')  # --disallowedTools gone
            self.stand_in(folder, 'codex', 'codex-cli 9.0.0', '--skip-git-repo-check --ephemeral --color --sandbox <mode>')
            code, out = self.run_drift(folder)
        self.assertEqual(code, 1)
        self.assertIn('[Broken] Claude Code 9.0.0', out)
        self.assertIn('--disallowedTools', out)
        self.assertIn('[Newer] Codex CLI 9.0.0', out)
        self.assertIn('[Skip] Gemini CLI: not installed', out)

    def test_an_option_is_matched_whole(self):
        with tempfile.TemporaryDirectory() as folder:
            self.stand_in(folder, 'claude', '1.0.0', '--print --model --disallowedToolsList')
            code, out = self.run_drift(folder)
        self.assertEqual(code, 1)

    def test_every_adapter_declares_a_verified_version_shown_in_the_matrix(self):
        matrix = (ROOT/'docs/cli/matrice.md').read_text(encoding='utf-8')
        for adapter in drift.ADAPTERS:
            self.assertIn(adapter.NAME, drift.RELIED_ON)
            row = next(line for line in matrix.splitlines() if line.startswith('| '+adapter.LABEL))
            self.assertIn(adapter.VERIFIED.rsplit('.0', 1)[0] if adapter.VERIFIED.endswith('.0') else adapter.VERIFIED, row, adapter.LABEL)


if __name__ == '__main__':
    unittest.main()
