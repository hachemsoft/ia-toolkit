"""The launcher (scripts/launcher.py): private environment, release ZIP installed with no index, git clone installed with
the pip configuration it finds, no foreign module imported, one run at a time, an interrupted or failed run detected,
nothing configured when the package does not install, update that never overwrites local changes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import wheelhouse

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == 'nt'
spec = importlib.util.spec_from_file_location('kit_launcher', ROOT/'scripts/launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
spec = importlib.util.spec_from_file_location('kit_build_release', ROOT/'scripts/build_release.py')
build_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_release)

# A network that answers nothing: anything that tries to reach a package index fails.
NO_NETWORK = {'PIP_INDEX_URL': 'http://127.0.0.1:9/simple', 'HTTPS_PROXY': 'http://127.0.0.1:9', 'HTTP_PROXY': 'http://127.0.0.1:9'}
_ZIP = {}


def release_zip():
    """The release ZIP built once from the current files (test build), its dependencies taken from the local wheelhouse."""
    if 'path' not in _ZIP:
        folder = Path(tempfile.mkdtemp(prefix='ai-kit-zip-'))
        with mock.patch.dict(os.environ, wheelhouse.pip_env()), mock.patch('sys.stdout'):
            build_release.main(['--worktree', '--out', str(folder)])
        _ZIP['path'] = next(folder.glob('*.zip'))
    return _ZIP['path']


def parasites(folder):
    """Modules named like the kit's and its libraries', that break everything if imported: in the current folder and PYTHONPATH."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('installer.py', 'ai_kit.py', 'rich.py', 'questionary.py', 'venv.py', 'json.py'):
        (folder/name).write_text('raise SystemExit("foreign module imported: '+name+'")\n', encoding='utf-8')
    (folder/'installer').mkdir(exist_ok=True)
    (folder/'installer'/'__init__.py').write_text('raise SystemExit("foreign installer package imported")\n', encoding='utf-8')


