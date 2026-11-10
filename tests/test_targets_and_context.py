"""CLI targets kept by update, a removed target cleaned up, the personal context that follows the person, secrets never copied."""
import contextlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.adapters import codex
from installer.core import read_json, json_error, KitError, load_agent
from v1_profiles import apply_as  # noqa: E402

SECRET = 'api_key = abcdefghijklmnop1234'  # fake, matches the detector


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def run_kit(self, target=None, profile='general'):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch('shutil.which', return_value=None):
            notices = apply_as(profile, self.home, False, {'email': 'a@example.org', 'source': 'option'}, target)
        self.out = out.getvalue()
        return notices

    def state(self):
        return read_json(self.home/'.ai-kit/state.json')

    def settings(self):
        return read_json(self.home/'.gemini/settings.json')


class TargetTests(Base):
    def test_update_keeps_the_recorded_choice_whatever_folders_exist(self):
        self.run_kit('codex')
        (self.home/'.gemini').mkdir()
        (self.home/'.gemini/settings.json').write_text('{}', encoding='utf-8')  # an old Gemini folder
        self.run_kit()  # update: no --target
        self.assertEqual(self.state()['targets'], ['codex'])
        self.assertFalse((self.home/'.gemini/skills').exists())

    def test_removed_gemini_leaves_no_kit_reference(self):
        settings = self.home/'.gemini/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'theme': 'Dark', 'context': {'fileName': ['MINE.md']}}), encoding='utf-8')
        self.run_kit('gemini')
        self.assertIn('00_KIT.md', self.settings()['context']['fileName'])
        self.assertTrue(self.settings()['hooks'])
        self.run_kit('codex')
        current = self.settings()
        self.assertEqual(current['theme'], 'Dark')
        self.assertIn('MINE.md', current['context']['fileName'])
        for name in current['context']['fileName']:
            if name != 'MINE.md' and name[:2].isdigit():
                self.assertTrue((self.home/'.gemini'/name).is_file(), name+' is referenced but no longer exists')
        self.assertNotIn('hooks', current)
        self.assertEqual(list((self.home/'.gemini/commands').glob('*')) if (self.home/'.gemini/commands').exists() else [], [])
        self.assertEqual(self.state()['targets'], ['codex'])

    def test_every_transition_and_back(self):
        names = ['gemini', 'agy', 'codex', 'claude', 'both', 'all']
        for first, second in itertools.permutations(names, 2):
            with self.subTest(first=first, second=second):
                for path in sorted(self.home.iterdir()):
                    __import__('shutil').rmtree(path)
                self.run_kit(first)
                user = self.home/'.ai-kit/context/USER.md'
                user.write_text('Prefers French, after '+first+'\n', encoding='utf-8')
                self.run_kit(second)
                self.run_kit()  # update keeps the second choice
                self.assertEqual(self.state()['targets'], [a.NAME for a in cli.selected_adapters(second, self.home)])
                self.run_kit(first)
                active = self.home/'.ai-kit/context/USER.md'
                self.assertEqual(active.read_text(encoding='utf-8'), 'Prefers French, after '+first+'\n')
                # No managed file recorded in the state is missing, no managed reference points to a missing layer.
                for rel in self.state()['files']:
                    self.assertTrue((self.home/rel).is_file(), rel)
                if (self.home/'.gemini/settings.json').is_file():
                    for name in self.settings().get('context', {}).get('fileName', []):
                        if name[:2].isdigit() and name != 'USER.md':
                            self.assertTrue((self.home/'.gemini'/name).is_file(), name)


