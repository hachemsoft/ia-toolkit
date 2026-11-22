#!/usr/bin/env python3
"""Kit guardrail (before a tool call): refuses a write tool aimed at the configuration of the kit or of a CLI (the path is
exact), and the kit's own commands that change the installation or bill a model call. It reads no other shell command:
what a command changes is reported by the integrity check after the tool call and at session start (ADR 0030).
Output: JSON {"decision": "deny", "reason": ...} or {} ({"decision": "ask"} for agy).
"""
import itertools
import json
import os
import re
import sys
import time

# --- Configuration -----------------------------------------------------------------------------------------------

# Configuration of the kit and of the CLIs, always protected: an agent must not be able to switch off its own guardrails.
# Relative to the home folder; a trailing / protects a whole folder. ~/.ai-kit/learning/ (personal /learn progress) and
# ~/.ai-kit/context/USER.md (the person's own file) stay writable. Every file the kit installed (state.json) is protected too.
CONFIG_PATHS = ('.ai-kit/aikit.toml', '.ai-kit/lock.toml', '.ai-kit/engine.lock', '.ai-kit/sources/', '.ai-kit/state.json', '.ai-kit/hooks/', '.ai-kit/bin/', '.ai-kit/backups/',
                '.ai-kit/runtime/', '.ai-kit/schemas/', '.ai-kit/context/00_', '.ai-kit/context/10_', '.ai-kit/context/20_',
                # the news the session hook shows (their text enters the next session) and its marker
                '.ai-kit/news/', '.ai-kit/news.json', '.ai-kit/integrity.json',
                # the questions /me follows as instructions
                '.ai-kit/me/',
                '.gemini/00_', '.gemini/10_', '.gemini/20_', '.gemini/settings.json', '.gemini/.env', '.gemini/config/plugins/ai-kit/',
                '.gemini/antigravity-cli/settings.json',  # agy's permissions: the person's answers, never the agent's
                '.codex/config.toml', '.codex/AGENTS.md', '.codex/AGENTS.override.md', '.codex/ai-kit/', '.claude/settings.json', '.claude/settings.local.json', '.claude/CLAUDE.md', '.claude/agents/ai-kit-',
                '.claude.json',
                # git's own configuration can redirect the kit's next fetch (url.insteadOf) or run a program (core.fsmonitor) (0.51.1).
                '.gitconfig', '.config/git/config')

# Configuration of a repo, protected in every repo: a project setting can turn hooks off or change the environment the
# guardrails read (a .env setting the kit's variables is refused through its content).
REPO_CONFIG = ('.claude/settings.json', '.claude/settings.local.json',
               '.gemini/settings.json', '.gemini/.env', '.codex/config.toml')

KIT_VARIABLES = re.compile(r'^\s*(export\s+)?(AI_KIT_[A-Z_]*|DBT_TARGET)\s*=', re.M | re.I)  # Windows reads a variable's name without case

DOTENV_BLOCKED = 'Blocked by the kit: a .env file the agent writes must not set the kit\'s variables (AI_KIT_*) or DBT_TARGET.'

def repo_dirs(start):
    """Folders from start up to the repo root (the first folder that contains .git), where a repo's CLI settings live.
    A monorepo started from a subfolder keeps the root's settings protected."""
    dirs, current = [], os.path.abspath(start)
    while True:
        dirs.append(current)
        if os.path.exists(os.path.join(current, '.git')):
            return dirs
        parent = os.path.dirname(current)
        if parent == current:
            return [os.path.abspath(start)]
        current = parent

def deny_output(payload, reason):
    """Refusal in the shape the CLI expects: Codex and the CLIs using the PreToolUse format validate their output strictly."""
    if payload.get('hook_event_name') == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
    return {'decision': 'deny', 'reason': reason}

def as_text(value):
    """A command can arrive as a string or as a list of arguments (Codex: ["bash", "-lc", "..."])."""
    if isinstance(value, list):
        return ' '.join(str(v) for v in value)
    return str(value or '')

