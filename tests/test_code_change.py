"""One language-agnostic code-change playbook replaces python-js-change and java-change (ADR 0031): the body holds what
applies to any language; a language's pitfalls the model would otherwise miss live in references/<language>.md, read
only for a change in that language."""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
PLAYBOOK = ROOT/'skills/internal/development/code-change'
LANGUAGES = ('python', 'javascript', 'java', 'php', 'go', 'scala')


def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


class CodeChangePlaybookTests(unittest.TestCase):
    def test_one_optional_playbook_for_any_language(self):
        skill = (PLAYBOOK/'SKILL.md').read_text(encoding='utf-8')
        for words in ('name: code-change', 'aikit-default: "false"', 'aikit-requires: "tdd"', 'in any language',
                      'Not for: SQL or dbt models', 'infrastructure',
                      'implicit framework migration', 'Preserve public contracts', 'a new library'):
            self.assertIn(words, skill)
        self.assertFalse((ROOT/'skills/internal/development/python-js-change').exists())
        self.assertFalse((ROOT/'skills/internal/development/java-change').exists())

    def test_language_references_are_read_only_when_they_apply(self):
        skill = (PLAYBOOK/'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('read references/<language>.md only when the change is in that language', skill)
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertIn('references/'+language+'.md', skill)
                text = (PLAYBOOK/'references'/(language+'.md')).read_text(encoding='utf-8')
                self.assertLess(len(text.splitlines()), 40)  # pitfalls only, not a course

    def test_installed_with_its_references(self):
        from presets import apply_as
        sys.path.insert(0, str(ROOT))
        from installer.toml_files import dump_toml
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            home = Path(tmp)
            (home/'.ai-kit').mkdir()
            (home/'.ai-kit/aikit.toml').write_text(dump_toml({'schema': 1, 'user': {'extra_skills': ['code-change']}}), encoding='utf-8')
            apply_as('general', home, False, None, 'gemini')
            self.assertTrue((home/'.gemini/skills/code-change/references/php.md').is_file())

    def test_no_text_cites_the_old_playbooks(self):
        found = subprocess.run(['git', 'grep', '-l', '-e', 'python-js-change', '-e', 'java-change', '--', '.',
                                ':!CHANGELOG.md', ':!evals/results', ':!tests/test_code_change.py', ':!docs/adr', ':!versions.lock.json'],
                               cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
