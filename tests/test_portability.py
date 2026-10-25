"""Tests run on the host OS; no OS simulation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kit space é ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'User café'

    def run_cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, '-m', 'installer', *args, '--home', str(self.home), '--no-live'],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONIOENCODING':'utf-8'})
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc

    def test_native_cli_lifecycle_in_unicode_path(self):
        self.run_cli('setup', '--profile', 'data-analyst')
        state = self.home / '.ai-kit/state.json'
        self.assertEqual(json.loads(state.read_text(encoding='utf-8'))['profile'], 'data-analyst')
        prefs = self.home / '.gemini/30_USER.md'
        self.assertTrue(prefs.exists())
        prefs.write_text('Answer concisely. Personal preference.', encoding='utf-8')
        self.run_cli('update')
        self.assertIn('Personal preference', prefs.read_text(encoding='utf-8'))
        self.assertTrue((self.home / '.gemini/00_KIT.md').exists())
        names = json.loads((self.home / '.gemini/settings.json').read_text(encoding='utf-8'))['context']['fileName']
        self.assertEqual(names[:6], ['00_KIT.md','10_COMPANY.md','20_TEAM.md','30_USER.md','GEMINI.md','AGENTS.md'])
        self.run_cli('setup', '--profile', 'data-developer')
        self.assertTrue((self.home / '.gemini/skills/sql-review/SKILL.md').exists())
        self.assertTrue((self.home / '.gemini/skills/python-js-change/SKILL.md').exists())
        self.run_cli('setup', '--profile', 'data-analyst')
        self.assertFalse((self.home / '.gemini/skills/python-js-change/SKILL.md').exists())
        p = subprocess.run([sys.executable,'-m','installer','doctor','--home',str(self.home)],
                           cwd=ROOT,capture_output=True,text=True,encoding='utf-8',
                           env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        self.assertIn(p.returncode, (0,1), p.stdout+p.stderr)
        self.assertIn('Local diagnosis only',p.stdout)

    def test_native_cli_dry_run(self):
        self.run_cli('setup','--profile','data-developer','--dry-run')
        self.assertFalse(self.home.exists())

    def test_native_error_code_and_no_overwrite(self):
        cfg = self.home / '.gemini/settings.json'
        cfg.parent.mkdir(parents=True)
        cfg.write_text('{invalid',encoding='utf-8')
        self.run_cli('setup','--profile','data-analyst',code=2)
        self.assertEqual(cfg.read_text(encoding='utf-8'),'{invalid')

    def test_python_sources_support_39_syntax(self):
        import ast
        for source in (ROOT/'installer').rglob('*.py'):
            ast.parse(source.read_text(encoding='utf-8'),feature_version=(3,9))

    @unittest.skipIf(os.name == 'nt', 'Shell launcher on Unix only')
    def test_native_shell_launcher_from_outside_repo(self):
        proc = subprocess.run(['sh', str(ROOT/'scripts/bootstrap.sh'), 'setup',
                               '--profile','data-analyst','--home',str(self.home),'--no-live'],
                              cwd=self.base,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertTrue((self.home/'.ai-kit/state.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Requires a real Windows')
    def test_native_windows_launchers(self):
        # Tests Windows PowerShell 5.1 and PowerShell 7 when they are installed.
        tested=[]
        for engine in ('powershell.exe','pwsh.exe'):
            executable=shutil.which(engine)
            if not executable:
                continue
            target=self.base/engine
            proc=subprocess.run([executable,'-NoProfile','-NonInteractive','-File',
                                 str(ROOT/'scripts/bootstrap.ps1'),'setup','--profile',
                                 'data-developer','--home',str(target),'--no-live'],cwd=self.base,
                                capture_output=True)
            self.assertEqual(proc.returncode,0,repr(proc.stdout)+repr(proc.stderr))
            self.assertTrue((target/'.ai-kit/state.json').exists())
            tested.append(engine)
        self.assertTrue(tested,'No PowerShell available on the Windows runner')

if __name__=='__main__':
    unittest.main()