PATCH_HEADER = re.compile(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$|^\+\+\+ b/(.+)$', re.M)

def target_paths(tool, args):
    """Files a tool call will write: a direct path (Gemini, agy, Claude Code's Write/Edit/MultiEdit/NotebookEdit) or the headers of a patch (Codex apply_patch)."""
    if not isinstance(args, dict):
        args = {'input': args}
    for key in ('file_path', 'notebook_path', 'TargetFile', 'AbsolutePath', 'FilePath', 'path', 'Path'):
        if isinstance(args.get(key), str) and args.get(key):
            return [args[key]]
    if 'patch' in tool.lower():
        found = []
        for value in args.values():
            for match in PATCH_HEADER.finditer(as_text(value)):
                found.append(next(g for g in match.groups() if g).strip())
        return found
    return []

def patch_additions(text):
    """{file: the lines a patch adds to it} (Codex apply_patch, a unified diff): what a patch removes is not written."""
    found, current = {}, []
    for line in text.split('\n'):
        match = PATCH_HEADER.match(line)
        if match:
            name = next(g for g in match.groups() if g).strip()
            if line.startswith('*** Move to:'):
                found[name] = found.get(name, '') + ''.join(found.get(c, '') for c in current)
                current = current + [name]
            else:
                current = [name]
                found.setdefault(name, '')
        elif line.startswith('+') and not line.startswith('+++'):
            for name in current:
                found[name] += line[1:] + '\n'
    return found

def written_text(args):
    """The text a write tool puts in its file: the whole content, or the new side of each replacement (Claude Code's
    MultiEdit `edits`, agy's multi_replace_file_content `ReplacementChunks`). The text it removes is not written."""
    parts = [args.get(key) for key in ('content', 'new_string', 'CodeContent', 'ReplacementContent')]
    for key, inner in (('edits', 'new_string'), ('ReplacementChunks', 'ReplacementContent')):
        chunks = args.get(key)
        for chunk in chunks if isinstance(chunks, list) else []:
            parts.append(chunk.get(inner) if isinstance(chunk, dict) else chunk)
    return '\n'.join(part for part in parts if isinstance(part, str))

def use_utf8():
    """The CLIs send and read UTF-8; on Windows the console defaults to cp1252: force UTF-8 for input and output."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

def installed_files():
    """Files the kit installed, relative to the home folder (state.json): protected like the configuration."""
    try:
        with open(os.path.join(os.path.expanduser('~'), '.ai-kit', 'state.json'), encoding='utf-8') as handle:
            files = json.load(handle).get('files') or {}
    except (OSError, ValueError, AttributeError):
        return ()
    return tuple(rel for rel in files if isinstance(rel, str) and not rel.endswith('/USER.md'))

# --- The kit's own commands in a shell command ---------------------------------------------------------------------
# The only shell rule: the kit's commands that change the installation or bill a model call. Any other command runs; what
# it changes is reported by the integrity check (4.8.0).

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash',
               'PowerShell', 'powershell')

WRAPPERS = {'sudo', 'doas', 'env', 'xargs', 'nohup', 'time', 'command', 'exec', 'builtin', 'nice', '-exec', '-execdir', '-ok'}

RUNS_TEXT = re.compile(r'-[a-z]*c|-command|-encodedcommand', re.I)  # bash -c, sh -lc, pwsh -Command: the next word is run

SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'pwsh', 'powershell'}

CMD = {'cmd', 'cmd.exe'}  # cmd /c program: the next word is run

# Shell keywords before a command (for … ; do ai-kit sync): the next word is a program, as after a wrapper (4.24.2).
KEYWORDS = {'if', 'then', 'else', 'elif', 'do', 'while', 'until', '!', 'coproc', 'eval', 'iex', 'invoke-expression'}
# Tools that run a program after their own `run` (uv run ai-kit sync).
RUNNERS = {'uv', 'poetry', 'pdm', 'hatch', 'pipx', 'rye'}
TIMEOUT_VALUES = ('-s', '-k', '--signal', '--kill-after')  # timeout's options followed by a value

CHANGES_DIRECTORY = {'cd', 'pushd', 'chdir', 'set-location', 'sl', 'push-location'}

HEREDOC = re.compile(r'(?<!<)<<(?!<)-?\s*(?:"([^"\n]+)"|\'([^\'\n]+)\'|([A-Za-z_][A-Za-z0-9_]*))')  # <<'END-NOTE' ends at END-NOTE

BLOCKED = ('Blocked by the kit: "{}" is configuration of the kit or of a CLI; the agent does not change it. '
           'Reading it is fine. Tell the person what to change (then run ai-kit sync --offline).')

def without_data_heredocs(text):
    """The command without the bodies of heredocs given to a program that is not a shell (python3 - <<EOF): that text is
    data or another language, not shell commands. A heredoc given to sh, bash, pwsh… is kept: it runs as commands."""
    out, skip_until = [], None
    for line in text.split('\n'):
        if skip_until is not None:
            if line.strip() == skip_until:
                skip_until = None
                out.append(line)
            continue
        out.append(line)
        match = HEREDOC.search(line)
        if match:
            words = line[:match.start()].split()
            piped = [w for part in line[match.end():].split('|')[1:] for w in part.split()[:1]]
            # sudo bash <<EOF, cd x && sh <<EOF, cat <<EOF | sh (4.24.2): a shell given the body runs it.
            if not any(re.sub(r'\.exe$', '', w.strip('"\'').replace('\\', '/').rsplit('/', 1)[-1].lower()) in SHELLS
                       for w in words + piped):
                skip_until = next(group for group in match.groups() if group)
    return '\n'.join(out)

def normalised(text, lower=True):
    """The text as the shell would resolve its paths: backslashes as /, quotes removed (~/".ai-kit"/x, overrides.tom'l'),
    // and /./ collapsed. Lower case: protected names compare without case (macOS, Windows); lower=False keeps the case, for
    a path to look for on disk (a case-sensitive system finds it only as written)."""
    text = re.sub('["\'\u2018-\u201f]', '', text.replace('\\', '/'))  # typographic quotes too: PowerShell reads them as quotes
    previous = None
    while previous != text:
        previous, text = text, text.replace('/./', '/')
    text = re.sub(r'/{2,}', '/', text)
    return text.lower() if lower else text

# A redirection that holds an &: 2>&1, >&2, <&3, >&-, &>, &>>. Its & does not end the command; |& is a pipe.
REDIRECTION = re.compile(r'\d*[<>]&(?:\d+|-)?|&>>?')

# Whether the last split of a line in a reading ended inside a quote (the line is then also read BLIND, on its own).
QUOTE_LEFT_OPEN = {}

# How a shell reads quotes, escapes and comments (4.24.2). The line is read every way that may apply, and a kit command found
# by any reading is refused: the hook cannot tell which shell runs the line.
POSIX, POWERSHELL, CMD_READING, BLIND = 'posix', 'powershell', 'cmd', 'blind'

# Past this size a line is read as before 4.24.2 only (split on every operator, quotes or not): the quote reading is for
# the lines an agent writes, and a huge line must never make the hook give up.
DEEP_READING_LIMIT = 20000
# What makes a line more than plain quotes: an escape (\\, `), $'…', a substitution $( ) (a quoting context of its own), a
# here-document or here-string, PowerShell's @' '@ and <# #>, a typographic quote (PowerShell ends a string at one), a #
# (bash reads it as a comment only at the start of a word) and PowerShell's --% (it stops parsing). Only a line with none
# of them is read for its quotes alone; any other is also split on every operator, as before 4.24.2.
UNSURE_QUOTES = re.compile("<<|<#|@'|@\"|`|\\$'|\\$\\(|\\\\|[\u2018-\u201f]|#|--%")

def readings(command, run_by=None):
    """The readings that may apply to this line: POSIX always; PowerShell when it holds a backquote or a backslash (its
    escape is `, a backslash is a path separator); cmd for the text given to cmd /c (no escape there, ' is no quote). The
    CLIs run their commands in bash or PowerShell, never in cmd."""
    if len(command) > DEEP_READING_LIMIT:
        return [BLIND]
    found = [POSIX]
    if '`' in command or '\\' in command:
        found.append(POWERSHELL)
    if run_by == 'cmd':
        found.append(CMD_READING)
    if UNSURE_QUOTES.search(command):
        found.append(BLIND)  # where the quotes cannot be read with certainty, the line is refused as before 4.24.2
    return found

def shell_segments(command, reading=POSIX):
    """The pipelines of a shell line: split on new lines, ;, &&, || and &, after joining continued lines, but never inside
    quotes: echo "x & ai-kit sync" is one command, its & is text (4.24.2). A pipeline stays whole: in "echo path | xargs rm"
    the path and the write are in two commands of the same pipeline. The reading decides the escape (\\ in POSIX, ` in
    PowerShell, none in cmd), the quotes (' is no quote in cmd; $'…' escapes in POSIX) and the comments (# up to the end of
    the line, not in cmd). A quote left open (a comment's apostrophe, another shell's syntax) hides nothing: the line is
    then also split as if no quote were written (BLIND), as before 4.24.2."""
    text = re.sub(r'(\\|`)\r?\n', ' ', command)
    text = REDIRECTION.sub(' ', without_data_heredocs(text).replace('|&', '|'))  # `ai-kit 2>&1 sync` is one command
    text = re.sub(r'<#.*?(#>|$)', ' ; ', text, flags=re.S)  # a PowerShell block comment ends what is before it
    if reading == BLIND:
        return [s for s in re.split(r'\r?\n|;|&&|\|\||&', text) if s.strip()]
    escape = {POSIX: '\\', POWERSHELL: '`'}.get(reading)
    quotes = '"' if reading == CMD_READING else '"\''
    segments, current, quote, at = [], [], None, 0
    while at < len(text):
        char, pair = text[at], text[at:at + 2]
        escapes_here = quote in (None, '"', "$'") if reading == POSIX else quote != "'"
        if escape and char == escape and escapes_here and at + 1 < len(text):
            # An escaped quote outside quotes is a plain character: dropped, it opens nothing. Other pairs stay as written
            # (a Windows path), only their second character never ends the command.
            current.append('' if not quote and text[at + 1] in '"\'' else pair)
            at += 2
            continue
        if quote:
            if char == quote[-1]:
                quote = None
        elif reading == POSIX and pair == "$'":
            quote = "$'"
            current.append(pair)
            at += 2
            continue
        elif char in quotes:
            quote = char
        elif char == '#' and reading != CMD_READING and (not current or current[-1].isspace()):
            newline = text.find('\n', at)
            at = len(text) if newline < 0 else newline  # a comment: up to the end of the line
            continue
        elif pair in ('&&', '||') or char in ';&\n':
            segments.append(''.join(current))
            current = []
            at += 2 if pair in ('&&', '||') else 1
            continue
        current.append(char)
        at += 1
    segments.append(''.join(current))
    found = [s for s in segments if s.strip()]
    QUOTE_LEFT_OPEN[command, reading] = quote is not None
    return found

def posix_words(text):
    """The words of a line as a POSIX shell reads them: \\" inside double quotes and \\x outside quotes are the plain
    character (bash -c "eval \\"ai-kit sync\\"" gives eval the text ai-kit sync)."""
    words, word, quote, started, at = [], [], None, False, 0
    while at < len(text):
        char = text[at]
        if char == '\\' and quote != "'" and at + 1 < len(text) and (quote is None or text[at + 1] in '"\\$`'):
            word.append(text[at + 1])
            started, at = True, at + 2
            continue
        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in '"\'':
            quote, started = char, True
        elif char.isspace():
            if started or word:
                words.append(''.join(word))
            word, started = [], False
        else:
            word.append(char)
        at += 1
    if started or word:
        words.append(''.join(word))
    return words

def shell_texts(pipeline):
    """The texts this pipeline gives a shell to run as a command line of its own: bash -c '…', pwsh -Command "…",
    cmd /c …, eval '…'. The words are read as a POSIX shell and as PowerShell or cmd read them (a backslash is a path
    separator there); the texts of both readings are given."""
    readings = (posix_words(pipeline), split_words(pipeline)) if '\\' in pipeline else (split_words(pipeline),)
    for words in readings:
        yield from texts_run_by_a_shell(words)  # (text, 'cmd' or None)

def texts_run_by_a_shell(words):
    """One pass from the end: where the next -c (or /c) is, for each word, so a long line costs its length, not its square."""
    norm = [normalised(w) for w in words]
    next_flag, next_slash_c, flag, slash_c = [None] * len(words), [None] * len(words), None, None
    for index in range(len(words) - 1, -1, -1):
        next_flag[index], next_slash_c[index] = flag, slash_c
        if RUNS_TEXT.fullmatch(norm[index]):
            flag = index
        if norm[index] in ('/c', '/k'):
            slash_c = index
    for index, word in enumerate(norm):
        program = re.sub(r'\.exe$', '', word.rsplit('/', 1)[-1])
        if program in SHELLS:
            at = next_flag[index]
            if at is not None and at + 1 < len(words):
                yield words[at + 1], None
        elif program in CMD:
            at = next_slash_c[index]
            if at is not None:
                yield ' '.join(words[at + 1:]), 'cmd'
        elif program in ('eval', 'iex', 'invoke-expression') and index + 1 < len(words):
            yield ' '.join(words[index + 1:]), None

def substitutions(text):
    """The commands of $( … ), ` … ` and the process substitutions <( … ), >( … ) outside single quotes: the shell runs them,
    inside double quotes too (4.24.2)."""
    found, quote, at = [], None, 0
    while at < len(text):
        char = text[at]
        if char == '\\' and quote != "'":
            at += 2
            continue
        if quote == "'":
            quote = None if char == "'" else quote
        elif char == "'" and quote is None:
            quote = "'"
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif (text.startswith(('$(', '<(', '>('), at) and not text.startswith('$((', at)) and (quote is None or text[at] == '$'):
            depth, end, inner = 1, at + 2, None
            while end < len(text) and depth:
                char_in = text[end]
                if inner:
                    inner = None if char_in == inner else inner  # a ) inside quotes does not close the substitution
                elif char_in in '"\'':
                    inner = char_in
                else:
                    depth += {'(': 1, ')': -1}.get(char_in, 0)
                end += 1
            found.append(text[at + 2:end - 1] if depth == 0 else text[at + 2:])
            at = end
            continue
        elif char == '`':
            end = text.find('`', at + 1)
            found.append(text[at + 1:end] if end > 0 else text[at + 1:])
            at = end + 1 if end > 0 else len(text)
            continue
        at += 1
    return found

def split_words(pipeline):
    """The words of a pipeline as the shell reads them, as written: a quoted word stays one word
    ("C:\\Program Files\\Python311\\python.exe" is a program, not two words) and keeps the quotes written inside it (the
    text given to bash -c: '"/path with spaces/ai-kit" sync'), | is a word of its own. A quote left open (the pipeline is a
    piece of a longer quoted text) is read as a space."""
    words, word, quote, started, opened = [], [], None, False, 0
    for at, char in enumerate(pipeline):
        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in '"\'':
            quote, started, opened = char, True, at
        elif char.isspace() or char == '|':
            if started or word:
                words.append(''.join(word))
            if char == '|':
                words.append('|')
            word, started = [], False
        else:
            word.append(char)
    if quote:
        # The quote left open belongs to the longer text (pwsh -Command "& 'C:\\Program Files\\kit\\ai-kit.exe' sync": the
        # piece after the & ends with the outer quote). Without it, the quoted words of the piece stay whole.
        return split_words(pipeline[:opened] + ' ' + pipeline[opened+1:])
    if started or word:
        words.append(''.join(word))
    return words

def commands(pipeline):
    """(program, its words, the same words with their case kept) for each program the shell runs in a pipeline, without
    the bracket that opens them; after sudo, xargs, find -exec, bash -c… the next word is a program too, and the text
    bash -c is given is read as a command line of its own. Program and words are lower case: names compare without case."""
    expect, current, found, text_runs = True, None, [], False
    pending = split_words(pipeline)
    while pending:
        written = pending.pop(0)
        if written == '|':
            expect, text_runs = True, False
            continue
        if text_runs and ' ' in written.strip():
            pending[:0] = split_words(written)  # bash -c '"/my tools/ai-kit" sync': the quoted text is a command line
            text_runs = False
            continue
        text_runs = False
        word = normalised(written)
        opens = word.startswith(('(', '$(', '`', '{'))
        # (ai-kit sync), { ai-kit sync; }: the brackets around a word are not part of it (4.24.2: sync) was no action).
        core, cased = (re.sub(r'[)`}]+$', '', re.sub(r'^[\s`({$]+', '', w)) for w in (word, normalised(written, lower=False)))
        if opens and not core:
            expect = True  # ( or { alone: the next word is the program
            continue
        if not (expect or opens):
            if found:
                found[-1][1].append(core)
                found[-1][2].append(cased)
            if (current in SHELLS and RUNS_TEXT.fullmatch(core)) or core in ('-exec', '-execdir', '-ok') or (current in CMD and core in ('/c', '/k')):
                expect = text_runs = True  # bash -c '…', find … -exec, cmd /c: what follows is run
            continue
        if re.fullmatch(r'[a-z_][a-z0-9_]*=.*', core):
            found.append(('=', [core], [cased]))  # VAR=value: an assignment, not a program
            continue
        current = core.rsplit('/', 1)[-1]
        found.append((current, [], []))
        if current == 'timeout':  # timeout [options] DURATION program: the duration is no program
            while pending and normalised(pending[0]).startswith('-'):
                if normalised(pending.pop(0)) in TIMEOUT_VALUES and pending:
                    pending.pop(0)
            if pending and re.fullmatch(r'[0-9.]+[smhd]?', normalised(pending[0])):
                pending.pop(0)
            expect = True
            continue
        if current in RUNNERS and pending and normalised(pending[0]) == 'run':
            pending.pop(0)
            expect = True
            continue
        expect = current in WRAPPERS or current in KEYWORDS or (core.startswith('-') and expect)
    return found

PYTHONS = re.compile(r'(python[0-9.]*|py)(\.exe)?')

# The kit's own subcommands that change the installation or bill a model call: the agent tells the person, it does not run them
# (0.52.0). Reading ones (doctor, usage, friction logging, --version, managed-settings into an empty folder) stay allowed.
KIT_REFUSED = {'init', 'sync', 'rollback', 'uninstall'}

# Every action of the command (installer/cli.py; a test compares the two lists).
KIT_ACTIONS = {'init', 'sync', 'team', 'status', 'doctor', 'rollback', 'user', 'uninstall', 'usage', 'friction', 'managed-settings', 'validate', 'news'}

# The launchers of a kit folder: they run the same command, and init when no action is given (Installer.cmd calls launcher.py).
LAUNCHERS = ('bootstrap.sh', 'bootstrap.ps1', 'launcher.py')

KIT_COMMAND_BLOCKED = ('Blocked by the kit: `ai-kit {}` changes the installation or bills a model call; the agent does not run it. '
                       'Tell the person the command to run in a terminal.')

def kit_arguments(program, words):
    """(the words after the kit's entry point, the launcher's file name or None) when this program runs the kit: ai-kit,
    python -m ai_kit, or a launcher run directly, by Python or by a shell. Else None."""
    if program in ('ai-kit', 'ai-kit.cmd', 'ai-kit.exe'):
        return words, None
    if program == 'installer.cmd' or program in LAUNCHERS:
        return words, program
    if PYTHONS.fullmatch(program) and '-m' in words:
        index = words.index('-m')
        return (words[index + 2:], None) if index + 1 < len(words) and words[index + 1] in ('ai_kit', 'installer') else None
    if PYTHONS.fullmatch(program):  # the script Python runs, not a file it is given to check
        index = next((i for i, w in enumerate(words) if not w.startswith('-')), None)
    elif program in SHELLS:
        index = next((i for i, w in enumerate(words) if w.rsplit('/', 1)[-1] in LAUNCHERS), None)
    elif program in ('source', '.'):  # read into the current shell: it runs all the same
        index = 0 if words else None
    else:
        return None
    name = words[index].rsplit('/', 1)[-1] if index is not None else ''
    return (words[index + 1:], name) if name in LAUNCHERS else None

def kit_launcher_at(name, text, current):
    """True when the launcher a pipeline names sits with the kit's other launchers (scripts/ of a kit folder). The name alone
    does not tell: another project has its own bootstrap.sh. The path is looked for with the case it was written in (a
    case-sensitive system tells Kit from kit): each word that ends with the name, a quoted path with spaces as one word,
    then the words of a text given to bash -c "…"."""
    whole = split_words(text)
    written = whole + [w for word in whole if ' ' in word.strip() for w in split_words(word)]
    scripts = [w for w in (normalised(word, lower=False) for word in written) if w.rsplit('/', 1)[-1].lower() == name] or [name]
    for script in scripts:
        folder = os.path.dirname(where(re.sub(r'^\$\{?home\}?', '~', script, flags=re.I), current))
        if all(os.path.isfile(os.path.join(folder, other)) for other in ('bootstrap.sh', 'launcher.py')):
            return True
    return False

# How much one line may make the hook read (the texts a shell runs, the substitutions, each in every reading): a text
# costs 1, plus 1 per 200 characters. Past it the line is refused: a line built to be slow to read must not be let through
# by a hook that gave up.
READ_BUDGET = 400
TOO_INTRICATE = ('Blocked by the kit: this command line nests too many shells or substitutions to be read for the kit\'s '
                 'commands. Split it, or tell the person the command to run in a terminal.')

def kit_command_reason(command, cwd, depth=0, budget=None, run_by=None):
    """Reason to refuse a kit subcommand the agent must not run, or None. The line is read every way a shell may read it
    (readings); the text a shell is given to run, and each substitution, is read the same way, as a line of its own."""
    budget = budget if budget is not None else [READ_BUDGET]
    pending = readings(command, run_by)
    for reading in pending:  # each reading on its own, from the same folder: a cd counts once in each
        reason = kit_command_in(shell_segments(command, reading), cwd, depth, budget)
        if reason:
            return reason
        if QUOTE_LEFT_OPEN.get((command, reading)) and BLIND not in pending:
            pending.append(BLIND)  # a quote this reading left open hides nothing: the line is also split as before
    return None

def kit_command_in(pipelines, cwd, depth, budget):
    current = real(cwd)
    for pipeline in pipelines:
        text = pipeline
        if depth < 4 and len(text) <= DEEP_READING_LIMIT:
            seen = set()
            for inner, run_by in itertools.chain(shell_texts(text), ((s, None) for s in substitutions(text))):
                if (inner, run_by) in seen:
                    continue  # each text once
                seen.add((inner, run_by))
                budget[0] -= 1 + len(inner) // 200
                if budget[0] < 0:
                    return TOO_INTRICATE
                reason = kit_command_reason(inner, current, depth + 1, budget, run_by)
                if reason:
                    return reason
        for program, words, cased in commands(text):
            if program in CHANGES_DIRECTORY and words:
                current = where(cased[-1], current)
            if PYTHONS.fullmatch(program) and '--sync' in words and any(w.endswith('/.ai-kit/bin/friction.py') for w in words):
                return KIT_COMMAND_BLOCKED.format('friction --sync')  # publication is the person's approval (2.0.0)
            found = kit_arguments(program, words)
            if found is None:
                continue
            arguments, launcher = found
            # The action is the first word that names one: an option's value placed before it (--home /tmp/h uninstall) is
            # never taken for it, and an option counts wherever it is written (--live doctor).
            sub = next((w for w in arguments if w in KIT_ACTIONS), '')
            rest = arguments[arguments.index(sub) + 1:] if sub else []
            if not sub and launcher and (launcher == 'installer.cmd' or kit_launcher_at(launcher, text, current)):
                sub = 'init'  # a launcher with no action installs
            if (sub in KIT_REFUSED or (sub == 'doctor' and '--live' in arguments) or (sub == 'team' and 'use' in rest)
                    or (sub == 'friction' and ('--publish' in arguments or '--sync' in arguments))):
                return KIT_COMMAND_BLOCKED.format(' '.join([sub] + rest[:2]).strip())
    return None

def protected_names():
    return [entry.lower() for entry in CONFIG_PATHS + REPO_CONFIG + installed_files()]

def mention(text, names):
    """The first protected name a text mentions, or None: whole names (.claude.json.bak is not .claude.json, my.ai-kit is
    not .ai-kit), a folder entry only as that folder, a prefix entry (00_, ai-kit-) followed by anything."""
    for name in names:
        stem = name.rstrip('/')
        if not stem:
            continue
        start = text.find(stem)
        while start >= 0:
            end = start + len(stem)
            before = start == 0 or not re.match(r'[a-z0-9_.-]', text[start - 1])
            if name.endswith('/'):
                after = end == len(text) or text[end] == '/'
            else:
                after = name.endswith(('_', '-')) or end == len(text) or not re.match(r'[a-z0-9_.-]', text[end])
            if before and after:
                return stem
            start = text.find(stem, start + 1)
    return None

# --- Write tools ---------------------------------------------------------------------------------------------------

KIT_GIT = ('.git/config', '.git/hooks')

KIT_BLOCKED = ('Blocked by the kit: this touches the kit folder "{}", the source of the next update, from another repo; '
               'reading it is fine. Change it yourself, or work on the kit from a session started in its folder.')

KIT_GIT_BLOCKED = ('Blocked by the kit: this changes the git configuration of the kit folder ("{}"), which the kit runs git in; '
                   'make the change yourself in a terminal.')

def kit_dir():
    """(real path, the forms a command may write it in) of the kit folder of state.json, or (None, ())."""
    try:
        with open(os.path.join(os.path.expanduser('~'), '.ai-kit', 'state.json'), encoding='utf-8') as handle:
            raw = json.load(handle).get('kit_dir')
    except (OSError, ValueError, AttributeError):
        return None, ()
    if not isinstance(raw, str) or not raw or not os.path.isdir(raw):
        return None, ()
    folder, home = real(raw), real(os.path.expanduser('~'))
    forms = {normalised(raw).rstrip('/'), normalised(folder).rstrip('/')}
    if inside(folder, home):
        forms.add('~/' + normalised(os.path.relpath(folder, home)).rstrip('/'))
    return folder, tuple(forms)

def inside(path, folder):
    """True when path is folder or under it (a folder boundary: ai-toolkit-fix is not under ai-toolkit)."""
    try:
        relative = os.path.relpath(path, folder)
    except ValueError:
        return False
    return relative == '.' or not (relative == '..' or relative.startswith('..' + os.sep))

def where(word, current):
    """The folder a cd or -C word leads to, from the current one (~ expanded)."""
    word = word.strip('"\'')
    if word.startswith('~'):
        word = os.path.expanduser('~') + word[1:]
    return real(word if os.path.isabs(word) else os.path.join(current, word))

def real(path):
    """Absolute path with symbolic links resolved (a link to a protected folder is that folder); as written when the system
    rejects it (a NUL byte)."""
    try:
        return os.path.realpath(os.path.abspath(path))
    except (ValueError, OSError):
        try:
            return os.path.realpath(os.path.abspath(path.replace('\0', '')))
        except (ValueError, OSError):
            return os.path.abspath(path.replace('\0', ''))

def config_reason(absolute, directories, content=''):
    home = real(os.path.expanduser('~'))
    try:
        relative = os.path.relpath(absolute, home).replace(os.sep, '/')
    except ValueError:
        relative = '..'
    if not relative.startswith('..'):
        lowered = relative.lower()
        for entry in CONFIG_PATHS + installed_files():
            if lowered == entry.lower().rstrip('/') or (entry.endswith(('/', '_', '-')) and lowered.startswith(entry.lower())):
                return 'Blocked by the kit: "~/' + relative + '" is configuration of the kit or of a CLI; the agent does not change it. Make the change yourself (then run ai-kit sync --offline).'
    for directory in directories:
        try:
            inner = os.path.relpath(absolute, real(directory)).replace(os.sep, '/').lower()
        except ValueError:
            continue
        if inner in REPO_CONFIG:
            return ('Blocked by the kit: "' + inner + '" configures the repo\'s guardrails or agent settings; a person changes it, '
                    'through a merge request.')
    if os.path.basename(absolute).lower().startswith('.env') and KIT_VARIABLES.search(content):
        return DOTENV_BLOCKED
    return None

def as_written(path):
    """A path without the forms that name the same file another way: the Windows long path prefix (\\\\?\\C:\\…, \\\\?\\UNC\\…)
    and a leading ~ (the home folder)."""
    for prefix, kept in (('\\\\?\\UNC\\', '\\\\'), ('//?/UNC/', '//'), ('\\\\?\\', ''), ('//?/', ''), ('\\\\.\\', ''), ('//./', '')):
        if path.upper().startswith(prefix):
            path = kept + path[len(prefix):]
            break
    if path == '~' or path.startswith(('~/', '~\\')):
        path = os.path.expanduser('~') + path[1:]
    return path

def check(file_path, cwd, content=''):
    """Reason for refusal if a write tool's file is protected configuration, otherwise None. The repo is found from the
    file itself (and from the launch folder): a file of another repo keeps that repo's CLI settings protected."""
    file_path = as_written(file_path)
    absolute = real(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    directories = list(dict.fromkeys(repo_dirs(os.path.dirname(absolute)) + repo_dirs(cwd)))
    reason = config_reason(absolute, directories, content)
    if reason:
        return reason
    folder, _ = kit_dir()
    if folder and any(inside(absolute, os.path.join(folder, *g.split('/'))) for g in KIT_GIT):
        return KIT_GIT_BLOCKED.format(os.path.relpath(absolute, folder).replace(os.sep, '/'))
    if folder and inside(absolute, folder) and not inside(real(cwd), folder):
        return KIT_BLOCKED.format(folder)
    return None

def record_refusal(guardrail):
    """One line per refusal in ~/.ai-kit/refusals.jsonl: when, and which guardrail; never the command, so no path and no
    secret is kept. `ai-kit usage` counts them. Only the installed copy records (the one in ~/.ai-kit/hooks), not a
    doctor probe; the file keeps its last 1000 lines. A failure to record never changes the answer."""
    folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.basename(folder) != '.ai-kit' or os.environ.get('AI_KIT_PROBE') == '1':
        return
    path = os.path.join(folder, 'refusals.jsonl')
    try:
        if os.path.exists(path) and os.path.getsize(path) > 200000:
            with open(path, encoding='utf-8', errors='replace') as handle:
                kept = handle.readlines()[-1000:]
            with open(path, 'w', encoding='utf-8') as handle:
                handle.writelines(kept)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'guardrail': guardrail}) + '\n')
    except OSError:
        pass

