"""Messages a person meets when installing or updating, each one saying what to do next."""
import contextlib, io, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from installer import cli
from installer.adapters import claude, codex
from installer.core import KitError, read_json, split_block
from installer.status import status
from presets import apply_as  # noqa: E402


class InstallMessageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            apply_as('general', self.home, False, **kwargs)

    def test_block_of_another_kit_version_is_named_as_such(self):
        # The start marker's words changed between versions: the block is whole, written by another version, not damaged.
        for markers, start, end in ((codex.CODEX_MD, '<!-- ai-kit:start : other words -->', '<!-- ai-kit:end -->'),
                                    (claude.CLAUDE_MD, '<!-- ai-kit:start : other words -->', '<!-- ai-kit:end -->'),
                                    (codex.CODEX_TOML, '# >>> ai-kit : other words >>>', '# <<< ai-kit <<<')):
            with self.assertRaises(KitError) as caught:
                split_block('mine\n'+start+'\nkit text\n'+end+'\nmine too\n', markers, '~/file')
            message = str(caught.exception)
            self.assertIn('another version of the kit', message)
            self.assertIn('~/file', message)
            self.assertIn('remove', message)
            self.assertNotIn('damaged', message)

    def test_damaged_markers_keep_their_message(self):
        start, end = codex.CODEX_MD
        for text in (start+'\nkit\n', 'kit\n'+end+'\n', start+'\n'+start+'\nkit\n'+end+'\n', end+'\nkit\n'+start+'\n'):
            with self.assertRaises(KitError) as caught:
                split_block(text, codex.CODEX_MD, '~/file')
            self.assertIn('Kit markers damaged', str(caught.exception))
        self.assertEqual(split_block('mine\n', codex.CODEX_MD, '~/file'), ('mine\n', None, ''))

    def test_sync_without_a_core_source_says_what_works(self):
        self.install(user={'email': 'first.last@example.com', 'source': 'option'})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch.dict('os.environ', {'AI_KIT_NO_LIVE': '1'}):
            code = cli.main(['--home', str(self.home), '--plain', 'sync'])
        self.assertEqual(code, 1)
        self.assertIn('No Core source', err.getvalue())
        self.assertIn('ai-kit init', err.getvalue())
        self.assertIn('ai-kit sync --offline', err.getvalue())

    def test_init_proposes_the_recorded_identity(self):
        state = {'user': {'email': 'first.last@example.com', 'source': 'input'}}
        args = SimpleNamespace(user=None, action='init')
        with mock.patch.object(cli, 'detect_identity', side_effect=AssertionError('detected again')):
            with mock.patch.object(cli, 'interactive', return_value=True), mock.patch('builtins.input', return_value='') as asked:
                self.assertIsNone(cli.resolve_identity(args, self.home, state))  # Enter keeps the recorded identity
            self.assertIn('first.last@example.com', asked.call_args[0][0])
            with mock.patch.object(cli, 'interactive', return_value=True), mock.patch('builtins.input', return_value='other@example.com'):
                self.assertEqual(cli.resolve_identity(args, self.home, state), {'email': 'other@example.com', 'source': 'input'})
            with mock.patch.object(cli, 'interactive', return_value=True), mock.patch('builtins.input', return_value='not an email'):
                with self.assertRaises(KitError):
                    cli.resolve_identity(args, self.home, state)
            out = io.StringIO()
            with mock.patch.object(cli, 'interactive', return_value=False), contextlib.redirect_stdout(out):
                self.assertIsNone(cli.resolve_identity(args, self.home, state))  # no terminal: kept, without a question
            self.assertEqual(out.getvalue(), '')

    def test_init_keeps_the_recorded_identity_when_enter_is_pressed(self):
        self.install(user={'email': 'first.last@example.com', 'source': 'option'})
        self.install(user=None)
        self.assertEqual(read_json(self.home/'.ai-kit/state.json')['user']['email'], 'first.last@example.com')

    def status_text(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status(self.home)
        return out.getvalue()

    def test_status_names_a_cli_present_but_not_configured(self):
        from installer.adapters import ADAPTERS
        by_name = {a.NAME: a for a in ADAPTERS}
        present = lambda *names: [mock.patch.object(a, 'present', return_value=a.NAME in names) for a in ADAPTERS]  # noqa: E731
        self.install(target=['gemini'])
        with contextlib.ExitStack() as stack:
            for patch in present('gemini', 'claude'):
                stack.enter_context(patch)
            text = self.status_text()
        self.assertIn('CLIs: gemini\n', text)
        line = next(line for line in text.split('\n') if 'not configured' in line)
        self.assertIn(by_name['claude'].LABEL, line)
        self.assertNotIn(by_name['gemini'].LABEL, line)
        self.assertNotIn(by_name['codex'].LABEL, line)
        self.assertIn('ai-kit init --target auto', line)
        with contextlib.ExitStack() as stack:
            for patch in present('gemini'):
                stack.enter_context(patch)
            self.assertNotIn('not configured', self.status_text())


if __name__ == '__main__':
    unittest.main()
