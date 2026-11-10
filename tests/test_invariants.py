"""Kit invariants: safety and behaviour rules that no change may break.

Each test matches a rule written in the docs (README, docs/cli/*, docs/hooks.md) or in the project principles.
"""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from installer.adapters import ADAPTERS, gemini
from installer.resolve import skill_catalog
from installer.cli import apply, prune_empty_dirs
from installer.interface import Adapter, LiveCheck
from installer.core import ROOT
from personal import write_personal
from v1_profiles import apply_as  # noqa: E402
from installer.settings import core_selection  # noqa: E402

IDENTITY = {'email': 'test@example.org', 'source': 'test'}
CONFIG_FILES = ('settings.json', 'config.toml', 'hooks.json', 'plugin.json', 'mcp_config.json', '.env')


def install(home, target='all', overrides=None):
    if overrides is not None:
        write_personal(home, overrides)
    with contextlib.redirect_stdout(io.StringIO()):
        apply_as('data-developer', home, False, IDENTITY, target)


def config_texts(home):
    for path in home.rglob('*'):
        if path.is_file() and path.name in CONFIG_FILES:
            yield path, path.read_text(encoding='utf-8')


class InvariantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)/'home'
        self.home.mkdir()

    def test_installer_modules_stay_readable(self):
        root = Path(__file__).resolve().parents[1]/'installer'
        long = {p.name: n for p in root.rglob('*.py') if (n := p.read_text(encoding='utf-8').count('\n')) > 800}
        self.assertEqual(long, {}, 'split by responsibility (docs/architecture.md)')

    def test_no_permission_bypass_in_configuration(self):
        """Never a mode that skips confirmations (yolo, skip-permissions, automatic approval)."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True, 'protected-paths': True}})
        forbidden = re.compile(r'yolo|skip-permissions|dangerously|bypass|approval[-_]?(mode|policy)\s*=\s*"?never', re.I)
        for path, text in config_texts(self.home):
            self.assertIsNone(forbidden.search(text), str(path))

    def test_codex_hook_trust_left_to_user(self):
        """Codex hooks only run after approval in Codex: the kit never writes an approval."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True}})
        config = (self.home/'.codex/config.toml').read_text(encoding='utf-8')
        self.assertIn('[[hooks.PreToolUse]]', config)
        self.assertNotRegex(config, r'trusted_hash|trust_level|\btrusted\b')

    def test_no_authentication_without_overrides(self):
        """Without overrides, the kit configures neither authentication, nor the model, nor a .env file."""
        install(self.home)
        settings = json.loads((self.home/'.gemini/settings.json').read_text(encoding='utf-8'))
        self.assertNotIn('auth', settings.get('security', {}))
        self.assertNotIn('model', settings)
        self.assertFalse((self.home/'.gemini/.env').exists())

    def test_writes_only_under_home(self):
        """The kit never writes in the current folder (a project repo): everything goes under the home folder."""
        project = Path(self.temp.name)/'project'
        project.mkdir()
        previous = os.getcwd()
        os.chdir(project)
        try:
            install(self.home)
        finally:
            os.chdir(previous)
        self.assertEqual(list(project.iterdir()), [])
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()), ['home', 'project'])

    def test_prune_stays_bounded(self):
        """Cleanup removes empty folders left by a deletion, never a root or structural folder."""
        stop = self.home/'.gemini'
        leaf = stop/'skills'/'old-skill'/'refs'
        leaf.mkdir(parents=True)
        outside = self.home/'outside'/'empty'
        outside.mkdir(parents=True)
        prune_empty_dirs(leaf, stop)
        self.assertFalse((stop/'skills'/'old-skill').exists())
        self.assertTrue((stop/'skills').is_dir())
        prune_empty_dirs(outside, stop)
        self.assertTrue(outside.is_dir())

    def test_merge_request_wording(self):
        """The agent follows the repo's convention, merge request or pull request: what it reads (commands, practices,
        templates) never names one without the other. 0.34: before, pull requests could not be named at all (an MR-only team)."""
        files = [p for d in ('commands', 'context', 'templates') for p in (ROOT/d).rglob('*.md')]
        for path in files:
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 'merge request' in line:
                    continue  # names both, or the merge request only (the repo's term decides, 00_KIT.md)
                self.assertNotRegex(line, r'(?i:pull request)|\bPRs?\b', f'{path.relative_to(ROOT)}:{number}')

    def test_adapters_respect_the_contract(self):
        """Each adapter provides the whole interface; optional capabilities are declared by their presence."""
        for adapter in ADAPTERS:
            self.assertIsInstance(adapter, Adapter, adapter.__name__)
        self.assertEqual(len({a.NAME for a in ADAPTERS}), len(ADAPTERS))
        self.assertIsInstance(gemini, LiveCheck)

    def test_each_cli_alone_gets_the_whole_profile(self):
        """Installed alone, each CLI gets all the skills and all the agents of the profile."""
        profile = core_selection()
        places = {'gemini': ('.gemini/skills', '.gemini/agents'),
                  'agy': ('.gemini/skills', '.gemini/config/plugins/ai-kit/agents'),
                  'codex': ('.codex/skills', '.codex/ai-kit/agents')}
        for target, (skills_dir, agents_dir) in places.items():
            home = Path(self.temp.name)/target
            home.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                apply('general', home, False, IDENTITY, target)
            for skill in profile['skills']:
                self.assertTrue((home/skills_dir/skill/'SKILL.md').is_file(), target+' : skill '+skill)
            agents = sorted(f.stem for f in (home/agents_dir).iterdir())
            self.assertEqual(agents, sorted('ai-kit-'+a for a in profile['agents']), target)

    def test_selection_table_is_current(self):
        """The profile table in docs/getting-started.md is the one the code installs (scripts/selection_table.py --write)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('selection_table', ROOT/'scripts/selection_table.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text = module.PAGE.read_text(encoding='utf-8')
        self.assertEqual(text, module.page_with_table(text), 'run python3 scripts/selection_table.py --write')

    def test_doc_links_and_anchors_resolve(self):
        """Each relative link in the docs leads to an existing file, and each anchor to a heading of that file (GitHub anchor rule)."""
        def slug(heading):
            return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')
        pages = [ROOT/'README.md', ROOT/'CHANGELOG.md'] + list((ROOT/'docs').rglob('*.md'))
        for page in pages:
            if page.name.startswith('plan-') or page.name in ('roadmap.md', 'portability-report.md'):
                continue
            for match in re.finditer(r'\]\(([^)\s]+)\)', page.read_text(encoding='utf-8')):
                link = match.group(1)
                if link.startswith(('http', 'mailto', '~')):
                    continue
                path, _, anchor = link.partition('#')
                target = (page.parent/path) if path else page
                self.assertTrue(target.exists(), f'{page.relative_to(ROOT)} → {link}')
                if anchor and target.suffix == '.md':
                    headings = {slug(h) for h in re.findall(r'^#+ (.+)$', target.read_text(encoding='utf-8'), re.M)}
                    self.assertIn(anchor, headings, f'{page.relative_to(ROOT)} → {link}')

    def test_files_always_opened_with_an_encoding(self):
        """On Windows, a file read or written without an encoding uses cp1252: always pass encoding='utf-8'."""
        import ast
        sources = [p for d in ('installer', 'runtime', 'scripts', 'evals', 'tests') for p in (ROOT/d).rglob('*.py')]
        missing = []
        for source in sources:
            for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
                if not isinstance(node, ast.Call) or any(k.arg == 'encoding' for k in node.keywords):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ('read_text', 'write_text'):
                    missing.append(f'{source.relative_to(ROOT)}:{node.lineno}')
                elif isinstance(func, ast.Name) and func.id == 'open':
                    mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 'r'
                    if 'b' not in str(mode):
                        missing.append(f'{source.relative_to(ROOT)}:{node.lineno}')
        self.assertEqual(missing, [])

    def test_doctor_lists_repo_skills_that_replace_kit_skills(self):
        """Phase 2 : un skill de repo qui porte le nom d'un skill du kit est signalé par doctor, lancé depuis ce repo."""
        from installer.cli import doctor
        install(self.home, target='gemini')
        repo = Path(self.temp.name)/'repo'
        (repo/'.git').mkdir(parents=True)
        (repo/'.agents/skills/code-review').mkdir(parents=True)
        (repo/'.agents/skills/code-review/SKILL.md').write_text('---\nname: code-review\ndescription: x\n---\n', encoding='utf-8')
        (repo/'.agents/skills/team-only').mkdir(parents=True)
        (repo/'.agents/skills/team-only/SKILL.md').write_text('---\nname: team-only\ndescription: x\n---\n', encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            doctor(self.home, cwd=repo/'.agents')
        self.assertIn('has skills named like kit skills: .agents/skills/code-review', out.getvalue())
        self.assertNotIn('team-only', out.getvalue())

    def test_no_skill_shares_a_command_name(self):
        """Gemini CLI turns every skill into a /command: a skill with a command's name makes both get renamed (/guide1, /user.guide)."""
        from installer.core import load_commands
        catalog = skill_catalog(ROOT)
        self.assertEqual(sorted(set(catalog) & {c['name'] for c in load_commands()}), [])

if __name__ == '__main__':
    unittest.main()
