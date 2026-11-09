"""V2 slice 8: the kit's content exported as a Core repository in its V2 layout installs the same files; the Team example and
the exported Core pass ai-kit validate; a Team holding commands does not; sync --from-bundle installs the Core offline,
recorded under the configured URL. No network: the configured URL is never reached."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, sync
from installer.core import ROOT, content_from
from installer.toml_files import dump_toml, read_toml
from installer.validate import problems

HAS_GIT = shutil.which('git') is not None
VERSION = (ROOT/'VERSION').read_text(encoding='utf-8').strip()


def files_of(home):
    # The home folder is written into some files (paths): compared without it.
    return {p.relative_to(home).as_posix(): p.read_bytes().replace(str(home).encode(), b'~').replace(home.as_uri().encode(), b'~').replace(home.as_posix().encode(), b'~') for p in sorted(home.rglob('*'))
            if p.is_file() and not p.relative_to(home).as_posix().startswith(('.ai-kit/state.json', '.ai-kit/backups/'))}


@unittest.skipUnless(HAS_GIT, 'git not installed')
class CoreExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name).resolve()
        cls.core = cls.base/'core'
        subprocess.run([sys.executable, str(ROOT/'scripts/export_core.py'), str(cls.core), '--git'], check=True, capture_output=True,
                       env={**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull})

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def install(self, home, content=None):
        with content_from(content) if content else contextlib.nullcontext(), contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', home, False, None, 'claude')
        return files_of(home)

    def test_the_exported_core_is_flat_valid_and_installs_the_same_files(self):
        self.assertTrue((self.core/'skills/tdd/SKILL.md').is_file())
        self.assertTrue((self.core/'agents/code-reviewer.md').is_file())
        self.assertEqual(read_toml(self.core/'aikit.toml')['kind'], 'core')
        self.assertEqual(problems(self.core, VERSION), [])
        self.assertEqual(self.install(self.base/'h1', self.core), self.install(self.base/'h2'))

    def test_the_team_example_passes_and_a_team_with_commands_does_not(self):
        example = ROOT/'examples/team-repo'
        self.assertEqual(problems(example, VERSION), [])
        team = self.base/'team-with-commands'
        shutil.copytree(example, team)
        (team/'commands').mkdir()
        (team/'commands/build.md').write_text('x', encoding='utf-8')
        self.assertTrue(any('commands: a Team repository may not hold it' in line for line in problems(team, VERSION)))

    def test_sync_from_a_bundle_installs_the_core_offline(self):
        bundle = self.base/'core.bundle'
        subprocess.run(['git', 'bundle', 'create', '-q', str(bundle), '--all'], cwd=self.core, check=True, capture_output=True,
                       env={**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull})
        home = self.base/'offline'
        (home/'.ai-kit').mkdir(parents=True)
        url = 'https://gitlab.example.org/ai-toolkit/ai-core.git'  # never reached
        (home/'.ai-kit/aikit.toml').write_text(dump_toml({'schema': 1, 'core': {'repo': url}}), encoding='utf-8')
        managed = self.base/'no-managed.toml'
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', home, False, None, 'claude', managed_file=managed)
            with sync.activation(home, 'sync', False, lambda q: True, managed_file=managed, bundle=bundle) as act:
                cli.apply('general', home, False, None, 'claude', act.team, extra_writes=act.writes, managed_file=managed)
        core = read_toml(home/'.ai-kit/lock.toml')['sources']['core']
        self.assertEqual((core['url'], core['tag']), (url, 'v'+VERSION))
        self.assertEqual(len(core['commit']), 40)
        with mock.patch('installer.sources.remote_tags', side_effect=AssertionError('no network')), contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', home, False, None, 'claude', managed_file=managed)  # update: from the cache
        self.assertTrue((home/'.claude/skills/ai-kit-tdd/SKILL.md').is_file())


if __name__ == '__main__':
    unittest.main()
