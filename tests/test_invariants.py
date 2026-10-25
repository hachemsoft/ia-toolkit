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

from installer.cli import apply, prune_empty_dirs
from installer.core import ROOT

IDENTITY = {'email': 'test@example.org', 'source': 'test'}
CONFIG_FILES = ('settings.json', 'config.toml', 'hooks.json', 'plugin.json', 'mcp_config.json', '.env')


def install(home, target='all', overrides=None):
    if overrides is not None:
        (home/'.ai-toolkit').mkdir(parents=True, exist_ok=True)
        (home/'.ai-toolkit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
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

if __name__ == '__main__':
    unittest.main()
