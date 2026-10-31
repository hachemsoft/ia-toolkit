"""The same rule on every CLI: one of the person's own skills or commands with a kit name is kept, and the kit's is
installed with the prefix (skill_prefix, ai-kit- by default), its references rewritten; never a failed installation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import KitError, rename_references


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def mine(self, rel, text='mine\n'):
        path = self.home/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def run_kit(self, target):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, target)

    def read(self, rel):
        return (self.home/rel).read_text(encoding='utf-8')


class GeminiTests(Base):
    def test_personal_skill_kept_kit_skill_prefixed_and_referenced(self):
        mine = self.mine('.gemini/skills/implement/SKILL.md')
        notices = self.run_kit('gemini')
        self.assertEqual(mine.read_text(encoding='utf-8'), 'mine\n')
        self.assertIn('name: ai-kit-implement', self.read('.gemini/skills/ai-kit-implement/SKILL.md'))
        self.assertIn('the ai-kit-implement skill', self.read('.gemini/commands/build.toml'))
        self.assertTrue(any('skill implement as ai-kit-implement' in n for n in notices))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor_checks(self.home)
        self.assertNotIn('[Check] Command /build', out.getvalue())

    def test_back_to_the_plain_name_when_the_persons_skill_is_gone(self):
        mine = self.mine('.gemini/skills/tdd/SKILL.md')
        self.run_kit('gemini')
        mine.unlink()
        mine.parent.rmdir()
        self.run_kit('gemini')
        self.assertTrue((self.home/'.gemini/skills/tdd/SKILL.md').is_file())
        self.assertFalse((self.home/'.gemini/skills/ai-kit-tdd').exists())

    def test_empty_prefix_refuses_a_collision(self):
        self.mine('.gemini/skills/tdd/SKILL.md')
        overrides = self.home/'.ai-kit/overrides.json'
        overrides.parent.mkdir()
        overrides.write_text(json.dumps({'skill_prefix': ''}), encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_kit('gemini')


class AgyTests(Base):
    def test_command_skill_renamed_when_a_personal_skill_has_its_name(self):
        self.mine('.gemini/skills/review/SKILL.md')
        notices = self.run_kit('agy')
        plugin = self.home/'.gemini/config/plugins/ai-kit/skills'
        self.assertTrue((plugin/'ai-kit-review/SKILL.md').is_file())
        self.assertFalse((plugin/'review').exists())
        self.assertTrue(any('command /review as /ai-kit-review' in n for n in notices))

    def test_agents_carry_agys_tool_names(self):
        self.run_kit('agy')
        verifier = self.read('.gemini/config/plugins/ai-kit/agents/ai-kit-verifier.md')
        self.assertIn('"run_command"', verifier)
        self.assertIn('"list_dir"', verifier)
        self.assertNotIn('run_shell_command', verifier)
        self.assertNotIn('list_directory', verifier)
        self.assertIn('"view_file"', self.read('.gemini/config/plugins/ai-kit/agents/ai-kit-code-reviewer.md'))


class CodexTests(Base):
    def test_personal_skill_kept_and_the_block_says_which_name(self):
        mine = self.mine('.codex/skills/review/SKILL.md')
        notices = self.run_kit('codex')
        self.assertEqual(mine.read_text(encoding='utf-8'), 'mine\n')
        self.assertTrue((self.home/'.codex/skills/ai-kit-review/SKILL.md').is_file())
        self.assertIn('`review` is `ai-kit-review`', self.read('.codex/AGENTS.md'))
        self.assertTrue(any('command $review as $ai-kit-review' in n for n in notices))

    def test_renamed_skill_references_rewritten_in_other_skills(self):
        self.mine('.codex/skills/tdd/SKILL.md')
        self.run_kit('codex')
        self.assertIn('"ai-kit-tdd"', self.read('.codex/skills/implement/SKILL.md'))


class ReferenceTests(unittest.TestCase):
    def test_references_rewritten_only_where_they_name_the_skill(self):
        mapping = {'tdd': 'ai-kit-tdd', 'review': 'ai-kit-review'}
        text = 'Use `tdd`, call "tdd", the tdd skill, /review or $review; a review of tdd-like code; skills/tdd/SKILL.md'
        self.assertEqual(rename_references(text, mapping),
                         'Use `ai-kit-tdd`, call "ai-kit-tdd", the ai-kit-tdd skill, /ai-kit-review or $ai-kit-review; a review of tdd-like code; skills/tdd/SKILL.md')


if __name__ == '__main__':
    unittest.main()
