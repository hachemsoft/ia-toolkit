"""0.38: the personal context is one short file, filled by three quick questions in the installer (no model) and by the
/me interview in the CLI. The kit only writes it while it is still the file it created."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.core import KitError, load_commands


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini')
        self.user_file = self.home/'.gemini/30_USER.md'


class QuickContextTests(Base):
    def test_defaults_are_short_answers_that_disagree_when_needed(self):
        text = self.user_file.read_text(encoding='utf-8')
        self.assertIn('Reply in the language I write in.', text)
        self.assertIn('Short answer first', text)
        self.assertIn('say so plainly with the evidence before acting', text)  # always there: a profile makes assistants agree too easily
        self.assertIn('/me', text)
        self.assertNotIn('{', text)

    def test_answers_and_role_written_while_the_file_is_the_kits(self):
        written = cli.write_quick_context(self.home, {'language': 'fr', 'length': 'detailed', 'autonomy': 'ask'}, 'Data engineer,\nmigrating to FastAPI')
        text = written.read_text(encoding='utf-8')
        self.assertIn('Reply in French; code, comments and commit messages in English.', text)
        self.assertIn('Explain the why and the alternatives', text)
        self.assertIn('Ask before acting', text)
        self.assertIn('- Data engineer, migrating to FastAPI', text)
        self.assertNotIn(cli.ROLE_PLACEHOLDER, text)

    def test_never_over_the_persons_own_text(self):
        self.user_file.write_text('# Mine\n- Be brief.\n', encoding='utf-8')
        self.assertIsNone(cli.write_quick_context(self.home, {'length': 'detailed'}))
        self.assertEqual(self.user_file.read_text(encoding='utf-8'), '# Mine\n- Be brief.\n')

    def test_a_secret_is_never_written(self):
        with self.assertRaises(KitError):
            cli.write_quick_context(self.home, {}, 'token=abcdef123456')

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
                       'question tool', 'A topic you love to dig into, even as a beginner?', 'Reviews simpler, more teaching',
                       'By situation', 'no opinion about tools', 'At most 20 lines', 'before and after', 'With their agreement only',
                       'run update first'):
            self.assertIn(needle, prompt)


if __name__ == '__main__':
    unittest.main()
