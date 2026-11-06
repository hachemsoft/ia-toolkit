"""Colour for the command-line actions (update, doctor, usage, setup with options), added at the edge: every line keeps
its exact text, the layer only styles it by its prefix ([OK], [Check], [Info], Error:) or heading (Summary, Details,
Next step). Nothing changes for a redirected output, a plain terminal (NO_COLOR, TERM=dumb, --plain, AI_KIT_PLAIN=1) or
without Rich: the layer is not installed, or Rich itself writes no colour code. The guided screens have their own UI."""
import contextlib
import os
import sys

PREFIXES = (('[OK]', 'green'), ('[Check]', 'bold yellow'), ('[Info]', 'cyan'), ('Error:', 'bold red'))
HEADINGS = ('Summary', 'Details')
LEADS = (('Next step:', 'bold'),)


def style_of(line):
    """(styled head, style, rest of the line) for a line the layer colours, or None to leave it as it is."""
    stripped = line.lstrip()
    indent = line[:len(line)-len(stripped)]
    if stripped.rstrip() in HEADINGS:
        return indent, stripped, 'bold', ''
    for prefix, style in PREFIXES+LEADS:
        if stripped.startswith(prefix):
            return indent, prefix, style, stripped[len(prefix):]
    return None


class StyledOutput:
    """A text stream in place of sys.stdout: lines go through a Rich console with a style, partial writes wait for
    their end of line, everything else (encoding, fileno, isatty, the binary buffer an interface library writes to) is the
    real stream's."""
    def __init__(self, rich, stream):
        from rich.text import Text
        self.rich, self.stream, self.pending, self.Text = rich, stream, '', Text

    def write(self, data):
        self.pending += data
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            self.emit(line, newline=True)
        return len(data)

    def emit(self, line, newline):
        found = style_of(line) if newline else None
        if found:
            indent, head, style, rest = found
            text = self.Text(indent)
            text.append(head, style=style)
            text.append(rest, style='red' if head == 'Error:' else None)
            self.rich.print(text, end='\n', soft_wrap=True)
        else:
            self.stream.write(line+('\n' if newline else ''))

    def flush(self):
        if self.pending:
            self.stream.write(self.pending)
            self.pending = ''
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextlib.contextmanager
def styled_output(plain=False, rich=None):
    """Installs the layer on sys.stdout for the block, when colour makes sense here; otherwise a no-op."""
    stream = sys.stdout if rich is None else rich.file
    if rich is None:
        plain = plain or os.environ.get('AI_KIT_PLAIN') == '1' or not hasattr(stream, 'isatty') or not stream.isatty()
        if not plain:
            try:
                from rich.console import Console
                rich = Console(file=stream, highlight=False, emoji=False, safe_box=True)
            except ImportError:
                rich = None
        if rich is None or not rich.is_terminal:
            yield
            return
    layer = StyledOutput(rich, stream)
    sys.stdout = layer
    try:
        yield
    finally:
        layer.flush()
        sys.stdout = stream
