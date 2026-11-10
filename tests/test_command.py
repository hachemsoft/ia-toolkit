"""The `ai-kit` command: a script in ~/.ai-kit/bin that runs the launcher of the kit folder, and that folder on the
person's own PATH (user registry on Windows, a marked block in the shell startup file elsewhere). Chosen at init, kept
by a re-apply, removed by uninstall; nothing without a kit folder."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli, command
from installer.core import read_json


class FakeRegistry:
    """Just enough of winreg for the user PATH: one value, its kind kept."""
    HKEY_CURRENT_USER, KEY_READ, KEY_SET_VALUE, REG_SZ, REG_EXPAND_SZ = 'HKCU', 1, 2, 1, 2

    def __init__(self, value=None, kind=2):
        self.value, self.kind = value, kind

    @contextlib.contextmanager
    def OpenKey(self, root, name, reserved, access):
        yield self

    def QueryValueEx(self, key, name):
        if self.value is None:
            raise FileNotFoundError(name)
        return self.value, self.kind

    def SetValueEx(self, key, name, reserved, kind, value):
        self.value, self.kind = value, kind


class RegistryTests(unittest.TestCase):
    def test_entry_added_once_and_kind_kept_expandable(self):
        reg = FakeRegistry(r'C:\Tools;%USERPROFILE%\bin', kind=FakeRegistry.REG_EXPAND_SZ)
        self.assertTrue(command.registry_entry(True, reg))
        self.assertEqual(reg.value, r'C:\Tools;%USERPROFILE%\bin;%USERPROFILE%\.ai-kit\bin')
        self.assertEqual(reg.kind, FakeRegistry.REG_EXPAND_SZ)
        self.assertFalse(command.registry_entry(True, reg))  # already there, whatever the case
        reg.value = reg.value.upper()
        self.assertFalse(command.registry_entry(True, reg))

    def test_plain_value_becomes_expandable_and_removal_keeps_the_rest(self):
        reg = FakeRegistry(r'C:\Tools', kind=FakeRegistry.REG_SZ)
        command.registry_entry(True, reg)
        self.assertEqual(reg.kind, FakeRegistry.REG_EXPAND_SZ)
        self.assertTrue(command.registry_entry(False, reg))
        self.assertEqual(reg.value, r'C:\Tools')
        self.assertFalse(command.registry_entry(False, reg))
        empty = FakeRegistry()
        command.registry_entry(True, empty)
        self.assertEqual(empty.value, r'%USERPROFILE%\.ai-kit\bin')


class StartupFileTests(unittest.TestCase):
    def test_file_from_the_login_shell(self):
        self.assertEqual(command.startup_file('/bin/zsh'), '.zshrc')
        with mock.patch.object(command.sys, 'platform', 'darwin'):
            self.assertEqual(command.startup_file('/bin/bash'), '.bash_profile')
        with mock.patch.object(command.sys, 'platform', 'linux'):
            self.assertEqual(command.startup_file('/usr/bin/bash'), '.bashrc')
        self.assertEqual(command.startup_file('/bin/sh'), '.profile')
        self.assertIsNone(command.startup_file('/usr/bin/fish'))
        self.assertIsNone(command.startup_file(''))

    def test_block_added_once_and_removed_cleanly(self):
        line = command.path_line(Path('/home/me'))
        text = 'export EDITOR=vim\n'
        once = command.with_block(text, line)
        self.assertIn(line, once)
        self.assertTrue(once.startswith('export EDITOR=vim\n'))
        self.assertEqual(command.with_block(once, line), once)
        self.assertEqual(command.without_block(once), text)
        self.assertEqual(command.without_block(text), text)
        # A block without a trailing newline, or at the top of the file, goes cleanly too.
        self.assertEqual(command.without_block(command.with_block('', line)), '')


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)/'home'
        self.home.mkdir()
        self.kit = Path(temp.name)/'kit folder'
        self.kit.mkdir()
        (self.kit/'VERSION').write_text(cli.kit_version()+'\n', encoding='utf-8')
        for patcher in (mock.patch('shutil.which', return_value=None), mock.patch.dict(os.environ, {'SHELL': '/bin/zsh', 'AI_KIT_SOURCE_DIR': str(self.kit)}),
                        mock.patch.object(command, 'registry_entry', return_value=False)):
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.home/'.zshrc').write_text('export EDITOR=vim\n', encoding='utf-8')

    def apply(self, *args, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.apply(self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini', *args, **kwargs)
        return out.getvalue()

    def shim(self):
        return self.home/'.ai-kit/bin'/command.SHIM_NAME


class InstallTests(Base):
    def test_shim_and_startup_block_installed_by_default_and_recorded(self):
        out = self.apply()
        self.assertTrue(self.shim().is_file())
        text = self.shim().read_text(encoding='utf-8')
        self.assertIn(str(self.kit), text)
        self.assertIn('Installer.cmd' if os.name == 'nt' else 'scripts/bootstrap.sh', text)
        if os.name != 'nt':
            self.assertTrue(os.access(self.shim(), os.X_OK))
            startup = (self.home/'.zshrc').read_text(encoding='utf-8')
            self.assertTrue(startup.startswith('export EDITOR=vim\n'))
            self.assertEqual(startup.count(command.BLOCK_START), 1)
            self.assertIn(str(self.home/'.ai-kit/bin'), startup)
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertIn('.ai-kit/bin/'+command.SHIM_NAME, state['files'])
        self.assertEqual(state['command']['folder'], str(self.kit))
        self.assertTrue(state['command']['chosen'])
        self.assertIn('open a new terminal', out)
        # A second run changes nothing and says nothing new.
        again = self.apply()
        self.assertNotIn('open a new terminal', again)
        if os.name != 'nt':
            self.assertEqual((self.home/'.zshrc').read_text(encoding='utf-8').count(command.BLOCK_START), 1)

    def test_choice_no_removes_everything_and_uninstall_too(self):
        self.apply()
        self.apply(command=False)
        self.assertFalse(self.shim().exists())
        self.assertEqual((self.home/'.zshrc').read_text(encoding='utf-8'), 'export EDITOR=vim\n')
        self.assertFalse(read_json(self.home/'.ai-kit/state.json')['command']['chosen'])
        self.apply(command=True)
        self.assertTrue(self.shim().is_file())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.uninstall(self.home), 0)
        self.assertFalse(self.shim().exists())
        self.assertEqual((self.home/'.zshrc').read_text(encoding='utf-8'), 'export EDITOR=vim\n')

    def test_without_a_kit_folder_nothing_is_written_and_an_existing_shim_is_kept(self):
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''}):
            out = self.apply()
        self.assertFalse(self.shim().exists())
        self.assertEqual((self.home/'.zshrc').read_text(encoding='utf-8'), 'export EDITOR=vim\n')
        self.assertIn('run the installer from the kit folder', out)
        self.apply()
        shim = self.shim().read_bytes()
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''}):
            self.apply()
        self.assertEqual(self.shim().read_bytes(), shim)
        self.assertEqual(read_json(self.home/'.ai-kit/state.json')['command']['folder'], str(self.kit))

    def test_moved_kit_folder_rewrites_the_shim_and_doctor_reports_a_missing_one(self):
        self.apply()
        moved = self.kit.parent/'kit moved'
        self.kit.rename(moved)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': ''}), contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[Check] The `ai-kit` command points to a kit folder that moved or was deleted', out.getvalue())
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': str(moved)}):
            self.apply()
        self.assertIn(str(moved), self.shim().read_text(encoding='utf-8'))
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': str(moved)}), contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[OK] The `ai-kit` command runs the launcher of '+str(moved), out.getvalue())

    def test_doctor_does_not_take_the_kit_command_for_another_copy(self):
        self.apply()
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'PATH': str(self.shim().parent)}), contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertNotIn('another copy of the kit', out.getvalue())
        self.assertIn('[OK] The `ai-kit` command runs the launcher of '+str(self.kit), out.getvalue())
        self.assertNotIn('is not on the PATH of this terminal', out.getvalue())

    def test_unknown_shell_gets_the_line_to_add(self):
        with mock.patch.dict(os.environ, {'SHELL': '/usr/bin/fish'}):
            out = self.apply()
        if os.name != 'nt':
            self.assertIn('add this line to your shell startup file', out)
            self.assertEqual((self.home/'.zshrc').read_text(encoding='utf-8'), 'export EDITOR=vim\n')
        self.assertTrue(self.shim().is_file())


class ChoiceTests(Base):
    """AI Kit 3: no guided installer; the choice is init's option, yes the first time, and a re-apply keeps it."""
    def test_command_line_option(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(cli, 'interactive', return_value=False):
            self.assertEqual(cli.main(['init', '--user', 'a@example.org', '--target', 'gemini', '--home', str(self.home), '--command-on-path', 'no']), 0)
            self.assertFalse(self.shim().exists())
            self.assertFalse(read_json(self.home/'.ai-kit/state.json')['command']['chosen'])
            self.assertEqual(cli.main(['sync', '--offline', '--home', str(self.home)]), 0)  # the recorded answer stands
            self.assertFalse(self.shim().exists())
            self.assertEqual(cli.main(['init', '--home', str(self.home), '--command-on-path', 'yes']), 0)
            self.assertTrue(self.shim().is_file())
            self.assertEqual(cli.main(['init', '--home', str(self.home)]), 0)
            self.assertTrue(self.shim().is_file())


if __name__ == '__main__':
    unittest.main()
