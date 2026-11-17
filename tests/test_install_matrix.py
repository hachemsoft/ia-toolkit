"""Install matrix (docs/sdlc/2026-11-15-install-test-matrix): a blank or an installed home, without or with a Team, every CLI;
and the content-shape rule that keeps min_engine honest (an engine older than the content's shape refuses it instead of
failing on a missing layer: "Practice not found or ambiguous: company"). Local bare repositories over file://, no network,
no model call, no MCP server started.

Covered elsewhere, not repeated: a Team turned off then back from the cache (test_team_use), the pre-4.16 layers removed
with a backup (test_core_team_layers), a Team's local MCP server refused until approved (test_team_use)."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

from installer import cli, sources, sync
from installer.core import ROOT, content_root
from installer.settings import context_folder, core_selection
from installer.toml_files import read_toml
from test_git_sources import HAS_GIT, run_git

SHAPE_FILE = ROOT/'tests'/'content-shape.json'
TIME_ARGS = ['mcp-server-time==2026.10.28', '--local-timezone=Europe/Paris']


KIT_FILE_FOLDERS = ('bin', 'hooks', 'me', 'news', 'schemas')  # what the engine writes under ~/.ai-kit for the content to use


def content_shape():
    """What the content relies on the engine for: the context layer files, the layers the Core selection asks for, and the
    files the engine installs under ~/.ai-kit (4.18.0: /me reads ~/.ai-kit/me/questions.md, which only a 4.18 engine
    writes). Measured by a real install into a temporary home, never recomputed apart from the installer."""
    with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
        home = Path(temp)
        cli.apply(home, False, {'email': 'test@example.org'}, 'claude', managed_file=home/'managed.toml')
        kit = home/'.ai-kit'
        files = sorted(p.relative_to(kit).as_posix() for folder in KIT_FILE_FOLDERS for p in (kit/folder).rglob('*')
                       if p.is_file() and '__pycache__' not in p.parts)
    return {'layers': sorted(p.name for p in context_folder(content_root()).glob('[0-9][0-9]-*.md')),
            'practices': core_selection()['practices'], 'kit_files': files}


def shape_problem(recorded, shape, min_engine, version):
    """None when the record matches; otherwise what to do. A new shape with the same min_engine is the 4.16 incident."""
    if recorded == {**shape, 'min_engine': min_engine}:
        return None
    if shape != {k: recorded.get(k) for k in shape} and min_engine == recorded.get('min_engine'):
        return ('content shape changed ('+json.dumps(shape)+'): an older engine would accept this content and fail on it. Raise '
                'min_engine in aikit.toml to '+version+', then update tests/content-shape.json.')
    return 'tests/content-shape.json is out of date: write '+json.dumps({**shape, 'min_engine': min_engine})+'.'


class ContentShapeTests(unittest.TestCase):
    def test_the_content_shape_and_min_engine_are_recorded_together(self):
        recorded = json.loads(SHAPE_FILE.read_text(encoding='utf-8'))
        min_engine = read_toml(ROOT/'aikit.toml')['min_engine']
        version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
        self.assertIsNone(shape_problem(recorded, content_shape(), min_engine, version))

    def test_a_new_shape_without_a_new_min_engine_is_refused(self):
        # 4.16.0: context/10-company.md and 20-team.md became 10-core.md, min_engine stayed 4.0.0.
        before = {'layers': ['10-company.md', '20-team.md'], 'practices': ['company', 'team'], 'min_engine': '4.0.0'}
        after = {'layers': ['10-core.md'], 'practices': ['core']}
        self.assertIn('Raise min_engine in aikit.toml to 4.16.0', shape_problem(before, after, '4.0.0', '4.16.0'))
        self.assertIn('out of date', shape_problem(before, after, '4.16.0', '4.16.0'))  # raised: only the record lags
        self.assertIsNone(shape_problem({**after, 'min_engine': '4.16.0'}, after, '4.16.0', '4.17.0'))

    def test_a_new_file_the_engine_installs_needs_a_new_min_engine(self):
        # 4.18.0: /me reads ~/.ai-kit/me/questions.md; a 4.17 engine would install the new /me without that file, silently.
        layers = {'layers': ['10-core.md'], 'practices': ['core']}
        before = {**layers, 'kit_files': ['bin/friction.py'], 'min_engine': '4.17.0'}
        after = {**layers, 'kit_files': ['bin/friction.py', 'me/questions.md']}
        self.assertIn('Raise min_engine in aikit.toml to 4.18.0', shape_problem(before, after, '4.17.0', '4.18.0'))


@unittest.skipUnless(HAS_GIT, 'git not installed')
class InstallMatrixTests(unittest.TestCase):
    """Every case installs for all the CLIs, so a layer or a server missing from one of them shows."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base/'home'
        for patcher in (mock.patch.object(sources, 'LOCAL_FOR_TESTS', True), mock.patch('installer.config.ownership_problem', return_value=None),
                        mock.patch.object(sources, 'git_level_helpers', return_value=[])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.managed = self.base/'managed.toml'
        # The Team: the repository's own example, renamed, with the time server (a pinned, read-only reference server).
        self.work, self.bare = self.base/'team-work', self.base/'team.git'
        shutil.copytree(ROOT/'examples/team-repo', self.work)
        manifest = self.work/'aikit.toml'
        manifest.write_text(manifest.read_text(encoding='utf-8').replace('name = "reporting"', 'name = "kit-test"'), encoding='utf-8')
        (self.work/'mcp').mkdir()
        (self.work/'mcp/servers.toml').write_text('[servers.time]\ncommand = "uvx"\nargs = '+json.dumps(TIME_ARGS)+'\n', encoding='utf-8')
        run_git('init', '-q', cwd=self.work)
        run_git('add', '-A', cwd=self.work)
        run_git('commit', '-q', '-m', 'v1.0.0', cwd=self.work)
        run_git('tag', '-a', 'v1.0.0', '-m', 'v1.0.0', cwd=self.work)
        run_git('clone', '-q', '--bare', str(self.work), str(self.bare), cwd=self.base)
        self.url = 'file://'+self.bare.as_posix()

    def apply(self, team=None, approve=False):
        with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch.object(cli, 'APPROVE', [lambda question: approve]):
            if team:
                with sync.activation(self.home, 'team-use', False, managed_file=self.managed, team_name=team, team_url=self.url) as act:
                    cli.apply(self.home, False, None, 'all', act.team, extra_writes=act.writes, managed_file=self.managed)
            else:
                cli.apply(self.home, False, {'email': 'test@example.org'}, 'all', managed_file=self.managed)
        return out.getvalue()

    def state(self):
        return json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))

    def files(self):
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob('*') if p.is_file() and 'backups' not in p.parts}

    def test_m1_blank_home_through_the_command_line(self):
        env = {**os.environ, 'AI_KIT_NO_LIVE': '1'}
        proc = subprocess.run([sys.executable, '-m', 'installer', 'init', '--home', str(self.home), '--target', 'all',
                               '--user', 'test@example.org', '--command-on-path', 'no'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)
        context = self.home/'.ai-kit/context'
        self.assertTrue((context/'10_CORE.md').is_file())
        self.assertEqual(sorted(p.name for p in context.glob('20_*.md')), [])
        self.assertEqual(self.state()['practices'], ['core'])
        self.assertIn('10_CORE.md', (self.home/'.claude/CLAUDE.md').read_text(encoding='utf-8'))
        core_text = (context/'10_CORE.md').read_text(encoding='utf-8').strip()[:200]
        self.assertIn(core_text, (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))

    def test_m2_a_team_adds_its_layer_to_every_cli(self):
        self.apply()
        self.apply('kit-test')
        context = self.home/'.ai-kit/context'
        self.assertTrue((context/'20_KIT_TEST.md').is_file())
        self.assertEqual(self.state()['practices'], ['core', 'kit-test'])
        self.assertEqual(self.state()['team'], 'kit-test')
        self.assertIn('report-check', self.state()['installed']['skills'])
        claude = (self.home/'.claude/CLAUDE.md').read_text(encoding='utf-8')
        self.assertLess(claude.index('10_CORE.md'), claude.index('20_KIT_TEST.md'))
        team_text = (context/'20_KIT_TEST.md').read_text(encoding='utf-8').strip()[:120]
        self.assertIn(team_text, (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))

    def test_m3_a_second_run_writes_nothing(self):
        for team in (None, 'kit-test'):
            with self.subTest(team=team):
                self.apply(team)
                before, digests = self.files(), self.state()['files']
                self.apply(team)
                self.assertEqual(self.files(), before)
                self.assertEqual(self.state()['files'], digests)

    def test_m7_an_approved_team_server_reaches_every_cli_as_written(self):
        self.apply()
        self.apply('kit-test', approve=True)
        claude = json.loads((self.home/'.claude.json').read_text(encoding='utf-8'))['mcpServers']['ai-kit-time']
        codex = tomllib.loads((self.home/'.codex/config.toml').read_text(encoding='utf-8'))['mcp_servers']['ai-kit-time']
        gemini = json.loads((self.home/'.gemini/settings.json').read_text(encoding='utf-8'))['mcpServers']['ai-kit-time']
        for name, server in (('claude', claude), ('codex', codex), ('gemini', gemini)):
            with self.subTest(cli=name):
                self.assertEqual((server['command'], server['args']), ('uvx', TIME_ARGS))



if __name__ == '__main__':
    unittest.main()
