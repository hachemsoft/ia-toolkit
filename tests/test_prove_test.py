"""runtime/prove_test.py: the verifier proves that an approved acceptance test fails without the code of the change
(spec docs/sdlc/2026-11-14-kit-agents/spec.md, ADR 0033). Real temporary Git repositories, no model."""
import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'runtime'/'prove_test.py'
sys.path.insert(0, str(ROOT/'tests'))

TEST_FILE = ('import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n'
             'import calc\nassert calc.add(2, 3) == 5, "add is wrong"\n')


class Repo:
    """A Git repository in a temporary folder: files committed on main, then changed and left uncommitted."""

    def __init__(self, files):
        self.path = Path(tempfile.mkdtemp())
        self.git('init', '--quiet', '--initial-branch=main')
        self.write(files)
        self.git('add', '-A')
        self.git('commit', '--quiet', '-m', 'base')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@example.org', '-c', 'commit.gpgsign=false', *args],
                              cwd=self.path, check=True, capture_output=True, text=True).stdout

    def write(self, files):
        for rel, text in files.items():
            target = self.path/rel
            if text is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')

    def state(self):
        """Every file outside .git, byte for byte, plus what git reports: what must be identical before and after."""
        files = {str(p.relative_to(self.path)): p.read_bytes() for p in self.path.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.path).parts}
        return files, self.git('status', '--porcelain')

    def git_dir(self):
        return {str(p): p.read_bytes() for p in (self.path/'.git').rglob('*') if p.is_file() and p.name != 'index'}

    def cmd(self, *args):
        return [sys.executable, '-I', str(SCRIPT), '--repo', str(self.path), *args]

    def run(self, *args, timeout=120):
        proc = subprocess.run(self.cmd(*args), capture_output=True, text=True, timeout=timeout)
        return proc.returncode, json.loads(proc.stdout)

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


