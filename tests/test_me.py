"""0.38: the personal context is one short file, filled by three quick questions in the installer (no model) and by the
/me interview in the CLI. The kit only writes it while it is still the file it created."""
import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import load_commands

QUESTIONS = Path(__file__).resolve().parents[1]/'templates/me-questions.md'


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply(self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini')
        self.user_file = self.home/'.ai-kit/context/USER.md'


class QuickContextTests(Base):
    def test_defaults_are_short_answers_that_disagree_when_needed(self):
        text = self.user_file.read_text(encoding='utf-8')
        self.assertIn('Reply in the language I write in.', text)
        self.assertIn('Short answer first', text)
        self.assertIn('say so plainly with the evidence before acting', text)  # always there: a profile makes assistants agree too easily
        self.assertIn('/me', text)
        self.assertNotIn('{', text)

    def test_install_writes_the_questions_of_me(self):
        self.assertEqual((self.home/'.ai-kit/me/questions.md').read_bytes(), QUESTIONS.read_bytes())

    def test_short_enough_to_be_followed(self):
        # Studies of context files: few, specific instructions are followed; the template stays small.
        instructions = [line for line in self.user_file.read_text(encoding='utf-8').splitlines() if line.startswith('- ')]
        self.assertLessEqual(len(instructions), 6)


class MeCommandTests(unittest.TestCase):
    def test_me_interviews_then_writes_only_with_agreement(self):
        me = next(c for c in load_commands() if c['name'] == 'me')
        prompt = me['prompt']
        # Simple questions (feedback of a first real run): short, everyday words, examples in the options, small batches.
        for needle in ('Facts first, never asked', 'twelve words at most', 'a concrete example after a dash', 'at most four',
                       'question tool', 'By situation', 'no opinion about tools', 'At most 20 lines', 'before and after', 'With their agreement only',
                       'run ai-kit sync --offline first'):
            self.assertIn(needle, prompt)

    def test_me_yields_a_coherent_file_beside_the_kit(self):
        # Feedback of a real run: Q5 offered "ask a question" against the forced "say so plainly" line, Q6 and the Report
        # section gave two answers for one /review, Q4 competed with the kit's ceremony, Q7 produced lines the agent follows anyway.
        prompt = next(c for c in load_commands() if c['name'] == 'me')['prompt']
        for needle in ('that 00_KIT.md or 10_CORE.md already covers', 'replay three situations', 'ask which one wins'):
            self.assertIn(needle, prompt)
        for needle in ('For a small, obvious fix, I…', 'If I am not sure what you mean, I…',
                       'Last time an assistant annoyed you, what did it do?',
                       'C as two or three options, your pick first, on top of A or B for design choices'):
            self.assertIn(needle, QUESTIONS.read_text(encoding='utf-8'))
        for gone in ('If I think your idea is wrong', 'B. Ask you a question', 'What annoys you in an assistant?'):
            self.assertNotIn(gone, prompt + QUESTIONS.read_text(encoding='utf-8'))

    def test_questions_live_in_a_file_the_command_reads(self):
        # The question list left the prompt (4000-character limit of a command); it costs nothing until /me runs.
        prompt = next(c for c in load_commands() if c['name'] == 'me')['prompt']
        self.assertIn('~/.ai-kit/me/questions.md', prompt)
        self.assertNotIn('Which answer do you prefer?', prompt)
        questions = QUESTIONS.read_text(encoding='utf-8')
        for needle in ('A topic you love to dig into, even as a beginner?', 'Reviews simpler, more teaching',
                       'Bad news: how do you want it?', 'What makes you trust an answer?', 'How do you usually decide?'):
            self.assertIn(needle, questions)
        self.assertEqual(len(re.findall(r'^ *\d+\. "', questions, re.M)), 12)


if __name__ == '__main__':
    unittest.main()
