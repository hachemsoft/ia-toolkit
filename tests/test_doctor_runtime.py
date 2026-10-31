"""Which copy of the kit runs: --version, another `ai-kit` command first on the PATH (an old pipx or pip install), the
private environment's state, the kit folder's version, a newer version published in a clone, and menu wording."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.wizard import menu_wording

POSIX = os.name != 'nt'


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base/'home'
        self.home.mkdir()
        with contextlib.redirect_stdout(io.StringIO()), mock.patch('shutil.which', return_value=None):
            cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'codex')

    def doctor(self, **env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
            cli.doctor_checks(self.home)
        return out.getvalue()


class VersionTests(unittest.TestCase):
    def test_version_names_the_running_copy(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(['--version']), 0)
        self.assertIn('AI Kit '+cli.kit_version(), out.getvalue())
        self.assertIn(str(cli._PACKAGE_DIR), out.getvalue())
        self.assertIn(sys.executable, out.getvalue())


@unittest.skipUnless(POSIX, 'fake commands are shell scripts')
class KitCommandOnPathTests(Base):
    def command(self, folder, version, pipx_style=False):
        """A fake `ai-kit` whose Python answers `version` to the metadata question; the command itself is never run."""
        folder = self.base/folder
        folder.mkdir()
        interpreter = folder/'python'
        interpreter.write_text('#!/bin/sh\necho '+version+'\n', encoding='utf-8')
        interpreter.chmod(0o755)
        script = folder/'ai-kit'
        head = ("#!/bin/sh\n'''exec' \""+str(interpreter)+"\" \"$0\" \"$@\"\n' '''\n") if pipx_style else '#!'+str(interpreter)+'\n'
        script.write_text(head+'raise SystemExit("the command must not be run")\n', encoding='utf-8')
        script.chmod(0o755)
        return folder

    def test_an_old_copy_first_on_the_path_is_flagged_with_the_way_out(self):
        old = self.command('pipx bin', '0.25.1', pipx_style=True)
        new = self.command('conda bin', cli.kit_version())
        out = self.doctor(PATH=str(old)+os.pathsep+str(new))
        self.assertIn('[Check] The `ai-kit` command on your PATH is another copy of the kit', out)
        self.assertIn('version 0.25.1', out)
        self.assertIn('pipx uninstall ai-kit', out)
        self.assertIn('[Info] Another `ai-kit` command, not used', out)

    def test_the_right_copy_first_says_nothing_alarming(self):
        new = self.command('conda bin', cli.kit_version())
        out = self.doctor(PATH=str(new))
        self.assertNotIn('another copy of the kit', out)

    def test_no_command_on_the_path_is_fine(self):
        out = self.doctor(PATH=str(self.base))
        self.assertNotIn('ai-kit` command', out)


class RuntimeStateTests(Base):
    def record(self, **data):
        path = self.home/'.ai-kit/runtime/install.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_states_of_the_private_environment(self):
        self.assertIn('[Info] No private kit environment', self.doctor())
        self.record(status='ready', version='0.34.0')
        self.assertIn('[OK] Kit runtime ready: version 0.34.0', self.doctor())
        self.record(status='installing')
        self.assertIn('[Check] Kit runtime interrupted', self.doctor())
        self.record(status='failed')
        self.assertIn('[Check] Kit runtime failed to install', self.doctor())

    def test_kit_folder_newer_than_the_installed_package(self):
        folder = self.base/'kit folder'
        folder.mkdir()
        (folder/'VERSION').write_text('9.9.9\n', encoding='utf-8')
        out = self.doctor(AI_KIT_SOURCE_DIR=str(folder))
        self.assertIn('[Check] The kit folder (9.9.9) and the installed kit package', out)
        (folder/'VERSION').write_text(cli.kit_version()+'\n', encoding='utf-8')
        self.assertIn('[OK] The kit folder', self.doctor(AI_KIT_SOURCE_DIR=str(folder)))


@unittest.skipUnless(shutil.which('git'), 'git required')
class ReleaseCheckTests(unittest.TestCase):
    def test_newer_tag_found_in_the_clone_the_launcher_came_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp)
            (clone/'VERSION').write_text('0.34.0\n', encoding='utf-8')
            git = lambda *a: subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.org', *a], cwd=clone, check=True, capture_output=True)
            git('init', '--quiet')
            git('add', '-A')
            git('commit', '--quiet', '-m', 'v')
            git('tag', 'v9.9.9')
            out = io.StringIO()
            with mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': str(clone)}), contextlib.redirect_stdout(out):
                cli.release_check()  # no remote: the fetch fails quietly, the local tags are read
        self.assertIn('AI Kit 9.9.9 is published (this folder: 0.34.0)', out.getvalue())


class MenuWordingTests(unittest.TestCase):
    def test_command_line_actions_become_menu_choices(self):
        lines = menu_wording(['Next step: fix the points above, then run doctor again.', 'Install it, then run update.',
                              'apply the fix shown above, then run doctor --live.'])
        self.assertEqual(lines, ['Next step: fix the points above, then choose "Check the installation" again in this menu.',
                                 'Install it, then choose "Update" in this menu.',
                                 'apply the fix shown above, then choose the Advanced check in this menu.'])


if __name__ == '__main__':
    unittest.main()