def passes(payload, note=None):
    """The answer that lets a tool call through. agy requires a decision in every answer (its hooks docs: `decision`,
    required) and refuses an empty object without a reason. "ask" hands the call to agy's own permission flow; "allow" would approve it on the person's behalf (4.7.1). The other
    CLIs read an empty object as nothing to say."""
    answer = dict(note or {})
    if isinstance(payload, dict) and 'toolCall' in payload:
        answer['decision'] = 'ask'
    return json.dumps(answer, ensure_ascii=False)

def fallback(payload):
    """After an unexpected input: never a shell command, but a write tool that names a protected path is refused."""
    try:
        call = payload.get('toolCall') if isinstance(payload.get('toolCall'), dict) else {}
        tool = str(payload.get('tool_name') or call.get('name') or '')
        if tool in SHELL_TOOLS:
            return None
        name = mention(normalised(json.dumps(payload)), protected_names())
        return BLOCKED.format(name) if name else None
    except Exception:
        return None

def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    try:
        decision = decide(payload)
    except Exception:
        decision = fallback(payload)
    if decision:
        record_refusal('protected-paths')
    print(json.dumps(deny_output(payload, decision), ensure_ascii=False) if decision else passes(payload))

def decide(payload):
    # Input shapes: Gemini CLI (tool_name / tool_input.file_path), Antigravity (toolCall.name / toolCall.args.TargetFile...),
    # Codex (hook_event_name PreToolUse, apply_patch whose paths are in the patch headers), Claude Code (Bash, PowerShell, Write…).
    call = payload.get('toolCall') or {}
    tool = str(payload.get('tool_name') or call.get('name') or '')
    args = payload.get('tool_input') or call.get('args') or {}
    workspace = (payload.get('workspacePaths') or [None])[0]
    cwd = payload.get('cwd') or workspace or os.getcwd()
    if tool in SHELL_TOOLS:
        if not isinstance(args, dict):
            args = {'command': args}
        command = as_text(args.get('command') or args.get('cmd') or args.get('CommandLine'))
        folder = (args.get('workdir') or args.get('cwd') or cwd) if isinstance(args, dict) else cwd
        return kit_command_reason(command, folder)
    if not re.search(r'write|replace|edit|patch', tool, re.I):
        return None
    paths = target_paths(tool, args)
    if not isinstance(args, dict):
        args = {'input': args}
    content, added = written_text(args), {}
    if 'patch' in tool.lower():
        for value in args.values():
            for name, text in patch_additions(as_text(value)).items():
                added[name] = added.get(name, '') + text
    for file_path in paths:
        decision = check(file_path, cwd, added.get(file_path, content) if added else content)
        if decision:
            return decision
    return None

if __name__ == '__main__':
    main()
