"""Skills that cite other skills: a required one is in requires, an optional one is in optional with what to do without it."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from installer.cli import apply, resolve_skills, ROOT
from installer.core import KitError, read_json

CATALOG = read_json(ROOT/'skills/catalog.json')


def cited(skill):
    """Other catalog skills a skill's files cite by name (`name`, the name skill, /name)."""
    text = ''.join(f.read_text(encoding='utf-8') for f in (ROOT/CATALOG[skill]['path']).rglob('*.md'))
    return {other for other in CATALOG if other != skill and not CATALOG[other].get('replaced_by') and re.search(
        r'(`/?'+re.escape(other)+r'`|\b'+re.escape(other)+r'\s+skill|skill\s+`?'+re.escape(other)+r'\b|/'+re.escape(other)+r'\b)', text)}


class CatalogTests(unittest.TestCase):
    def test_every_cited_skill_is_declared(self):
        for skill, entry in CATALOG.items():
            if entry.get('replaced_by'):
                continue
            undeclared = cited(skill) - set(entry.get('requires', [])) - set(entry.get('optional', {}))
            self.assertEqual(undeclared, set(), skill+' cites skills it neither requires nor lists as optional')

    def test_declared_names_exist_and_optional_has_an_alternative(self):
        for skill, entry in CATALOG.items():
            for name in entry.get('requires', []) + list(entry.get('optional', {})):
                self.assertIn(name, CATALOG, skill)
            for name, alternative in entry.get('optional', {}).items():
                self.assertTrue(isinstance(alternative, str) and alternative.strip(), skill+' → '+name)
            self.assertFalse(set(entry.get('requires', [])) & set(entry.get('optional', {})), skill)


class InstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def install(self, overrides, profile='general'):
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        (self.home/'.ai-kit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            notices = apply(profile, self.home, False, None, 'gemini')
        return read_json(self.home/'.ai-kit/state.json')['installed']['skills'], notices

    def test_playbook_added_alone_brings_what_it_requires_and_says_what_is_missing(self):
        skills, _ = self.install({'extra_skills': ['python-js-change']})
        self.assertIn('tdd', skills)
        self.assertNotIn('codebase-design', skills)
        text = (self.home/'.gemini/skills/python-js-change/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('## Not installed here', text)
        self.assertIn('`codebase-design`: before adding an interface', text)
        skills, _ = self.install({'extra_skills': ['python-js-change', 'codebase-design']})
        self.assertNotIn('`codebase-design`:', (self.home/'.gemini/skills/python-js-change/SKILL.md').read_text(encoding='utf-8'))

    def test_each_playbook_installs_alone_on_general_without_duplicates(self):
        general = read_json(ROOT/'profiles/general.json')
        for skill, entry in CATALOG.items():
            if entry.get('category') != 'domain':
                continue
            with self.subTest(skill=skill):
                selected = resolve_skills({**general, 'skills': general['skills']+[skill]}, {}, CATALOG, log=lambda *_: None)
                self.assertEqual(len(selected), len(set(selected)))
                for name in entry.get('requires', []):
                    self.assertIn(name, selected)

    def test_disabled_required_skill_is_refused_not_reactivated(self):
        with self.assertRaises(KitError) as caught:
            self.install({'extra_skills': ['python-js-change'], 'disabled_skills': ['tdd']}, profile='general')
        self.assertIn('tdd', str(caught.exception))

    def test_disabled_optional_skill_stays_disabled(self):
        skills, _ = self.install({'extra_skills': ['architecture-decision'], 'disabled_skills': ['prototype']})
        self.assertNotIn('prototype', skills)

    def test_unknown_names_are_reported(self):
        _, notices = self.install({'disabled_skills': ['tddd'], 'disabled_agents': ['verifierr']})
        self.assertTrue(any('disabled_skills: unknown name tddd' in n for n in notices), notices)
        self.assertTrue(any('disabled_agents: unknown name verifierr' in n for n in notices), notices)
        with self.assertRaises(KitError):
            self.install({'extra_skills': ['nope']})

    def test_renamed_skill_names_still_work(self):
        skills, _ = self.install({'extra_skills': ['handoff']})
        self.assertIn('handover', skills)


if __name__ == '__main__':
    unittest.main()
