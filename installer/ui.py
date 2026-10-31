"""Terminal interface of the installer: Rich shows (titles, tables, states, progress, summaries, errors), Questionary asks
(arrow-key choices, checkboxes, confirmations, validated input). Plain numbered text when they are not installed
(python -m installer from a clone) or when asked (--plain, AI_KIT_PLAIN=1). Never used without a terminal: the
non-interactive mode asks nothing. Every question raises Cancelled on Ctrl+C, Esc or end of input."""
import contextlib
import os
import sys


class Cancelled(Exception):
    """The person left a question (Ctrl+C, end of input): nothing has been applied yet."""


def libraries():
    try:
        import rich  # noqa: F401
        import questionary  # noqa: F401
    except ImportError:
        return False
    return True


def unicode_ok(stream):
    try:
        '✓✗…─│●○'.encode(getattr(stream, 'encoding', None) or 'ascii')
    except (UnicodeEncodeError, LookupError):
        return False
    return True


STATE_MARK = {'ok': ('✓', '[OK]'), 'missing': ('✗', '[--]'), 'info': ('•', '[..]'), 'check': ('!', '[!]')}


class PlainUI:
    """Numbered questions with input(), lines with print(): works in any terminal, with any encoding."""
    rich = False

    def __init__(self, out=None, ask=None):
        self.out = out or sys.stdout
        self.ask_line = ask or input

    def print(self, text=''):
        print(text, file=self.out)

    def title(self, text):
        self.print('\n'+text+'\n'+'-'*min(len(text), 60))

    def table(self, title, rows):
        """rows: (label, value, state) with state ok, missing, info or check."""
        self.print(title)
        for label, value, state in rows:
            self.print('  '+STATE_MARK[state][1]+' '+label+': '+value)

    def panel(self, title, lines):
        self.title(title)
        for line in lines:
            self.print('  '+line)

    def warn(self, text):
        self.print('[Check] '+text)

    def error(self, text):
        self.print('Error: '+text)

    def _input(self, prompt):
        try:
            return self.ask_line(prompt)
        except (EOFError, KeyboardInterrupt):
            raise Cancelled()

    def select(self, message, choices, default=None):
        """choices: (value, label). Enter keeps the default."""
        self.print(message)
        for i, (value, label) in enumerate(choices, 1):
            self.print('  '+str(i)+'. '+label+(' (default)' if value == default else ''))
        while True:
            answer = self._input('Number'+(' (Enter: default)' if default is not None else '')+': ').strip()
            if not answer and default is not None:
                return default
            if answer.isdigit() and 1 <= int(answer) <= len(choices):
                return choices[int(answer)-1][0]
            self.print('Type a number between 1 and '+str(len(choices))+'.')

    def checkbox(self, message, choices, minimum=0):
        """choices: (value, label, checked). Numbers toggle; Enter accepts."""
        checked = [value for value, _, on in choices if on]
        while True:
            self.print(message)
            for i, (value, label, _) in enumerate(choices, 1):
                self.print('  '+str(i)+'. ['+('x' if value in checked else ' ')+'] '+label)
            answer = self._input('Numbers to tick or untick, separated by spaces (Enter: accept): ').strip()
            if not answer:
                if len(checked) >= minimum:
                    return [value for value, _, _ in choices if value in checked]
                self.print('Choose at least '+str(minimum)+'.')
                continue
            for part in answer.replace(',', ' ').split():
                if part.isdigit() and 1 <= int(part) <= len(choices):
                    value = choices[int(part)-1][0]
                    if value in checked:
                        checked.remove(value)
                    else:
                        checked.append(value)

    def confirm(self, message, default=False):
        answer = self._input(message+(' [Y/n] ' if default else ' [y/N] ')).strip().lower()
        return default if not answer else answer in ('y', 'yes', 'o', 'oui')

    def text(self, message, default='', validate=None):
        while True:
            answer = self._input(message+(' ['+default+']' if default else '')+': ').strip() or default
            problem = validate(answer) if validate else None
            if not problem:
                return answer
            self.print(problem)

    def pause(self, message):
        self._input(message)

    @contextlib.contextmanager
    def progress(self, label):
        """A callback(step, done, total) for apply(): one line per step, as the files are really written."""
        seen = set()
        names = {'backup': 'Backing up', 'write': 'Writing', 'remove': 'Removing'}
        def step(name, done, total):
            if name not in seen:
                seen.add(name)
                self.print('  '+names.get(name, name)+' '+str(total)+' files…')
        self.print(label)
        yield step


