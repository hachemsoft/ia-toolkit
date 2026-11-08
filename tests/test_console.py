"""Colour for update, doctor and usage: the lines keep their exact text, only their style changes, through one output
layer installed at the edge (installer/console.py). A redirected or plain output carries no colour code at all."""
import contextlib
import io
import re
import unittest

from installer import console
from installer.ui import libraries

ANSI = re.compile(r'\x1b\[[0-9;]*m')


class StyledOutputTests(unittest.TestCase):
    def styled(self, text, **kwargs):
        from rich.console import Console
        out = io.StringIO()
        rich = Console(file=out, force_terminal=True, color_system='standard', width=200, highlight=False, emoji=False)
        with console.styled_output(rich=rich):
            print(text, **kwargs)
        return out.getvalue()

    @unittest.skipUnless(libraries(), 'rich not installed (pip install -r packaging/runtime.txt)')
    def test_prefixes_get_a_colour_and_the_text_stays_the_same(self):
        for line, colour in (('[OK] Python 3.11 minimum', '32'), ('[Check] Kit installation; run setup if missing.', '33'),
                             ('[Info] Updated: skill tdd 1.0.0 → 1.1.0.', '36'), ('Error: Kit not installed: run setup.', '31')):
            out = self.styled(line)
            self.assertRegex(out, r'\x1b\[[0-9;]*'+colour+'m', line)
            self.assertEqual(ANSI.sub('', out), line+'\n')
        for heading in ('Summary', 'Details', 'Next step: open a terminal in your repo'):
            out = self.styled(heading)
            self.assertIn('\x1b[1m', out, heading)
            self.assertEqual(ANSI.sub('', out), heading+'\n')
        plain = 'Profile: general | 17 skills'
        self.assertEqual(self.styled(plain), plain+'\n')

    @unittest.skipUnless(libraries(), 'rich not installed')
    def test_the_binary_buffer_is_the_real_streams(self):
        # prompt_toolkit writes to sys.stdout.buffer: a question asked under this layer crashed on a text attribute of that name.
        from rich.console import Console
        real = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
        rich = Console(file=real, force_terminal=True, color_system='standard', width=200)
        self.assertIs(console.StyledOutput(rich, real).buffer, real.buffer)

    def test_partial_writes_and_markup_characters_are_safe(self):
        self.assertEqual(ANSI.sub('', self.styled('[OK] a [bold]b[/] ' + '\n'.join(['x', '[Check] y']))), '[OK] a [bold]b[/] x\n[Check] y\n')
        from rich.console import Console
        out = io.StringIO()
        rich = Console(file=out, force_terminal=True, color_system='standard', width=200, highlight=False, emoji=False)
        with console.styled_output(rich=rich):
            print('[Info] no newline yet', end='')
        self.assertEqual(ANSI.sub('', out.getvalue()), '[Info] no newline yet')  # flushed unstyled when the layer leaves

    def test_redirected_or_plain_output_has_no_colour_code(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), console.styled_output():
            print('[OK] Python 3.11 minimum')
            print('Error: x')
        self.assertEqual(out.getvalue(), '[OK] Python 3.11 minimum\nError: x\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), console.styled_output(plain=True):
            print('[OK] Python 3.11 minimum')
        self.assertEqual(out.getvalue(), '[OK] Python 3.11 minimum\n')


if __name__ == '__main__':
    unittest.main()
