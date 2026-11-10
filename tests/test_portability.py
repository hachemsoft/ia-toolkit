"""Tests run on the host OS; no OS simulation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import wheelhouse

ROOT = Path(__file__).resolve().parents[1]

class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kit space é ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'User café'

    def run_cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, '-m', 'installer', *args, '--home', str(self.home)],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONIOENCODING':'utf-8'})
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc

    def test_native_cli_lifecycle_in_unicode_path(self):
        self.run_cli('init', '--target', 'gemini')
        self.assertTrue((self.home / '.ai-kit/state.json').is_file())
        prefs = self.home / '.gemini/USER.md'
        self.assertTrue(prefs.exists())
        prefs.write_text('Answer concisely. Personal preference.', encoding='utf-8')
        self.run_cli('init')  # installed: checks and re-applies
        self.assertIn('Personal preference', prefs.read_text(encoding='utf-8'))
        self.assertTrue((self.home / '.gemini/00_KIT.md').exists())
        names = json.loads((self.home / '.gemini/settings.json').read_text(encoding='utf-8'))['context']['fileName']
        self.assertEqual(names[:6], ['00_KIT.md','10_COMPANY.md','20_TEAM.md','USER.md','GEMINI.md','AGENTS.md'])
        # 3.0: no profiles, and no --profile option any more (a usage error).
        refused = self.run_cli('init', '--profile', 'data-developer', code=2)
        self.assertIn('--profile', refused.stderr)
        p = subprocess.run([sys.executable,'-m','installer','doctor','--home',str(self.home)],
                           cwd=ROOT,capture_output=True,text=True,encoding='utf-8',
                           env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        self.assertIn(p.returncode, (0,1), p.stdout+p.stderr)
        self.assertIn('Local diagnosis only',p.stdout)

    def test_native_cli_dry_run(self):
        self.run_cli('init','--target','gemini','--dry-run')
        self.assertFalse(self.home.exists())

    def test_native_error_code_and_no_overwrite(self):
        cfg = self.home / '.gemini/settings.json'
        cfg.parent.mkdir(parents=True)
        cfg.write_text('{invalid',encoding='utf-8')
        proc = self.run_cli('init','--target','gemini',code=1)  # refused, nothing changed
        self.assertIn('settings.json', proc.stderr)
        self.assertEqual(cfg.read_text(encoding='utf-8'),'{invalid')

    def test_python_sources_support_311_syntax(self):
        import ast
        for source in (ROOT/'installer').rglob('*.py'):
            ast.parse(source.read_text(encoding='utf-8'),feature_version=(3,11))

    @unittest.skipIf(os.name == 'nt', 'Shell launcher on Unix only')
    @unittest.skipUnless(wheelhouse.AVAILABLE, wheelhouse.WHY)
    def test_native_shell_launcher_from_outside_repo(self):
        # The launcher installs the engine with pip: from the local wheelhouse, so a contributor needs no package index.
        proc = subprocess.run(['sh', str(ROOT/'scripts/bootstrap.sh'), 'init',
                               '--home',str(self.home),'--target','gemini'],
                              cwd=self.base,capture_output=True,text=True,encoding='utf-8',env={**os.environ, **wheelhouse.pip_env()})
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertTrue((self.home/'.ai-kit/state.json').exists())

if __name__=='__main__':
    unittest.main()
