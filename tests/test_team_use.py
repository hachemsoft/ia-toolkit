"""V2 slice 5 (docs/v2/git-sync.md "team use", docs/v2/cli.md): a Team from Git on top of the content, activated globally;
known Teams activated from the cache without network; an unknown Team only with its URL; a Team never brings commands and
never replaces a protected Core resource; rollback restores the previous Team. Local bare repositories, no network."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from installer import cli, sources, sync
from installer.core import ROOT, KitError
from installer.toml_files import dump_toml, read_toml
from test_git_sources import HAS_GIT, remove_repository, run_git


@unittest.skipUnless(HAS_GIT, 'git not installed')
class TeamTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base/'home'
        self.kit = self.home/'.ai-kit'
        self.kit.mkdir(parents=True)
        for patcher in (mock.patch.object(sources, 'LOCAL_FOR_TESTS', True), mock.patch('installer.config.ownership_problem', return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.managed = self.base/'managed.toml'
        self.work, self.bare = self.base/'team-work', self.base/'team.git'
        self.work.mkdir()
        (self.work/'aikit.toml').write_text('schema = 1\nname = "data"\nkind = "team"\n\n[defaults]\nextra_skills = ["sql-review", "data-check"]\n', encoding='utf-8')
        (self.work/'skills/data-check').mkdir(parents=True)
        (self.work/'skills/data-check/SKILL.md').write_text(
            '---\nname: data-check\ndescription: "Check a data change. Triggers: data check."\nmetadata:\n  aikit-version: "1.0.0"\n'
            '  aikit-origin: "team"\n  aikit-category: "domain"\n  aikit-tier: "optional"\n---\n\n# data-check\n\nCheck it.\n', encoding='utf-8')
        (self.work/'context').mkdir()
        (self.work/'context/rules.md').write_text('# Data team\n\nTeam rule marker.\n', encoding='utf-8')
        run_git('init', '-q', cwd=self.work)
        self.commit_tag('v1.0.0')
        run_git('clone', '-q', '--bare', str(self.work), str(self.bare), cwd=self.base)
        self.url = 'file://'+self.bare.as_posix()
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'claude', managed_file=self.managed)

    def commit_tag(self, tag, push=False):
        run_git('add', '-A', cwd=self.work)
        run_git('commit', '-q', '-m', tag, cwd=self.work)
        run_git('tag', '-a', tag, '-m', tag, cwd=self.work)
        if push:
            run_git('push', '-q', str(self.bare), 'main', tag, cwd=self.work)

    def use(self, name, url=None, ask=None, action='team-use'):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with sync.activation(self.home, action, False, managed_file=self.managed, team_name=name, team_url=url, ask_url=ask) as act:
                cli.apply('general', self.home, False, None, 'claude', act.team, extra_writes=act.writes, managed_file=self.managed)
        return out.getvalue()

    def state(self):
        return json.loads((self.kit/'state.json').read_text(encoding='utf-8'))

    def context_text(self):
        folder = self.home/self.state()['context_dir']
        return ''.join(p.read_text(encoding='utf-8') for p in folder.glob('*.md'))

    def test_team_use_installs_the_team_on_top_and_records_it(self):
        self.use('data', self.url)
        installed = self.state()['installed']['skills']
        self.assertIn('data-check', installed)
        self.assertIn('sql-review', installed)  # the Team's [defaults]
        self.assertIn('Team rule marker.', self.context_text())
        lock = read_toml(self.kit/'lock.toml')
        self.assertEqual((lock['sources']['team']['name'], lock['sources']['team']['tag']), ('data', 'v1.0.0'))
        mine = read_toml(self.kit/'aikit.toml')
        self.assertEqual((mine['teams']['data']['repo'], mine['user']['active_team']), (self.url, 'data'))
        self.assertEqual(self.state()['team'], 'data')
        self.assertEqual(self.state()['installed']['sources']['data-check'], 'team:data')
        self.assertEqual(self.state()['installed']['sources']['tdd'], 'package')

    def test_none_then_back_from_the_cache_without_network(self):
        self.use('data', self.url)
        self.use('none')
        self.assertNotIn('data-check', self.state()['installed']['skills'])
        self.assertNotIn('team', read_toml(self.kit/'lock.toml').get('sources', {}))
        self.assertIn('data', read_toml(self.kit/'lock.toml')['known_teams'])
        remove_repository(self.bare)  # no remote: the cached version is activated
        self.use('data')
        self.assertIn('data-check', self.state()['installed']['skills'])

    def test_an_unknown_team_needs_its_url(self):
        with self.assertRaises(KitError) as caught:
            self.use('data')
        self.assertIn('give its repository URL', str(caught.exception))
        self.use('data', ask=lambda name: self.url)  # asked in a terminal
        self.assertIn('data-check', self.state()['installed']['skills'])

    def test_it_restricts_teams(self):
        self.managed.write_text(dump_toml({'managed_schema': 1, 'teams': {'allowed': ['file:///nowhere']}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError):
            self.use('data', self.url)
        self.managed.write_text(dump_toml({'managed_schema': 1, 'teams': {'allow_unknown': False}}), encoding='utf-8')
        with self.assertRaises(sources.SourceError):
            self.use('data', ask=lambda name: self.url)
        self.assertFalse((self.kit/'lock.toml').exists())

    def test_a_team_never_brings_commands(self):
        (self.work/'commands').mkdir()
        (self.work/'commands/build.md').write_text('---\nname: build\n---\nmine\n', encoding='utf-8')
        self.commit_tag('v1.1.0', push=True)
        with self.assertRaises(sources.SourceError) as caught:
            self.use('data', self.url)
        self.assertIn('only the Core may define', str(caught.exception))

    def test_a_protected_core_skill_cannot_be_replaced(self):
        core = self.base/'core'
        for name in ('skills', 'agents', 'commands', 'context', 'templates', 'organization.toml', 'aikit.toml'):
            (shutil.copytree if (ROOT/name).is_dir() else shutil.copy2)(ROOT/name, core/name)
        tdd = core/'skills/internal/common/tdd/SKILL.md'
        tdd.write_text(tdd.read_text(encoding='utf-8').replace('metadata:\n', 'metadata:\n  aikit-protected: "true"\n', 1), encoding='utf-8')
        team = self.base/'team-tree'
        shutil.copytree(self.work, team, ignore=shutil.ignore_patterns('.git'))
        (team/'skills/tdd').mkdir()
        (team/'skills/tdd/SKILL.md').write_text('---\nname: tdd\ndescription: "x"\nmetadata:\n  aikit-version: "9.0.0"\n---\nx\n', encoding='utf-8')
        with self.assertRaises(sources.SourceError) as caught:
            sync.overlay(core, team, 'data')
        self.assertIn('protected Core skill tdd', str(caught.exception))
        tdd.write_text(tdd.read_text(encoding='utf-8').replace('  aikit-protected: "true"\n', ''), encoding='utf-8')
        merged = sync.overlay(core, team, 'data')
        self.addCleanup(shutil.rmtree, merged, True)
        self.assertEqual((merged/'skills/team-data/tdd/SKILL.md').read_text(encoding='utf-8').split('\n')[1], 'name: tdd')
        self.assertFalse((merged/'skills/internal/common/tdd').exists())

    def test_rollback_restores_the_previous_team_and_status_shows_it(self):
        self.use('data', self.url)
        self.use('none')
        self.use(None, action='rollback')
        self.assertIn('data-check', self.state()['installed']['skills'])
        self.assertEqual(read_toml(self.kit/'aikit.toml')['user']['active_team'], 'data')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            from installer.status import status
            status(self.home)
        self.assertIn('Team data v1.0.0', out.getvalue())

    def test_the_cli_commands(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['team', 'list', '--home', str(self.home)]), 0)
        self.assertIn('No Team known', out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['team', 'frobnicate', '--home', str(self.home)]), 2)
            self.assertEqual(cli.main(['status', '--verbose', '--home', str(self.home)]), 0)
        self.assertIn('team needs', err.getvalue())


if __name__ == '__main__':
    unittest.main()
