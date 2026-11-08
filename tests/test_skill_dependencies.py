"""Skills that cite other skills: a required one is in requires, an optional one is in optional with what to do without it."""
import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest

from installer.cli import apply, resolve_skills, ROOT
from installer.resolve import skill_catalog
from installer.core import KitError, read_json
from installer.toml_files import dump_toml, read_toml

CATALOG = skill_catalog(ROOT)


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


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    return text.split('\n---', 1)[0] if text.startswith('---') else ''


def user_only(skill):
    """disable-model-invocation: true — Claude Code hides it from the model and refuses it in the Skill tool; Codex hides it."""
    return bool(re.search(r'^disable-model-invocation:\s*true\s*$', frontmatter(ROOT/CATALOG[skill]['path']/'SKILL.md'), re.M))


# 0.52.0: these skills carry a whole command's method; they became model-invocable with a guard so /spec, /learn… can chain them.
COMMAND_SKILLS = {'to-spec': 'spec', 'teach': 'learn', 'retrospective': 'retro', 'wayfinder': 'map', 'ticket-sorting': 'triage',
                  'to-questionnaire': 'ask', 'improve-codebase-architecture': 'audit', 'zoom-out': 'explain', 'wait-what': 'explain',
                  'handover': 'handoff'}


class ChainTests(unittest.TestCase):
    """0.52.0: a command chains only skills the model can invoke. Observed on Claude Code 2.1.317 to 2.1.319 and Codex 0.167.0: a
    user-only skill is absent from the model's skill list, and Claude Code refuses it ("do not replicate this skill's workflow")."""
    def commands(self):
        return sorted((ROOT/'commands').glob('*.md'))

    def test_no_command_chains_a_user_only_skill(self):
        for path in self.commands():
            head = frontmatter(path)
            listed = re.search(r'^skills:\s*\[(.*)\]', head, re.M)
            names = [n.strip() for n in listed.group(1).split(',') if n.strip()] if listed else []
            names += re.findall(r'[Aa]ctivate the ([a-z0-9-]+) skill', path.read_text(encoding='utf-8'))
            for name in names:
                with self.subTest(command=path.stem, skill=name):
                    self.assertIn(name, CATALOG)
                    self.assertFalse(user_only(name), '/'+path.stem+' chains '+name+', which the model cannot invoke')

    def test_command_skills_are_guarded_against_activating_on_their_own(self):
        for skill, command in COMMAND_SKILLS.items():
            with self.subTest(skill):
                head = frontmatter(ROOT/CATALOG[skill]['path']/'SKILL.md')
                self.assertFalse(user_only(skill))
                self.assertIn('/'+command, head)
                self.assertIn('do not activate on your own', head)

    def test_no_command_keeps_the_old_fallback(self):
        # "if the skill tool is unavailable" was wrong on Claude Code (the tool exists) and contradicted the CLI's refusal.
        for path in self.commands():
            with self.subTest(path.stem):
                self.assertNotIn('skill tool is unavailable', path.read_text(encoding='utf-8'))


class InstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def install(self, overrides, profile='general'):
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        (self.home/'.ai-kit/overrides.toml').write_text(dump_toml(overrides), encoding='utf-8')
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
        general = read_toml(ROOT/'profiles/general.toml')
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
