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

from installer.adapters import ADAPTERS, agy, codex, gemini
from installer.cli import apply, prune_empty_dirs
from installer.interface import Adapter, ContextHost, LiveCheck
from installer.adapters.codex import CODEX_TOML
from installer.core import KitError, ROOT, digest, split_block

IDENTITY = {'email': 'test@example.org', 'source': 'test'}
CONFIG_FILES = ('settings.json', 'config.toml', 'hooks.json', 'plugin.json', 'mcp_config.json', '.env')


def install(home, target='all', overrides=None):
    if overrides is not None:
        (home/'.ai-kit').mkdir(parents=True, exist_ok=True)
        (home/'.ai-kit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        apply('data-developer', home, False, IDENTITY, target)


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
        """The team works with MRs: what the agent reads (commands, practices, templates) does not mention pull requests."""
        files = [p for d in ('commands', 'practices', 'templates') for p in (ROOT/d).rglob('*.md')]
        for path in files:
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 'merge request' in line:
                    continue  # the translation rule itself (00_KIT.md)
                self.assertNotRegex(line, r'(?i:pull request)|\bPRs?\b', f'{path.relative_to(ROOT)}:{number}')

    def test_adapters_respect_the_contract(self):
        """Each adapter provides the whole interface; optional capabilities are declared by their presence."""
        for adapter in ADAPTERS:
            self.assertIsInstance(adapter, Adapter, adapter.__name__)
        self.assertEqual(len({a.NAME for a in ADAPTERS}), len(ADAPTERS))
        self.assertIsInstance(gemini, ContextHost)
        self.assertIsInstance(gemini, LiveCheck)
        self.assertNotIsInstance(agy, ContextHost)
        self.assertNotIsInstance(codex, ContextHost)

    def test_each_cli_alone_gets_the_whole_profile(self):
        """Installed alone, each CLI gets all the skills and all the agents of the profile."""
        profile = json.loads((ROOT/'profiles/general.json').read_text(encoding='utf-8'))
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

    def test_profile_table_is_current(self):
        """The profile table in docs/getting-started.md is the one the code installs (scripts/profile_table.py --write)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('profile_table', ROOT/'scripts/profile_table.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text = module.PAGE.read_text(encoding='utf-8')
        self.assertEqual(text, module.page_with_table(text), 'run python3 scripts/profile_table.py --write')

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

    def test_legacy_kit_dir_migrated(self):
        """An installation from before 0.19 (~/.ai-toolkit) is renamed to ~/.ai-kit on the first update, without losing anything."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True}})
        kit = self.home/'.ai-kit'
        # Simulate the old installation: folder renamed, state prefixes and declaration paths using .ai-toolkit.
        state = json.loads((kit/'state.json').read_text(encoding='utf-8'))
        for rel in ('.gemini/settings.json', '.codex/config.toml', '.gemini/config/plugins/ai-kit/hooks.json'):
            path = self.home/rel
            path.write_bytes(path.read_bytes().replace(b'.ai-kit', b'.ai-toolkit'))
            if rel in state['files']:
                state['files'][rel] = digest(path.read_bytes())
        _, block, _ = split_block((self.home/'.codex/config.toml').read_text(encoding='utf-8'), CODEX_TOML, 'config.toml')
        state['blocks']['.codex/config.toml'] = digest(block.encode('utf-8'))
        # Every kit folder path recorded in the state (files, guardrail declarations) carries the old name.
        (kit/'state.json').write_text(json.dumps(state).replace('.ai-kit', '.ai-toolkit'), encoding='utf-8')
        os.replace(kit, self.home/'.ai-toolkit')
        with contextlib.redirect_stdout(io.StringIO()):
            apply('data-developer', self.home, True, IDENTITY, 'all')  # --dry-run: renames nothing
        self.assertTrue((self.home/'.ai-toolkit').is_dir())
        install(self.home, overrides=None)
        self.assertFalse((self.home/'.ai-toolkit').exists())
        self.assertEqual(json.loads((kit/'overrides.json').read_text(encoding='utf-8')), {'hooks': {'dbt-prod-guard': True}})
        state = json.loads((kit/'state.json').read_text(encoding='utf-8'))
        self.assertFalse([rel for rel in state['files'] if rel.startswith('.ai-toolkit/')])
        for rel in ('.gemini/settings.json', '.codex/config.toml', '.gemini/config/plugins/ai-kit/hooks.json'):
            self.assertNotIn('.ai-toolkit', (self.home/rel).read_text(encoding='utf-8'), rel)
        self.assertTrue((kit/'hooks/dbt-prod-guard.py').is_file())

    def test_both_kit_dirs_refused(self):
        install(self.home)
        (self.home/'.ai-toolkit').mkdir()
        with self.assertRaises(KitError):
            install(self.home)

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
        self.assertIn('replaces kit skills: .agents/skills/code-review', out.getvalue())
        self.assertNotIn('team-only', out.getvalue())

    def test_no_skill_shares_a_command_name(self):
        """Gemini CLI turns every skill into a /command: a skill with a command's name makes both get renamed (/guide1, /user.guide)."""
        from installer.core import load_commands
        catalog = json.loads((ROOT/'skills/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(set(catalog) & {c['name'] for c in load_commands()}), [])

if __name__ == '__main__':
    unittest.main()