def calc_repo(case, test_text=TEST_FILE):
    """Base: add() is wrong. Change (uncommitted): add() fixed, and a new acceptance test."""
    repo = Repo({'calc.py': 'def add(a, b):\n    return a - b\n'})
    case.addCleanup(repo.cleanup)
    repo.write({'calc.py': 'def add(a, b):\n    return a + b\n', 'tests/test_calc.py': test_text})
    return repo


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class ProveTests(unittest.TestCase):
    """T1, R1, R3, R4: the verdict, and a working tree identical byte for byte after the proof."""

    def test_a_test_that_needs_the_code_is_proven(self):
        repo = calc_repo(self)
        before, git_before = repo.state(), repo.git_dir()
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual((code, out['verdict']), (0, 'proven'), out)
        self.assertEqual(out['swapped'], ['calc.py'])
        self.assertIn('add is wrong', out['output_tail'])
        self.assertEqual(repo.state(), before)
        self.assertEqual(repo.git_dir(), git_before)
        self.assertFalse((repo.path/'.ai-kit-proof').exists())

    def test_a_test_that_passes_without_the_code_is_not_proven(self):
        repo = calc_repo(self, test_text='assert True\n')
        before = repo.state()
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual((code, out['verdict']), (0, 'not_proven'), out)
        self.assertEqual(repo.state(), before)


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class SafetyTests(unittest.TestCase):
    """T2, R4: the files come back after a timeout or an interruption; a backup left by a hard stop blocks until recover."""

    def test_restored_after_a_timeout(self):
        repo = calc_repo(self)
        before = repo.state()
        code, out = repo.run('prove', '--timeout', '1', '--test', 'tests/test_calc.py', '--', sys.executable, '-c', 'import time; time.sleep(30)')
        self.assertEqual(out['verdict'], 'timeout', out)
        self.assertEqual(repo.state(), before)

    @unittest.skipIf(os.name == 'nt', 'POSIX signals')
    def test_restored_after_an_interruption(self):
        repo = calc_repo(self)
        before = repo.state()
        proc = subprocess.Popen(repo.cmd('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-c', 'import time; time.sleep(30)'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_for_backup(repo)
        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=60)
        self.assertEqual(repo.state(), before)

    @unittest.skipIf(os.name == 'nt', 'POSIX signals')
    def test_a_hard_stop_leaves_a_backup_that_blocks_until_recover(self):
        repo = calc_repo(self)
        before = repo.state()
        proc = subprocess.Popen(repo.cmd('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-c', 'import time; time.sleep(30)'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_for_backup(repo)
        proc.kill()
        proc.communicate(timeout=60)
        self.assertNotEqual((repo.path/'calc.py').read_bytes(), before[0]['calc.py'])  # still swapped
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual(code, 2)
        self.assertIn('recover', out['error'])
        code, out = repo.run('recover')
        self.assertEqual(code, 0, out)
        self.assertEqual(repo.state(), before)

    def wait_for_backup(self, repo):
        for _ in range(200):
            if (repo.path/'.ai-kit-proof'/'manifest.json').is_file() and (repo.path/'calc.py').read_text(encoding='utf-8').endswith('a - b\n'):
                return
            time.sleep(0.05)
        self.fail('the proof never started')


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class ModesTests(unittest.TestCase):
    """R1, R2, R3, R6, R7: what counts as a test, the other modes, files added, deleted and renamed."""

    def repo(self, files):
        repo = Repo(files)
        self.addCleanup(repo.cleanup)
        return repo

    def test_what_counts_as_a_test(self):
        sys.path.insert(0, str(ROOT/'runtime'))
        import prove_test
        for path in ('tests/a.py', 'src/__tests__/a.js', 'test_a.py', 'a_test.py', 'a_test.go', 'a.test.ts', 'a.spec.tsx',
                     'src/ATest.java', 'src/ATests.java', 'src/ASpec.scala', 'src/ATest.php', 'spec/a_spec.rb'):
            self.assertTrue(prove_test.is_test_path(path), path)
        for path in ('src/a.py', 'latest.py', 'contest/a.py', 'src/Testing.java', 'models/a.sql'):
            self.assertFalse(prove_test.is_test_path(path), path)
        self.assertTrue(prove_test.is_test_path('checks/acceptance.py', ['checks/acceptance.py']))

    def test_added_deleted_and_renamed_code_files_are_swapped_and_restored(self):
        repo = self.repo({'old.py': 'X = 1\n', 'gone.py': 'Y = 2\n', 'deep/keep.py': 'Z = 3\n'})
        repo.git('mv', 'old.py', 'new.py')
        repo.write({'gone.py': None, 'added/mod.py': 'W = 4\n', 'deep/keep.py': 'Z = 30\n', 'tests/test_x.py': 'assert True\n'})
        before = repo.state()
        script = ('import pathlib, sys; p = pathlib.Path(".");'
                  'sys.exit(0 if (p/"old.py").exists() and (p/"gone.py").exists() and not (p/"new.py").exists()'
                  ' and not (p/"added/mod.py").exists() and (p/"deep/keep.py").read_text() == "Z = 3\\n" else 1)')
        code, out = repo.run('prove', '--test', 'tests/test_x.py', '--', sys.executable, '-B', '-c', script)
        self.assertEqual(out['verdict'], 'not_proven', out)  # the command saw the base state, so it passed
        self.assertEqual(set(out['swapped']), {'old.py', 'new.py', 'gone.py', 'added/mod.py', 'deep/keep.py'})
        self.assertEqual(repo.state(), before)
        self.assertEqual(repo.run('recover')[1]['verdict'], 'nothing_to_recover')

    def test_keep_leaves_a_file_at_its_new_version(self):
        repo = calc_repo(self)
        repo.write({'config.ini': 'x\n'})
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--keep', 'config.ini', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual((out['verdict'], out['swapped'], out['kept']), ('proven', ['calc.py'], ['config.ini']), out)

    def test_not_possible_cases(self):
        repo = calc_repo(self)
        code, out = repo.run('prove', '--test', 'tests/other.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual((code, out['verdict']), (0, 'not_possible'))
        self.assertIn('tests/other.py', out['reason'])
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', 'no-such-command-ai-kit')
        self.assertEqual(out['verdict'], 'not_possible')
        self.assertIn('command not found', out['reason'])
        only_tests = self.repo({'calc.py': 'x = 1\n'})
        only_tests.write({'tests/test_calc.py': 'assert True\n'})
        code, out = only_tests.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual(out['verdict'], 'not_possible')
        self.assertIn('no code file', out['reason'])

    def test_base_run_tells_new_failures_from_old_ones(self):
        repo = calc_repo(self)
        before = repo.state()
        code, out = repo.run('base-run', '--', sys.executable, '-B', '-c', 'import calc; assert calc.add(2, 3) == 5')
        self.assertEqual(out['verdict'], 'fails_on_base', out)
        code, out = repo.run('base-run', '--', sys.executable, '-B', '-c', 'import pathlib; assert not pathlib.Path("tests/test_calc.py").exists()')
        self.assertEqual(out['verdict'], 'passes_on_base', out)  # tests are put back to the base too
        self.assertEqual(repo.state(), before)

    def test_modified_tests_lists_existing_tests_only(self):
        repo = self.repo({'tests/test_a.py': 'assert 1\n', 'tests/test_b.py': 'assert 2\n', 'src/a.py': 'x = 1\n'})
        repo.write({'tests/test_a.py': 'assert True\n', 'tests/test_b.py': None, 'tests/test_new.py': 'assert 3\n', 'src/a.py': 'x = 2\n'})
        code, out = repo.run('modified-tests')
        self.assertEqual(code, 0, out)
        self.assertEqual(out['tests'], [{'path': 'tests/test_a.py', 'change': 'modified'}, {'path': 'tests/test_b.py', 'change': 'deleted'}])

    def test_recover_with_nothing_to_recover_and_outside_a_repo(self):
        repo = calc_repo(self)
        self.assertEqual(repo.run('recover')[1]['verdict'], 'nothing_to_recover')
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', tmp, 'recover'], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(json.loads(proc.stdout)['error'])


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class ReviewFindingsTests(unittest.TestCase):
    """The defects the cold review of 4.12.0 found, one test each."""

    def test_the_executable_bit_comes_back(self):
        if os.name == 'nt':
            self.skipTest('POSIX modes')
        repo = calc_repo(self)
        os.chmod(repo.path/'calc.py', 0o755)
        before = repo.state()
        self.assertEqual(repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')[1]['verdict'], 'proven')
        self.assertEqual(repo.state(), before)
        self.assertTrue(os.stat(repo.path/'calc.py').st_mode & 0o100)

    def test_a_link_in_the_change_makes_the_proof_not_possible(self):
        if os.name == 'nt':
            self.skipTest('links need rights on Windows')
        repo = calc_repo(self)
        os.symlink('calc.py', repo.path/'alias.py')
        before = repo.state()
        out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')[1]
        self.assertEqual(out['verdict'], 'not_possible', out)
        self.assertIn('alias.py', out['reason'])
        self.assertTrue((repo.path/'alias.py').is_symlink())
        self.assertEqual(repo.state(), before)

    def test_from_a_subfolder_paths_stay_rooted(self):
        repo = Repo({'app/calc.py': 'def add(a, b):\n    return a - b\n'})
        self.addCleanup(repo.cleanup)
        repo.write({'app/calc.py': 'def add(a, b):\n    return a + b\n', 'app/tests/test_calc.py': TEST_FILE})
        before = repo.state()
        proc = subprocess.run([sys.executable, '-I', str(SCRIPT), 'prove', '--test', 'tests/test_calc.py', '--',
                               sys.executable, '-B', 'tests/test_calc.py'], cwd=repo.path/'app', capture_output=True, text=True, timeout=120)
        out = json.loads(proc.stdout)
        self.assertEqual((out['verdict'], out['swapped']), ('proven', ['app/calc.py']), out)
        self.assertEqual(repo.state(), before)
        self.assertFalse((repo.path/'app/app').exists())

    def test_a_file_saved_during_the_run_is_kept_and_reported(self):
        repo = calc_repo(self)
        edit = 'import pathlib; pathlib.Path("calc.py").write_text("def add(a, b):\\n    return 99\\n"); raise SystemExit(1)'
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', '-c', edit)
        self.assertEqual(code, 2, out)
        self.assertIn('changed during the run', out['error'])
        self.assertEqual((repo.path/'calc.py').read_text(encoding='utf-8'), 'def add(a, b):\n    return 99\n')
        self.assertTrue((repo.path/'.ai-kit-proof'/'manifest.json').is_file())

    def test_recover_refuses_a_planted_manifest(self):
        repo = calc_repo(self)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        (outside/'precious.txt').write_text('keep me', encoding='utf-8')
        folder = repo.path/'.ai-kit-proof'
        folder.mkdir()
        rel = os.path.relpath(outside/'precious.txt', repo.path).replace(os.sep, '/')
        (folder/'manifest.json').write_text(json.dumps({'files': [{'path': rel, 'existed': False, 'swapped': None}]}), encoding='utf-8')
        code, out = repo.run('recover')
        self.assertEqual(code, 2)
        self.assertIn('refused', out['error'])
        self.assertTrue((outside/'precious.txt').is_file())

    def test_a_warehouse_command_needs_a_target(self):
        repo = calc_repo(self)
        fake = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, fake, True)
        name = 'dbt.bat' if os.name == 'nt' else 'dbt'
        (fake/name).write_text('@exit /b 0\n' if os.name == 'nt' else '#!/bin/sh\nexit 0\n', encoding='utf-8')
        os.chmod(fake/name, 0o755)
        env = dict(os.environ, PATH=str(fake)+os.pathsep+os.environ.get('PATH', ''))
        proc = subprocess.run(repo.cmd('prove', '--test', 'tests/test_calc.py', '--', 'dbt', 'build', '-s', 'orders'),
                              capture_output=True, text=True, timeout=60, env=env)
        out = json.loads(proc.stdout)
        self.assertEqual(out['verdict'], 'not_possible', out)
        self.assertIn('--target', out['reason'])

    @unittest.skipIf(os.name == 'nt', 'POSIX process groups')
    def test_the_timeout_stops_the_children_too(self):
        repo = calc_repo(self)
        before = repo.state()
        child = 'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]); import time; time.sleep(60)'
        started = time.monotonic()
        code, out = repo.run('prove', '--timeout', '1', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', '-c', child)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(out['verdict'], 'timeout', out)
        self.assertEqual(repo.state(), before)

    @unittest.skipIf(os.name == 'nt', 'POSIX signals')
    def test_restored_after_sigterm(self):
        repo = calc_repo(self)
        before = repo.state()
        proc = subprocess.Popen(repo.cmd('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-c', 'import time; time.sleep(30)'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        SafetyTests.wait_for_backup(self, repo)
        proc.terminate()
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 130)
        self.assertEqual(repo.state(), before)
        self.assertFalse((repo.path/'.ai-kit-proof').exists())

    def test_a_second_run_waits_for_the_first(self):
        repo = calc_repo(self)
        (repo.path/'.ai-kit-proof').mkdir()  # a run in progress, before its manifest
        code, out = repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual(code, 2)
        self.assertIn('running', out['error'])
        self.assertTrue((repo.path/'.ai-kit-proof').is_dir())

    def test_the_index_is_untouched(self):
        repo = calc_repo(self)
        repo.git('add', 'calc.py')
        staged = repo.git('diff', '--cached')
        repo.run('prove', '--test', 'tests/test_calc.py', '--', sys.executable, '-B', 'tests/test_calc.py')
        self.assertEqual(repo.git('diff', '--cached'), staged)


class WiringTests(unittest.TestCase):
    """T3, R5, R8, R10, R11: the verifier, /build and the MR body use the proof; the script is installed."""

    def read(self, rel):
        return (ROOT/rel).read_text(encoding='utf-8')

    def test_the_verifier_runs_the_proof(self):
        verifier = self.read('agents/internal/common/verifier.md')
        for words in ('prove_test.py prove', 'not_proven', 'prove_test.py recover', 'prove_test.py base-run',
                      'prove_test.py modified-tests', 'already failing on the base', 'development target', 'one agreement'):
            self.assertIn(words, verifier)

    def test_build_stops_when_the_test_proves_nothing(self):
        self.assertIn('passes without the code', self.read('commands/build.md'))
        self.assertIn('fails without the code', self.read('skills/internal/common/mr/SKILL.md'))

    def test_installed_next_to_weakened_tests(self):
        from presets import apply_as
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', Path(tmp), False, None, 'gemini')
            self.assertTrue((Path(tmp)/'.ai-kit'/'bin'/'prove_test.py').is_file())


if __name__ == '__main__':
    unittest.main()
