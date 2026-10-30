"""Enterprise installation: release ZIP, thin launchers (Installer.cmd, bootstrap.sh), Python absent or unusable,
paths with spaces and accents, a kit folder that can be deleted, a new version from another folder, 30_USER.md guidance,
no system change, no secret kept, a network failure explained.

With AI_KIT_RELEASE_ZIP=<path to the release ZIP>, the launcher tests run on the extracted ZIP (CI release job);
otherwise on a copy of this folder.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from installer import cli
from installer.core import ROOT, SECRET, read_json, redact
from installer.adapters.gemini import diagnose_live

RELEASE_ZIP = os.environ.get('AI_KIT_RELEASE_ZIP')
WINDOWS = os.name == 'nt'


def kit_copy(dest):
    """The kit as a person gets it: the extracted release ZIP, or a copy of this folder without maintainer files."""
    if RELEASE_ZIP:
        with zipfile.ZipFile(RELEASE_ZIP) as archive:
            archive.extractall(dest)
    else:
        shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns('.git', '__pycache__', 'dist', 'build', '.debug', '.codegraph',
                                                                  '.claude', 'tests', 'evals', '.ai-kit'))
    return dest


def launcher(kit):
    # sh by its full path: some tests run the launcher with a PATH reduced to a few tools.
    return [str(kit/'Installer.cmd')] if WINDOWS else [shutil.which('sh'), str(kit/'scripts'/'bootstrap.sh')]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Spaces and accents in the kit folder and in the home folder, as in "Documents/Kit IA été".
        self.base = Path(self.temp.name)/'Mes documents é'
        self.kit = kit_copy(self.base/'Kit IA été'/'ai-kit 1')
        self.home = self.base/'Home à'
        self.env = {**os.environ, 'AI_KIT_NO_LIVE': '1'}

    def run_launcher(self, kit, *args, env=None):
        return subprocess.run(launcher(kit) + list(args), cwd=self.base, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', env=env or self.env, stdin=subprocess.DEVNULL)

    def setup_kit(self, kit, *extra):
        proc = self.run_launcher(kit, 'setup', '--home', str(self.home), '--no-live', *extra)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def test_setup_then_the_extracted_folder_can_be_deleted(self):
        self.setup_kit(self.kit, '--profile', 'general', '--target', 'all', '--user', 'first.last@example.com')
        self.assertTrue((self.home/'.ai-kit/state.json').is_file())
        shutil.rmtree(self.base/'Kit IA été')
        # Nothing installed points back to the extracted folder: hooks, scripts and schema live in ~/.ai-kit.
        markers = {str(self.kit), self.kit.as_uri(), str(self.kit).replace('\\', '/'), str(self.kit).replace('\\', '\\\\')}
        for path in self.home.rglob('*'):
            if path.is_file() and '/backups/' not in path.as_posix():
                text = path.read_text(encoding='utf-8', errors='replace')
                self.assertFalse([m for m in markers if m in text], path)
        self.assertTrue((self.home/'.ai-kit/schemas/overrides.schema.json').is_file())

    def test_new_version_from_another_folder_keeps_personal_settings(self):
        self.setup_kit(self.kit, '--profile', 'general', '--target', 'all', '--user', 'first.last@example.com')
        user_file = self.home/'.gemini/30_USER.md'
        user_file.write_text(user_file.read_text(encoding='utf-8') + '\nMon rôle : ingénieure données, projet Été.\n', encoding='utf-8')
        personal = self.home/'.ai-kit/overrides.json'
        # As written by 0.26: the schema link pointed to the extracted folder.
        old_link = (self.kit/'schemas'/'overrides.schema.json').as_uri()
        personal.write_text('{\n  "$schema": "' + old_link + '",\n  "extra_skills": ["teach"],\n  "_mine": "kept"\n}\n', encoding='utf-8')
        user_before = user_file.read_bytes()
        # New version: another ZIP extracted elsewhere, the old folder deleted, setup again without any option.
        new_kit = shutil.copytree(self.kit, self.base/'ai-kit 2')
        shutil.rmtree(self.base/'Kit IA été')
        self.setup_kit(new_kit)
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(state['profile'], 'general')
        self.assertEqual(state['user']['email'], 'first.last@example.com')
        self.assertEqual(user_file.read_bytes(), user_before)
        self.assertIn('Mon rôle : ingénieure données', (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
        self.assertTrue((self.home/'.gemini/skills/teach/SKILL.md').is_file())
        new_link = (self.home.resolve()/'.ai-kit'/'schemas'/'overrides.schema.json').as_uri()
        self.assertEqual(personal.read_text(encoding='utf-8'),
                         '{\n  "$schema": "' + new_link + '",\n  "extra_skills": ["teach"],\n  "_mine": "kept"\n}\n')

    def python_free_path(self):
        """A PATH with the system tools the launcher needs, without any Python."""
        if WINDOWS:
            return os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
        tools = self.base/'tools'
        tools.mkdir()
        for name in ('dirname', 'uname'):
            (tools/name).symlink_to(shutil.which(name))
        return str(tools)

    def test_python_absent_says_what_to_ask_it_support(self):
        proc = self.run_launcher(self.kit, 'setup', '--home', str(self.home), env={**self.env, 'PATH': self.python_free_path()})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        output = proc.stdout + proc.stderr
        self.assertIn('Python 3.9 or newer was not found', output)
        self.assertIn('What to ask IT support', output)
        self.assertFalse((self.home/'.ai-kit').exists())

    @unittest.skipIf(WINDOWS, 'Fake interpreters as shell scripts: Unix only')
    def test_old_or_blocked_python_is_explained(self):
        path = self.python_free_path()
        for code, expected in ((3, 'older than 3.9'), (1, 'could not be started')):
            fake = Path(path)/'python3'
            fake.write_text('#!/bin/sh\nexit ' + str(code) + '\n', encoding='utf-8')
            fake.chmod(0o755)
            proc = self.run_launcher(self.kit, 'setup', env={**self.env, 'PATH': path})
            self.assertEqual(proc.returncode, 2)
            self.assertIn(expected, proc.stderr)


class ReleaseFilesTests(unittest.TestCase):
    def test_installer_cmd_is_ascii_with_crlf_and_needs_no_powershell(self):
        data = (ROOT/'Installer.cmd').read_bytes()
        data.decode('ascii')
        self.assertEqual(data.count(b'\n'), data.count(b'\r\n'), 'cmd.exe misreads labels with LF line endings')
        commands = [line for line in data.decode('ascii').splitlines() if not line.lower().startswith('rem ')]
        self.assertFalse([line for line in commands if 'powershell' in line.lower()])

    @unittest.skipUnless(RELEASE_ZIP, 'Release ZIP built by scripts/package.sh (CI release job)')
    def test_release_zip_content(self):
        with zipfile.ZipFile(RELEASE_ZIP) as archive:
            names = archive.namelist()
            self.assertIn('Installer.cmd', names)  # at the root: no top folder, extraction gives a single folder
            self.assertIn('scripts/bootstrap.sh', names)
            self.assertFalse([n for n in names if n.startswith(('tests/', 'evals/', '.github/', '.git/', 'build/', 'dist/'))])
            self.assertEqual(archive.read('Installer.cmd').count(b'\n'), archive.read('Installer.cmd').count(b'\r\n'))

    def test_no_system_change_in_installer_and_launchers(self):
        # Registry, system or user PATH, execution policy, Gatekeeper and quarantine, elevation, shell startup files.
        forbidden = re.compile(r'winreg|\bsetx\b|reg add|ExecutionPolicy|\bxattr\b|\bspctl\b|\bsudo\b|\brunas\b|HKEY_|Set-ItemProperty'
                               r'|\.zshrc|\.bashrc|\.bash_profile|\.zprofile|/etc/|launchctl|defaults write', re.I)
        sources = list((ROOT/'installer').rglob('*.py')) + [ROOT/'Installer.cmd', ROOT/'scripts/bootstrap.sh', ROOT/'runtime/friction.py']
        found = []
        for source in sources:
            for number, line in enumerate(source.read_text(encoding='utf-8').splitlines(), 1):
                code = line.split('#', 1)[0] if source.suffix in ('.py', '.sh') else ('' if line.lower().startswith('rem ') else line)
                if forbidden.search(code):
                    found.append(source.name + ':' + str(number))
        self.assertEqual(found, [])

    def test_launchers_download_nothing(self):
        for source in (ROOT/'Installer.cmd', ROOT/'scripts/bootstrap.sh'):
            text = source.read_text(encoding='utf-8').lower()
            for word in ('curl ', 'wget ', 'bitsadmin', 'invoke-webrequest', 'pip install', 'winget', 'brew '):
                self.assertNotIn(word, text, source.name)


class Console(io.StringIO):
    def isatty(self):
        return True


class PersonalContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name)/'30_USER.md'
        self.file.write_text('# My context\n', encoding='utf-8')

    def step(self, answers, saved):
        """Runs the step with the editor replaced by a write of `saved` (what the person saves)."""
        reapply = mock.Mock()
        def editor(*args, **kwargs):
            if isinstance(saved, bytes):
                self.file.write_bytes(saved)
            return mock.Mock()
        out = io.StringIO()
        with mock.patch.object(cli, 'text_editor', return_value=('Editor', ['editor', str(self.file)])), \
             mock.patch.object(cli.subprocess, 'Popen', side_effect=editor) as popen, \
             mock.patch('builtins.input', side_effect=answers), contextlib.redirect_stdout(out):
            cli.personal_context_step(self.file, reapply)
        return out.getvalue(), reapply, popen

    def test_edit_then_apply_then_new_session(self):
        out, reapply, popen = self.step(['y', ''], '# My context\nData engineer, project Été.\n'.encode('utf-8'))
        popen.assert_called_once()
        reapply.assert_called_once()
        self.assertIn('Start a new session of your CLI', out)

    def test_declined_leaves_everything_as_is(self):
        out, reapply, popen = self.step([''], None)
        popen.assert_not_called()
        reapply.assert_not_called()
        self.assertEqual(self.file.read_text(encoding='utf-8'), '# My context\n')
        self.assertIn('run update', out)

    def test_rich_text_is_not_applied(self):
        out, reapply, _ = self.step(['y', ''], b'{\\rtf1\\ansi My context}')
        reapply.assert_not_called()
        self.assertIn('Make Plain Text', out)

    def test_editor_renamed_the_file(self):
        self.file.rename(self.file.with_name('30_USER.md.txt'))
        self.assertIn('30_USER.md.txt', cli.plain_text_problem(self.file))

    def test_setup_without_a_terminal_never_asks(self):
        # Windows: stdin redirected from NUL reports isatty(); the optional step must not turn a complete install into a failure.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cli.sys.stdin, 'isatty', return_value=True), \
             mock.patch.object(cli, 'text_editor', return_value=('Editor', ['editor'])), \
             mock.patch('builtins.input', side_effect=EOFError) as asked, contextlib.redirect_stdout(Console()):
            code = cli.main(['setup', '--profile', 'general', '--home', tmp, '--no-live', '--user', 'a@example.org', '--target', 'gemini'])
        self.assertEqual(code, 0)
        asked.assert_called_once()  # the question was asked, the end of input skipped it

    def test_output_not_at_a_terminal_means_no_question(self):
        # The Windows case: stdin from NUL says "terminal", stdout is captured; no identity, profile or editor question.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cli.sys.stdin, 'isatty', return_value=True), \
             mock.patch('builtins.input', side_effect=EOFError) as asked, contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(['setup', '--profile', 'general', '--home', tmp, '--no-live', '--target', 'gemini'])
        self.assertEqual(code, 0)
        asked.assert_not_called()

    def test_native_editor_or_none(self):
        found = cli.text_editor(self.file)
        if WINDOWS:
            self.assertEqual(found[1][0], 'notepad.exe')
        elif os.uname().sysname == 'Darwin':
            self.assertEqual(found[1][:2], ['open', '-t'])  # plain-text editor: no rich text


class SecretsAndNetworkTests(unittest.TestCase):
    SAMPLES = ['key AIzaSyA1234567890abcdefghijklmnopqrstuv', 'token=abcdef123456', 'Authorization: Bearer abcdefghijklmnop1234',
               'ghp_' + 'a' * 36, 'password: hunter22', 'sk-proj-' + 'b' * 30]

    def test_secrets_redacted_in_frictions(self):
        for sample in self.SAMPLES:
            self.assertNotRegex(redact(sample), SECRET, sample)
        self.assertEqual(redact('"TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"'), '"TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"')
        self.assertEqual(redact('the token expired'), 'the token expired')

    def test_friction_script_uses_the_same_list(self):
        source = (ROOT/'runtime/friction.py').read_text(encoding='utf-8')
        core = (ROOT/'installer/core.py').read_text(encoding='utf-8')
        pattern = re.compile(r"^SECRET = re\.compile\(.*?\)\n", re.S | re.M)
        self.assertEqual(pattern.search(source).group(0), pattern.search(core).group(0))

    def test_friction_text_is_redacted_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, 'HOME': tmp, 'USERPROFILE': tmp}
            proc = subprocess.run([shutil.which('python3') or shutil.which('python') or 'python', str(ROOT/'runtime/friction.py'),
                                   '--category', 'auth', '--text', 'login failed with ghp_' + 'c' * 36],
                                  capture_output=True, text=True, encoding='utf-8', env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            line = json.loads((Path(tmp)/'.ai-kit/frictions.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(line['text'], 'login failed with [redacted]')

    def test_doctor_flags_a_secret_in_personal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                cli.apply('general', home, False, {'email': 'a@example.org', 'source': 'test'}, 'gemini')
            (home/'.gemini/30_USER.md').write_text('My key: AIzaSyA1234567890abcdefghijklmnopqrstuv\n', encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.doctor(home)
            self.assertIn('30_USER.md seems to contain a secret', out.getvalue())
            self.assertNotIn('AIzaSy', out.getvalue())

    def test_network_proxy_and_certificate_failures_explained(self):
        cases = {'Error: getaddrinfo ENOTFOUND generativelanguage.googleapis.com': 'cannot reach the Google APIs',
                 'TypeError: fetch failed': 'cannot reach the Google APIs',
                 'Error: self-signed certificate in certificate chain': 'company root certificate',
                 'status: 407 Proxy Authentication Required': 'proxy asks for authentication'}
        for output, expected in cases.items():
            diagnostic, remedy = diagnose_live(1, output, False, {})
            self.assertIn(expected, diagnostic)
            self.assertNotRegex(remedy, r'(?i)NODE_TLS_REJECT_UNAUTHORIZED|--insecure|no_proxy|strict-ssl')
        # Offline, the call times out after network errors: the network is named, not the model.
        self.assertIn('cannot reach', diagnose_live(None, 'ETIMEDOUT', True, {})[0])


if __name__ == '__main__':
    unittest.main()