@unittest.skipUnless(wheelhouse.AVAILABLE, wheelhouse.WHY)
class LauncherRunTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        # Spaces, accents and parentheses everywhere; the current folder holds parasite modules.
        self.base = Path(temp.name)/'Dossier (test) é'
        self.cwd = self.base/'mon projet'
        parasites(self.cwd)
        self.home_arg = '../Home à'  # relative: resolved from the person's current folder
        self.home = (self.cwd/self.home_arg).resolve()

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith('PIP_')}
        env.update({'AI_KIT_NO_LIVE': '1', 'PYTHONPATH': str(self.cwd)}, **extra)
        return env

    def run_kit(self, kit, *args, env=None):
        command = [str(kit/'Installer.cmd')] if WINDOWS else ['sh', str(kit/'scripts'/'bootstrap.sh')]
        proc = subprocess.run(command+list(args), cwd=self.cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                              env=env or self.env(), stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout+proc.stderr

    def setup_args(self, target='gemini'):
        return ('setup', '--profile', 'general', '--user', 'a@example.org', '--target', target, '--home', self.home_arg)

    def extracted_zip(self):
        kit = self.base/'Kit IA été (v1)'
        with zipfile.ZipFile(release_zip()) as archive:
            archive.extractall(kit)
        return kit

    def repo_copy(self):
        return Path(shutil.copytree(ROOT, self.base/'ai-kit clone', ignore=shutil.ignore_patterns(
            '.git', '__pycache__', 'dist', 'build', '.debug', '.codegraph', '.claude', '.ai-kit')))

    def runtime_python(self):
        return launcher.environment_python(self.home/'.ai-kit'/'runtime'/'venv')

    def test_zip_installs_with_no_index_and_no_network_then_the_folder_can_go(self):
        kit = self.extracted_zip()
        code, out = self.run_kit(kit, *self.setup_args('all'), env=self.env(**NO_NETWORK))
        self.assertEqual(code, 0, out)
        self.assertIn('no download', out)
        self.assertIn('Kit configuration installed', out)
        record = json.loads((self.home/'.ai-kit/runtime/install.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'ready')
        # The guardrails run with the private environment's Python, never with a file of the extracted folder.
        settings = json.loads((self.home/'.gemini/settings.json').read_text(encoding='utf-8'))
        command = settings['hooks']['BeforeTool'][0]['hooks'][0]['command']
        self.assertIn(str(self.runtime_python().parent), command.replace('\\\\', '\\').replace('/', os.sep) if WINDOWS else command)
        shutil.rmtree(kit)
        proc = subprocess.run([str(self.runtime_python()), '-I', '-m', 'ai_kit', 'doctor', '--home', str(self.home)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', env=self.env())
        self.assertNotIn('Traceback', proc.stdout+proc.stderr)
        self.assertIn('Kit configuration: installed', proc.stdout)

    def test_second_run_reuses_the_environment(self):
        kit = self.extracted_zip()
        self.assertEqual(self.run_kit(kit, *self.setup_args())[0], 0)
        code, out = self.run_kit(kit, 'update', '--home', self.home_arg, env=self.env(**NO_NETWORK))
        self.assertEqual(code, 0, out)
        self.assertNotIn('Installing the kit', out)
        self.assertIn('already installed', out)

    def test_clone_installs_with_the_configured_index_and_no_editable(self):
        kit = self.repo_copy()
        code, out = self.run_kit(kit, *self.setup_args(), env=self.env(**wheelhouse.pip_env()))
        self.assertEqual(code, 0, out)
        self.assertIn('configured package index', out)
        probe = subprocess.run([str(self.runtime_python()), '-I', '-c', 'import ai_kit, sys; print(ai_kit.__file__)'], capture_output=True, text=True)
        self.assertIn(str(self.home), probe.stdout)  # installed into the environment, not pointing to the clone
        self.assertNotIn(str(kit), probe.stdout)

    def test_failed_package_install_configures_nothing_and_is_detected_next_time(self):
        kit = self.repo_copy()
        empty = self.base/'empty index'
        empty.mkdir()
        code, out = self.run_kit(kit, *self.setup_args(), env=self.env(PIP_NO_INDEX='1', PIP_FIND_LINKS=str(empty)))
        self.assertEqual(code, 3, out)
        self.assertIn('the agents were not configured', out)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        self.assertFalse((self.home/'.gemini').exists())
        self.assertEqual(json.loads((self.home/'.ai-kit/runtime/install.json').read_text(encoding='utf-8'))['status'], 'failed')
        code, out = self.run_kit(kit, *self.setup_args(), env=self.env(**wheelhouse.pip_env()))
        self.assertEqual(code, 0, out)
        self.assertIn('previous installation of the kit runtime failed', out)

    def test_interrupted_install_is_started_again(self):
        kit = self.extracted_zip()
        record = self.home/'.ai-kit/runtime/install.json'
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({'status': 'installing'}), encoding='utf-8')
        (self.home/'.ai-kit/runtime/venv').mkdir()  # a half-built environment
        code, out = self.run_kit(kit, *self.setup_args())
        self.assertEqual(code, 0, out)
        self.assertIn('did not finish', out)

    def test_zip_update_shows_its_three_steps(self):
        kit = self.extracted_zip()
        self.assertEqual(self.run_kit(kit, *self.setup_args())[0], 0)
        code, out = self.run_kit(kit, 'update', '--home', self.home_arg)
        self.assertEqual(code, 0, out)
        for step in ('Step 1/3', 'Step 2/3', 'Step 3/3'):
            self.assertIn(step, out)

    def test_uninstall_with_runtime_removal_after_the_kit_has_exited(self):
        kit = self.extracted_zip()
        self.assertEqual(self.run_kit(kit, *self.setup_args())[0], 0)
        code, out = self.run_kit(kit, 'uninstall', '--remove-runtime', '--home', self.home_arg)
        self.assertEqual(code, 2, out)  # no terminal and no --yes: refused, nothing removed
        self.assertTrue(self.runtime_python().exists())
        code, out = self.run_kit(kit, 'uninstall', '--yes', '--remove-runtime', '--home', self.home_arg)
        self.assertEqual(code, 0, out)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        self.assertFalse((self.home/'.ai-kit/runtime/venv').exists())
        self.assertTrue((self.home/'.gemini/30_USER.md').exists())
        self.assertIn('Kit runtime removed', out)

    def test_a_second_run_waits_for_the_first(self):
        kit = self.extracted_zip()
        lock = self.home/'.ai-kit/runtime/install.lock'
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({'pid': os.getpid()}), encoding='utf-8')  # this test process: alive
        code, out = self.run_kit(kit, *self.setup_args())
        self.assertEqual(code, 4, out)
        self.assertIn('Another run of the kit installer is in progress', out)
        lock.write_text(json.dumps({'pid': 2**22+12345}), encoding='utf-8')  # a process that no longer exists
        code, out = self.run_kit(kit, *self.setup_args())
        self.assertEqual(code, 0, out)
        self.assertFalse(lock.exists())


@unittest.skipUnless(wheelhouse.AVAILABLE and shutil.which('git'), wheelhouse.WHY+' or no git')
class GitUpdateTests(unittest.TestCase):
    """update in a clone: explicit fetch, fast-forward only, never over local changes, never a false success."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.origin = Path(shutil.copytree(ROOT, self.base/'origin', ignore=shutil.ignore_patterns(
            '.git', '__pycache__', 'dist', 'build', '.debug', '.codegraph', '.claude', '.ai-kit')))
        self.git(self.origin, 'init', '--quiet', '--initial-branch=main')
        self.git(self.origin, 'add', '-A')
        self.git(self.origin, 'commit', '--quiet', '-m', 'v1')
        self.clone = self.base/'clone'
        self.git(self.base, 'clone', '--quiet', str(self.origin), str(self.clone))
        self.home = self.base/'home'

    def git(self, cwd, *args):
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.org', *args], cwd=cwd, check=True, capture_output=True)

    def update(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('PIP_')}
        env.update({'AI_KIT_NO_LIVE': '1', **wheelhouse.pip_env()})
        command = [str(self.clone/'Installer.cmd')] if WINDOWS else ['sh', str(self.clone/'scripts'/'bootstrap.sh')]
        proc = subprocess.run(command+['update', '--home', str(self.home)], capture_output=True, text=True, encoding='utf-8',
                              errors='replace', env=env, stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout+proc.stderr

    def setup_kit(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('PIP_')}
        env.update({'AI_KIT_NO_LIVE': '1', **wheelhouse.pip_env()})
        command = [str(self.clone/'Installer.cmd')] if WINDOWS else ['sh', str(self.clone/'scripts'/'bootstrap.sh')]
        proc = subprocess.run(command+['setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini', '--home', str(self.home)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)

    def test_update_fetches_reinstalls_and_applies(self):
        self.setup_kit()
        (self.origin/'VERSION').write_text('9.9.9\n', encoding='utf-8')
        pyproject = (self.origin/'pyproject.toml').read_text(encoding='utf-8')
        (self.origin/'pyproject.toml').write_text(pyproject.replace('version = "', 'version = "9.9.9" #', 1), encoding='utf-8')
        self.git(self.origin, 'commit', '--quiet', '-am', 'v2')
        code, out = self.update()
        self.assertEqual(code, 0, out)
        self.assertIn('Step 1/3', out)
        self.assertIn('Fetched:', out)
        self.assertIn('Kit package 9.9.9 installed', out)
        self.assertEqual(json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))['version'], '9.9.9')

    def test_local_changes_are_never_overwritten_and_the_update_is_reported_incomplete(self):
        self.setup_kit()
        (self.origin/'README.md').write_text('upstream change\n', encoding='utf-8')
        self.git(self.origin, 'commit', '--quiet', '-am', 'v2')
        mine = self.clone/'README.md'
        mine.write_text('my local change\n', encoding='utf-8')
        code, out = self.update()
        self.assertEqual(code, 1, out)
        self.assertIn('local changes', out)
        self.assertIn('Update incomplete', out)
        self.assertEqual(mine.read_text(encoding='utf-8'), 'my local change\n')

    def test_fetch_failure_is_not_a_success(self):
        self.setup_kit()
        shutil.rmtree(self.origin)  # the remote is gone: like no network
        code, out = self.update()
        self.assertEqual(code, 1, out)
        self.assertIn('Fetch failed', out)
        self.assertIn('Update incomplete', out)


class LauncherUnitTests(unittest.TestCase):
    def test_missing_venv_support_explains_the_it_prerequisite(self):
        with mock.patch.dict(sys.modules, {'ensurepip': None}):
            with self.assertRaises(launcher.LauncherError) as caught:
                launcher.check_python()
        self.assertIn('venv or pip', str(caught.exception))
        self.assertIn('What to ask IT support', str(caught.exception))

    def test_action_and_home_are_read_without_parsing_the_rest(self):
        argv = ['--home', 'update', 'setup', '--profile', 'general']
        self.assertEqual(launcher.action_of(argv), 'setup')
        self.assertEqual(launcher.option(argv, '--home'), 'update')
        self.assertEqual(launcher.option(['--home=x'], '--home'), 'x')
        self.assertIsNone(launcher.action_of(['--dry-run']))

    def test_messages_before_the_interface_are_plain_text(self):
        text = (ROOT/'scripts/launcher.py').read_text(encoding='utf-8')
        self.assertNotIn('import rich', text)
        self.assertNotIn('import questionary', text)


if __name__ == '__main__':
    unittest.main()