class RichUI(PlainUI):
    """Rich for display, Questionary for questions. input and output: prompt_toolkit objects, for tests."""
    rich = True

    def __init__(self, out=None, input=None, output=None, width=None):
        from rich.console import Console
        import questionary
        self.out = out or sys.stdout
        self.unicode = unicode_ok(self.out)
        # Rich follows NO_COLOR and TERM=dumb by itself; a redirected output gets no colour codes.
        self.console = Console(file=self.out, highlight=False, width=width, emoji=False, safe_box=True)
        self.q = questionary
        self.io = {k: v for k, v in (('input', input), ('output', output)) if v is not None}
        if not self.unicode:
            import questionary.prompts.common as common
            common.INDICATOR_SELECTED, common.INDICATOR_UNSELECTED = '[x]', '[ ]'
        self.pointer = '»' if self.unicode else '>'

    def print(self, text=''):
        self.console.print(text, markup=False)

    def title(self, text):
        from rich.rule import Rule
        self.console.print()
        self.console.print(Rule(text, style='bold', characters='─' if self.unicode else '-'))

    def table(self, title, rows):
        from rich.table import Table
        from rich import box
        table = Table(title=title, title_justify='left', box=box.SIMPLE if self.unicode else box.ASCII, show_header=False, expand=False)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=False)
        table.add_column(overflow='fold')
        styles = {'ok': 'green', 'missing': 'yellow', 'info': 'cyan', 'check': 'red'}
        for label, value, state in rows:
            mark = STATE_MARK[state][0 if self.unicode else 1]
            table.add_row('['+styles[state]+']'+mark+'[/]', label, value)
        self.console.print(table)

    def panel(self, title, lines):
        from rich.panel import Panel
        from rich.text import Text
        from rich import box
        self.console.print(Panel(Text('\n'.join(lines)), title=title, title_align='left', box=box.ROUNDED if self.unicode else box.ASCII, expand=False))

    def warn(self, text):
        self.console.print('[yellow]'+('!' if self.unicode else '[Check]')+'[/] ', end='')
        self.console.print(text, markup=False)

    def error(self, text):
        self.console.print('[bold red]Error:[/] ', end='')
        self.console.print(text, markup=False)

    def _ask(self, question):
        try:
            answer = question.unsafe_ask()
        except (KeyboardInterrupt, EOFError):
            raise Cancelled()
        if answer is None:
            raise Cancelled()
        return answer

    def select(self, message, choices, default=None):
        options = [self.q.Choice(label, value=value) for value, label in choices]
        start = next((o for o in options if o.value == default), None)
        return self._ask(self.q.select(message, choices=options, default=start, pointer=self.pointer, use_shortcuts=False,
                                       instruction='(arrows, Enter)', **self.io))

    def checkbox(self, message, choices, minimum=0):
        options = [self.q.Choice(label, value=value, checked=on) for value, label, on in choices]
        def enough(selected):
            return True if len(selected) >= minimum else 'Choose at least '+str(minimum)+'.'
        return self._ask(self.q.checkbox(message, choices=options, validate=enough, pointer=self.pointer,
                                         instruction='(arrows, Space to tick, Enter to accept)', **self.io))

    def confirm(self, message, default=False):
        return self._ask(self.q.confirm(message, default=default, **self.io))

    def text(self, message, default='', validate=None):
        def check(value):
            problem = validate(value.strip()) if validate else None
            return problem or True
        return self._ask(self.q.text(message, default=default, validate=check, **self.io)).strip()

    def pause(self, message):
        self._ask(self.q.text(message, **self.io))

    @contextlib.contextmanager
    def progress(self, label):
        from rich.progress import Progress, BarColumn, MofNCompleteColumn, TextColumn
        names = {'backup': 'Backing up', 'write': 'Writing', 'remove': 'Removing'}
        columns = [TextColumn('{task.description}'), BarColumn(), MofNCompleteColumn()]
        with Progress(*columns, console=self.console, transient=False) as bar:
            tasks = {}
            def step(name, done, total):
                if name not in tasks:
                    tasks[name] = bar.add_task(names.get(name, name), total=total)
                bar.update(tasks[name], completed=done)
            self.console.print(label)
            yield step


def make_ui(plain=False):
    """The richest interface this terminal and this Python allow."""
    if plain or os.environ.get('AI_KIT_PLAIN') == '1' or not libraries():
        return PlainUI()
    return RichUI()