class PersonalContextTests(Base):
    def test_one_file_whatever_the_clis(self):
        """Gemini with A written in its copy, then Codex, then B in the file, then back to Gemini: one file all along,
        ~/.ai-kit/context/USER.md, and B in Gemini's copy."""
        self.run_kit('gemini')
        (self.home/'.gemini/USER.md').write_text('Preference A\n', encoding='utf-8')
        notices = self.run_kit('codex')
        user = self.home/'.ai-kit/context/USER.md'
        self.assertEqual(user.read_text(encoding='utf-8'), 'Preference A\n')
        self.assertTrue(any('your change is now in' in n for n in notices))
        user.write_text('Preference B\n', encoding='utf-8')
        self.run_kit()
        self.assertIn('Preference B', (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
        self.run_kit('gemini')
        self.assertEqual((self.home/'.gemini/USER.md').read_text(encoding='utf-8'), 'Preference B\n')
        self.assertFalse([p for p in (self.home/'.gemini').iterdir() if p.name.startswith('USER.md.before-')])
        self.assertIn(str(self.home.resolve()/'.ai-kit/context/USER.md'), self.out)  # resolved: Windows short names (RUNNER~1)

    def test_secret_is_never_copied_to_a_new_location(self):
        self.run_kit('gemini')
        (self.home/'.gemini/USER.md').write_text('Preference\n'+SECRET+'\n', encoding='utf-8')
        notices = self.run_kit('codex')
        self.assertNotIn(SECRET, (self.home/'.ai-kit/context/USER.md').read_text(encoding='utf-8'))
        self.assertNotIn(SECRET, (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
        self.assertTrue(any('secret' in n and 'installed' in n for n in notices))
        self.assertNotIn('abcdefghijklmnop1234', self.out)
        self.assertIn(SECRET, (self.home/'.gemini/USER.md').read_text(encoding='utf-8'))  # the edited copy is left as it is

    def test_codex_keeps_the_last_valid_copy(self):
        self.run_kit('codex')
        user = self.home/'.ai-kit/context/USER.md'
        user.write_text('Valid preference\n', encoding='utf-8')
        self.run_kit()
        user.write_text('Valid preference\n'+SECRET+'\n', encoding='utf-8')
        notices = self.run_kit()
        agents = (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('Valid preference', agents)
        self.assertNotIn('abcdefghijklmnop1234', agents)
        self.assertTrue(any('not copied into ~/.codex/AGENTS.md' in n for n in notices))
        self.assertIn('Kit configuration', self.out)  # the installation itself went through
        user.write_text('Fixed preference\n', encoding='utf-8')
        self.run_kit()
        self.assertIn('Fixed preference', (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))

    def test_rich_text_or_bad_encoding_not_copied(self):
        self.run_kit('codex')
        user = self.home/'.ai-kit/context/USER.md'
        for data in (b'{\\rtf1 hello}', 'café'.encode('latin-1')):
            user.write_bytes(data)
            notices = self.run_kit()
            self.assertTrue(any('not copied' in n for n in notices), data)


class RedactionTests(unittest.TestCase):
    def test_json_syntax_error_does_not_repeat_a_secret(self):
        text = '{\n  "token": "ghp_' + 'a'*36 + '"\n  "x": 1\n}'
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            message = json_error(Path('overrides.json'), text, exc)
        self.assertIn('line 3', message)
        self.assertNotIn('a'*36, message)

    def test_printed_errors_are_redacted(self):
        err = io.StringIO()
        with mock.patch.object(cli, 'apply', side_effect=KitError('bad value sk-' + 'b'*30)), contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as tmp:
            code = cli.main(['init', '--home', tmp, '--user', 'a@example.org'])
        self.assertEqual(code, 1)  # refused or failed
        self.assertNotIn('b'*30, err.getvalue())


class CodexApprovalTests(Base):
    def test_foreign_approval_is_never_reported_as_the_kits(self):
        self.run_kit('codex')
        config = self.home/'.codex/config.toml'
        config.write_text(config.read_text(encoding='utf-8')+'\n[hooks.state."/x/config.toml:pre_tool_use:0:0"]\ntrusted_hash = "abc"\n', encoding='utf-8')
        recorded, message = codex.hook_approval(self.home)
        self.assertTrue(recorded)
        self.assertIn('not verifiable automatically', message)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertNotIn('[OK] Codex: kit guardrails approved', out.getvalue())
        self.assertIn('not verifiable automatically', out.getvalue())

    def test_no_record_is_reported_as_not_approved(self):
        self.run_kit('codex')
        recorded, message = codex.hook_approval(self.home)
        self.assertFalse(recorded)
        self.assertIn('not yet', message)


class AgentContractTests(unittest.TestCase):
    def test_each_adapter_declares_how_it_applies_agent_tools(self):
        for adapter in cli.ADAPTERS:
            self.assertIn(adapter.AGENT_TOOLS, ('native', 'instruction', 'unavailable'), adapter.NAME)

    def test_verifier_may_run_its_checks_and_reviewers_only_read(self):
        verifier = load_agent(cli.ROOT/'agents/internal/common/verifier.md')
        reviewer = load_agent(cli.ROOT/'agents/internal/development/code-reviewer.md')
        self.assertIn('run only the commands', cli.agent_instruction(verifier))
        self.assertNotIn('run no command', cli.agent_instruction(verifier))
        self.assertIn('run no command', cli.agent_instruction(reviewer))


if __name__ == '__main__':
    unittest.main()
