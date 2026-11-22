"""Version C of the agents (spec docs/sdlc/2026-11-14-kit-agents/spec-c.md): four optional read-only agents,
silent-failure-hunter, pattern-scout, rule-miner and fresh-eyes, called at the standard and full levels only when installed.
Content and installation checks; their behaviour is measured by eval cases, written and run only on request."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
NAMES = ('silent-failure-hunter', 'pattern-scout', 'rule-miner', 'fresh-eyes')


def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


def agent(name):
    path = ROOT/'agents/internal/common'/(name+'.md')
    return path.read_text(encoding='utf-8') if path.is_file() else ''


class AgentsTests(unittest.TestCase):
    """T1, R1, R3, R5, R7, R9: what each agent looks for and returns; read-only, cold, optional, with its limits."""

    def test_common_form(self):
        for name in NAMES:
            with self.subTest(agent=name):
                text = agent(name)
                for words in ('aikit-default: "false"', 'Not for:', 'Modify nothing', 'limits', 'Cold'):
                    self.assertIn(words, text)
                self.assertNotIn('tools:', text.split('---')[1] if text.count('---') >= 2 else 'tools:')

    def test_each_mission(self):
        expected = {
            'silent-failure-hunter': ('Cold review', 'empty `catch`', 'fallback', 'return code ignored', 'COALESCE',
                                      'the input that triggers', 'what the caller sees', 'Important', 'Minor'),
            'pattern-scout': ('two or three places', 'file:line', 'the shared convention', 'what differs', 'nothing comparable'),
            'rule-miner': ('Given', 'When', 'Then', 'file:line', 'contradict', 'written nowhere but in the code', 'never invent'),
            'fresh-eyes': ('a newcomer', 'never the conversation', 'GLOSSARY.md', 'the question you would ask', 'rewrite nothing'),
        }
        for name, words in expected.items():
            text = agent(name)
            for word in words:
                with self.subTest(agent=name, words=word):
                    self.assertIn(word, text)


class CallsTests(unittest.TestCase):
    """T2, R2, R4, R6, R8: each call happens only when the agent is installed, at the standard and full levels."""

    def test_where_each_is_called(self):
        calls = {
            'skills/internal/common/code-review/SKILL.md': ('When ai-kit-silent-failure-hunter is installed and the review is not quick', 'not installed: skip it and say nothing'),
            'skills/internal/development/code-change/SKILL.md': ('when ai-kit-pattern-scout is installed',),
            'skills/internal/analytics/kpi-definition/SKILL.md': ('when ai-kit-rule-miner is installed',),
            'commands/spec.md': ('when ai-kit-rule-miner is installed', 'when ai-kit-fresh-eyes is installed'),
            'commands/ship.md': ('when ai-kit-fresh-eyes is installed',),
        }
        for rel, words in calls.items():
            text = read(rel)
            for word in words:
                with self.subTest(file=rel, words=word):
                    self.assertIn(word, text)

    def test_within_their_budget(self):
        sys.path.insert(0, str(ROOT))
        from installer.core import load_commands
        sizes = {c['name']: len(c['prompt']) for c in load_commands()}
        for name in ('spec', 'ship'):
            self.assertLess(sizes[name], 4000, name)
        # 4.23.3: + the one-line contract rule in /build (Codex classed a contract change as quick in four releases).
        self.assertLess(sizes['build'], 4200, 'build')


class AvailabilityTests(unittest.TestCase):
    """T3, R10: none is installed by default, each installs through extra_agents; the docs give a set per role."""

    def test_installed_only_when_chosen(self):
        self.assertTrue(all(agent(name) for name in NAMES), 'an agent of the batch is missing')
        sys.path.insert(0, str(ROOT))
        from presets import apply_as
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('general', Path(tmp), False, None, 'gemini')
            for name in NAMES:
                self.assertFalse((Path(tmp)/'.gemini/agents'/('ai-kit-'+name+'.md')).exists(), name)
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('general', Path(tmp), False, None, 'gemini', choices={'extra_agents': list(NAMES)})
            for name in NAMES:
                self.assertTrue((Path(tmp)/'.gemini/agents'/('ai-kit-'+name+'.md')).is_file(), name)

    def test_the_docs_give_a_set_per_role(self):
        commands = read('docs/commands.md')
        for name in NAMES:
            self.assertIn(name, commands)
        self.assertIn('extra_agents', read('docs/repositories.md'))
        for words in ('development → silent-failure-hunter, pattern-scout', 'data → rule-miner', 'everyone → fresh-eyes'):
            self.assertIn(words, read('docs/repositories.md'))


if __name__ == '__main__':
    unittest.main()
