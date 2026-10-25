"""Invariants du kit : règles de sécurité et de comportement qu'aucun changement ne doit casser.

Chaque test correspond à une règle écrite dans la doc (README, docs/cli/*, docs/hooks.md) ou dans les principes du projet.
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
        """Jamais de mode qui saute les confirmations (yolo, skip-permissions, approbation automatique)."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True, 'protected-paths': True}})
        forbidden = re.compile(r'yolo|skip-permissions|dangerously|bypass|approval[-_]?(mode|policy)\s*=\s*"?never', re.I)
        for path, text in config_texts(self.home):
            self.assertIsNone(forbidden.search(text), str(path))

    def test_codex_hook_trust_left_to_user(self):
        """Les hooks Codex ne tournent qu'après approbation dans Codex : le kit n'écrit jamais d'approbation."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True}})
        config = (self.home/'.codex/config.toml').read_text(encoding='utf-8')
        self.assertIn('[[hooks.PreToolUse]]', config)
        self.assertNotRegex(config, r'trusted_hash|trust_level|\btrusted\b')

    def test_no_authentication_without_overrides(self):
        """Sans overrides, le kit ne configure ni l'authentification, ni le modèle, ni de fichier .env."""
        install(self.home)
        settings = json.loads((self.home/'.gemini/settings.json').read_text(encoding='utf-8'))
        self.assertNotIn('auth', settings.get('security', {}))
        self.assertNotIn('model', settings)
        self.assertFalse((self.home/'.gemini/.env').exists())

    def test_writes_only_under_home(self):
        """Le kit n'écrit jamais dans le dossier courant (un repo de projet) : tout va sous le dossier personnel."""
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
        """Le rangement retire les dossiers vides laissés par une suppression, jamais un dossier racine ni structurant."""
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
        """L'équipe travaille en MR : ce que l'agent lit (commandes, pratiques, gabarits) ne parle pas de pull request."""
        files = [p for d in ('commands', 'practices', 'templates') for p in (ROOT/d).rglob('*.md')]
        for path in files:
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 'merge request' in line:
                    continue  # la règle de traduction elle-même (00_KIT.md)
                self.assertNotRegex(line, r'(?i:pull request)|\bPRs?\b', f'{path.relative_to(ROOT)}:{number}')

    def test_adapters_respect_the_contract(self):
        """Chaque adaptateur fournit toute l'interface ; les capacités facultatives sont déclarées par leur présence."""
        for adapter in ADAPTERS:
            self.assertIsInstance(adapter, Adapter, adapter.__name__)
        self.assertEqual(len({a.NAME for a in ADAPTERS}), len(ADAPTERS))
        self.assertIsInstance(gemini, ContextHost)
        self.assertIsInstance(gemini, LiveCheck)
        self.assertNotIsInstance(agy, ContextHost)
        self.assertNotIsInstance(codex, ContextHost)

    def test_each_cli_alone_gets_the_whole_profile(self):
        """Installée seule, chaque CLI reçoit tous les skills et tous les agents du profil."""
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
        """La table des profils de docs/getting-started.md est celle que le code installe (scripts/profile_table.py --write)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('profile_table', ROOT/'scripts/profile_table.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text = module.PAGE.read_text(encoding='utf-8')
        self.assertEqual(text, module.page_with_table(text), 'lancer python3 scripts/profile_table.py --write')

    def test_doc_links_and_anchors_resolve(self):
        """Chaque lien relatif de la doc mène à un fichier qui existe, et chaque ancre à un titre de ce fichier (règle des ancres GitHub)."""
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
        """Une installation d'avant la 0.19 (~/.ai-toolkit) est renommée en ~/.ai-kit au premier update, sans rien perdre."""
        install(self.home, overrides={'hooks': {'dbt-prod-guard': True}})
        kit = self.home/'.ai-kit'
        # Simuler l'ancienne installation : dossier renommé, préfixes de l'état et chemins des déclarations en .ai-toolkit.
        state = json.loads((kit/'state.json').read_text(encoding='utf-8'))
        for rel in ('.gemini/settings.json', '.codex/config.toml', '.gemini/config/plugins/ai-kit/hooks.json'):
            path = self.home/rel
            path.write_bytes(path.read_bytes().replace(b'.ai-kit', b'.ai-toolkit'))
            if rel in state['files']:
                state['files'][rel] = digest(path.read_bytes())
        _, block, _ = split_block((self.home/'.codex/config.toml').read_text(encoding='utf-8'), CODEX_TOML, 'config.toml')
        state['blocks']['.codex/config.toml'] = digest(block.encode('utf-8'))
        # Tout chemin du dossier du kit enregistré dans l'état (fichiers, déclarations des garde-fous) porte l'ancien nom.
        (kit/'state.json').write_text(json.dumps(state).replace('.ai-kit', '.ai-toolkit'), encoding='utf-8')
        os.replace(kit, self.home/'.ai-toolkit')
        with contextlib.redirect_stdout(io.StringIO()):
            apply('data-developer', self.home, True, IDENTITY, 'all')  # --dry-run : ne renomme rien
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
        """Sous Windows, un fichier lu ou écrit sans encodage passe en cp1252 : toujours préciser encoding='utf-8'."""
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

if __name__ == '__main__':
    unittest.main()
