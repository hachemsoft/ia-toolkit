"""Guided installer: Questionary questions driven by real keystrokes, Rich output in narrow, colourless or ASCII-only
terminals, and the whole flow (first run, review, back, cancel, menu, uninstall, billed check) scripted in plain mode.
Nothing is applied before Install; Ctrl+C, end of input or an interface error leaves the configuration as it was."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from installer import cli, wizard
from installer.core import read_json
from installer.ui import Cancelled, PlainUI, libraries

ANSI = re.compile(r'\x1b\[')


class Script:
    """Answers typed one after the other; end of input when there are no more (like Ctrl+D)."""
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError()
        return self.answers.pop(0)


def plain(*answers):
    out = io.StringIO()
    script = Script(*answers)
    return PlainUI(out=out, ask=script), out, script


@unittest.skipUnless(libraries(), 'rich and questionary not installed (pip install -r packaging/runtime.txt)')
class RichComponentTests(unittest.TestCase):
    def ask(self, keys, question, *args, **kwargs):
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from installer.ui import RichUI
        with create_pipe_input() as pipe:
            pipe.send_text(keys)
            ui = RichUI(out=io.StringIO(), input=pipe, output=DummyOutput())
            return getattr(ui, question)(*args, **kwargs)

    def test_select_with_arrow_keys(self):
        choices = [('a', 'First'), ('b', 'Second'), ('c', 'Third')]
        self.assertEqual(self.ask('\x1b[B\r', 'select', 'Pick', choices, 'a'), 'b')
        self.assertEqual(self.ask('\r', 'select', 'Pick', choices, 'c'), 'c')

    def test_checkbox_space_toggles_and_minimum_is_enforced(self):
        choices = [('gemini', 'Gemini', True), ('agy', 'agy', False), ('codex', 'Codex', False)]
        self.assertEqual(self.ask('\x1b[B \x1b[B \r', 'checkbox', 'CLIs', choices, 1), ['gemini', 'agy', 'codex'])
        # Unticking everything is refused while minimum is 1; ticking one again is accepted.
        self.assertEqual(self.ask(' \r\x1b[B \r', 'checkbox', 'CLIs', choices, 1), ['agy'])

    def test_confirm_and_validated_text(self):
        self.assertTrue(self.ask('y', 'confirm', 'Sure?'))
        valid = lambda v: None if '@' in v else 'This is not an email address.'
        self.assertEqual(self.ask('bad\r'+'\x7f'*3+'a@example.org\r', 'text', 'Email', '', valid), 'a@example.org')

    def test_ctrl_c_and_end_of_input_cancel(self):
        with self.assertRaises(Cancelled):
            self.ask('\x03', 'select', 'Pick', [('a', 'A')], 'a')
        with self.assertRaises(Cancelled):
            self.ask('\x04', 'text', 'Email')

    def test_narrow_colourless_output(self):
        from installer.ui import RichUI
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'NO_COLOR': '1'}):
            ui = RichUI(out=out, width=40)
            ui.title('AI Kit 0.34.0')
            ui.table('This workstation', [('Gemini CLI', 'not found on this workstation, configuration prepared', 'missing')])
            ui.panel('Before installing', ['Files: 120 new, 3 updated, 0 removed (~/.gemini 80, ~/.codex 43)'])
        text = out.getvalue()
        self.assertNotRegex(text, ANSI)
        self.assertTrue(all(len(line) <= 40 for line in text.splitlines()), text)
        self.assertIn('not found', text)

    def test_ascii_only_terminal(self):
        from installer.ui import RichUI
        raw = io.BytesIO()
        out = io.TextIOWrapper(raw, encoding='ascii', errors='strict')
        ui = RichUI(out=out, width=60)
        ui.table('This workstation', [('Python', '3.9', 'ok'), ('Codex CLI', 'not found', 'missing')])
        ui.panel('Result', ['Kit configuration: installed.'])
        out.flush()
        text = raw.getvalue().decode('ascii')
        self.assertIn('[OK]', text)
        self.assertIn('[--]', text)


class WizardFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for patcher in (mock.patch('shutil.which', return_value=None), mock.patch.object(cli, 'detect_identity', return_value={})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_wizard(self, *answers, setup=False):
        ui, out, script = plain(*answers)
        with contextlib.redirect_stdout(io.StringIO()):
            code = wizard.start(ui, self.home, setup=setup)
        return code, out.getvalue(), script

    def state(self):
        return read_json(self.home/'.ai-kit/state.json')

    # First run: CLIs (Enter: proposed), profile (Enter: General), email, keep the profile, review → Install, context later.
    FIRST = ('', '', 'a@example.org', '', '', 'n')

    def test_first_run_installs_after_review_and_never_calls_the_model(self):
        code, out, _ = self.run_wizard(*self.FIRST)
        self.assertEqual(code, 0, out)
        self.assertIn('This workstation', out)
        self.assertIn('not checked', out)
        self.assertIn('Before installing', out)
        self.assertIn('No call to the model', out)
        self.assertIn('Result', out)
        self.assertEqual(self.state()['profile'], 'general')
        self.assertEqual(self.state()['user']['email'], 'a@example.org')
        self.assertEqual(self.state()['targets'], ['gemini'])

    def test_cancel_at_review_writes_nothing(self):
        code, out, _ = self.run_wizard('', '', 'a@example.org', '', '3')
        self.assertEqual(code, 1)
        self.assertIn('was not changed', out)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        self.assertFalse((self.home/'.gemini').exists())

    def test_end_of_input_midway_writes_nothing(self):
        code, out, _ = self.run_wizard('', '')
        self.assertEqual(code, 130)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        self.assertFalse((self.home/'.gemini').exists())

    def test_back_keeps_the_answers_and_changes_the_profile(self):
        profiles = [p for p, _, _ in wizard.profiles()]
        devops = str(profiles.index('devops')+1)
        code, out, _ = self.run_wizard('', '', 'a@example.org', '', '2', '', devops, '', '', '', 'n')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()['profile'], 'devops')
        self.assertEqual(out.count('Before installing'), 2)

    def test_customized_choices_are_written_only_on_install(self):
        catalog = read_json(cli.ROOT/'skills/catalog.json')
        playbooks = [s for s, e in catalog.items() if e.get('category') == 'domain' and not e.get('replaced_by')]
        pick = str(playbooks.index('python-js-change')+1)
        overrides = self.home/'.ai-kit/overrides.json'
        overrides.parent.mkdir()
        overrides.write_text(json.dumps({'_mine': 'kept', 'frictions': 'off'}), encoding='utf-8')
        # Adjust: tick python-js-change (its number, then Enter), keep tools, commands and agents, then cancel: nothing written.
        self.run_wizard('', '', 'a@example.org', '2', pick, '', '', '', '', '3')
        self.assertEqual(json.loads(overrides.read_text(encoding='utf-8')), {'_mine': 'kept', 'frictions': 'off'})
        code, out, _ = self.run_wizard('', '', 'a@example.org', '2', pick, '', '', '', '', '1', 'n')
        self.assertEqual(code, 0, out)
        saved = json.loads(overrides.read_text(encoding='utf-8'))
        self.assertEqual(saved['_mine'], 'kept')
        self.assertEqual(saved['frictions'], 'off')
        self.assertEqual(saved['extra_skills'], ['python-js-change'])
        self.assertIn('python-js-change', self.state()['installed']['skills'])
        self.assertIn('Not installed here', (self.home/'.gemini/skills/python-js-change/SKILL.md').read_text(encoding='utf-8'))

    def test_a_choice_turned_off_is_not_ticked_again(self):
        self.run_wizard(*self.FIRST)
        overrides = self.home/'.ai-kit/overrides.json'
        data = json.loads(overrides.read_text(encoding='utf-8'))
        data['disabled_commands'] = ['retro']
        overrides.write_text(json.dumps(data), encoding='utf-8')
        # Adjust, then accept every list as shown: retro appears unticked and stays off.
        ui, out, _ = plain('2', '', '', '', '')
        with contextlib.redirect_stdout(io.StringIO()):
            choices = wizard.customize(ui, self.home, 'general')
        self.assertIn('retro', choices['disabled_commands'])
        self.assertRegex(out.getvalue(), r'\[ \] /retro')

    def test_menu_update_keeps_recorded_choices(self):
        cli_out = io.StringIO()
        with contextlib.redirect_stdout(cli_out):
            cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'codex')
        code, out, script = self.run_wizard('1')
        self.assertEqual(code, 0, out)
        self.assertIn('What do you want to do?', out)
        self.assertEqual(self.state()['targets'], ['codex'])
        self.assertIn('Result', out)

    def test_menu_change_choices_proposes_the_recorded_clis(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'codex')
        code, out, _ = self.run_wizard('2', '', '', '', '', '1')
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r'\[x\] Codex CLI')
        self.assertRegex(out, r'\[ \] Gemini CLI')

    def test_billed_check_needs_its_own_confirmation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'gemini')
        with mock.patch.object(cli, 'live_checks') as live, mock.patch.dict(os.environ, {'AI_KIT_NO_LIVE': ''}):
            code, out, _ = self.run_wizard('6', 'n')
        live.assert_not_called()
        self.assertIn('may bill', out)
        with mock.patch.object(cli, 'live_checks') as live, mock.patch.dict(os.environ, {'AI_KIT_NO_LIVE': '1'}):
            code, out, _ = self.run_wizard('6')
        live.assert_not_called()
        self.assertEqual(code, 2)

    def test_menu_uninstall_asks_first(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('general', self.home, False, None, 'gemini')
        code, out, _ = self.run_wizard('5', 'n')
        self.assertTrue((self.home/'.ai-kit/state.json').exists())
        code, out, _ = self.run_wizard('5', 'y')
        self.assertEqual(code, 0, out)
        self.assertFalse((self.home/'.ai-kit/state.json').exists())
        self.assertTrue((self.home/'.gemini/30_USER.md').exists())

    def test_interface_error_during_the_writes_leaves_nothing_half_done(self):
        def broken(step, done, total):
            if step == 'write' and done == 5:
                raise KeyboardInterrupt()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            cli.apply('general', self.home, False, None, 'gemini', progress=broken)
        written = [p for p in self.home.rglob('*') if p.is_file() and '/backups/' not in p.as_posix()]
        self.assertEqual(written, [])


class EntryPointTests(unittest.TestCase):
    def test_no_action_without_a_terminal_asks_nothing(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch('builtins.input', side_effect=AssertionError('no question without a terminal')):
            code = cli.main(['--home', tmp])
        self.assertEqual(code, 2)
        self.assertIn('no terminal', err.getvalue())

    def test_update_with_arguments_never_opens_the_questions(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini', '--home', tmp]), 0)
            with mock.patch.object(cli, 'interactive', return_value=True), mock.patch('installer.wizard.start') as start, \
                    mock.patch('builtins.input', side_effect=AssertionError('no question for update')):
                self.assertEqual(cli.main(['update', '--home', tmp]), 0)
            start.assert_not_called()

    def test_plain_mode_is_chosen_without_libraries_or_on_request(self):
        from installer import ui
        with mock.patch.object(ui, 'libraries', return_value=False):
            self.assertFalse(ui.make_ui().rich)
        self.assertFalse(ui.make_ui(plain=True).rich)
        with mock.patch.dict(os.environ, {'AI_KIT_PLAIN': '1'}):
            self.assertFalse(ui.make_ui().rich)


if __name__ == '__main__':
    unittest.main()
