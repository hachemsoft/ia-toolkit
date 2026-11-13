#!/usr/bin/env python3
"""Kit guardrail (before a tool call): blocks agent writes to the configuration of the kit and of the CLIs, and under the
paths a repo protects.

Protected paths of a repo are glob patterns, one per line, in <repo>/.ai-kit/protected-paths,
comments with #. Example: target/**  ·  models/legacy/**  ·  *.lock  ·  dbt_project.yml
A shell command that names a protected path is allowed only when every program it runs only reads (cat, grep, ls…):
the list of what is allowed is closed, not the list of what writes. Output: JSON {"decision": "deny", "reason": ...} or {}.
"""
import fnmatch
import json
import os
import re
import sys
import time

# Protected-paths file of a folder: .ai-kit/protected-paths (neutral, all CLIs).
PATTERN_FILES = (os.path.join('.ai-kit', 'protected-paths'),)

# Configuration of the kit and of the CLIs, always protected: an agent must not be able to switch off its own guardrails.
# Relative to the home folder; a trailing / protects a whole folder. ~/.ai-kit/learning/ (personal /learn progress) and
# ~/.ai-kit/context/USER.md (the person's own file) stay writable. Every file the kit installed (state.json) is protected too.
CONFIG_PATHS = ('.ai-kit/aikit.toml', '.ai-kit/lock.toml', '.ai-kit/sources/', '.ai-kit/state.json', '.ai-kit/hooks/', '.ai-kit/bin/', '.ai-kit/backups/',
                '.ai-kit/runtime/', '.ai-kit/schemas/', '.ai-kit/context/00_', '.ai-kit/context/10_', '.ai-kit/context/20_',
                # the news the session hook shows (their text enters the next session) and its marker
                '.ai-kit/news/', '.ai-kit/news.json',
                '.gemini/00_', '.gemini/10_', '.gemini/20_', '.gemini/settings.json', '.gemini/.env', '.gemini/config/plugins/ai-kit/',
                '.gemini/antigravity-cli/settings.json',  # agy's permissions: the person's answers, never the agent's
                '.codex/config.toml', '.codex/AGENTS.md', '.codex/ai-kit/', '.claude/settings.json', '.claude/CLAUDE.md', '.claude/agents/ai-kit-',
                '.claude.json',
                # git's own configuration can redirect the kit's next fetch (url.insteadOf) or run a program (core.fsmonitor) (0.51.1).
                '.gitconfig', '.config/git/config')
# The folders that hold that configuration: a `cd` into one of them, or a wildcard inside one, is treated as touching it.
CONFIG_FOLDERS = ('.ai-kit', '.gemini', '.codex', '.claude')
# Configuration of a repo, protected in every repo: a project setting can turn hooks off or change the environment the
# guardrails read (a .env setting the kit's variables is refused through its content).
REPO_CONFIG = ('.ai-kit/protected-paths', '.claude/settings.json', '.claude/settings.local.json',
               '.gemini/settings.json', '.gemini/.env', '.codex/config.toml')
KIT_VARIABLES = re.compile(r'^\s*(export\s+)?(AI_KIT_[A-Z_]*|DBT_TARGET)\s*=', re.M)
SETS_KIT_VARIABLE = re.compile(r'(ai_kit_[a-z_]*|dbt_target)\s*=')  # the same, anywhere in a normalised (lower case) command
DOTENV_BLOCKED = 'Blocked by the kit: a .env file the agent writes must not set the kit\'s variables (AI_KIT_*) or DBT_TARGET.'

def patterns(directory):
    found = []
    for name in PATTERN_FILES:
        try:
            with open(os.path.join(directory, name), encoding='utf-8') as handle:
                found += [line.strip() for line in handle if line.strip() and not line.lstrip().startswith('#')]
        except OSError:
            continue
    return found

def pattern_dirs(start):
    """Folders whose protected-paths file applies: from a folder up to the repo root (the first folder that contains .git).
    A monorepo started from a subfolder stays protected by the root."""
    dirs, current = [], os.path.abspath(start)
    while True:
        dirs.append(current)
        if os.path.exists(os.path.join(current, '.git')):
            return dirs
        parent = os.path.dirname(current)
        if parent == current:
            return [os.path.abspath(start)]
        current = parent

def matches(relative, pattern):
    # '**' also covers zero folders; fnmatch does not do that on its own. Case-insensitive comparison (macOS, Windows).
    # A leading / anchors the pattern at the repo root, as in .gitignore.
    relative, pattern = relative.lower(), pattern.lower().lstrip('/')
    candidates = {pattern, pattern.replace('/**', ''), pattern.replace('**/', '')}
    if any(fnmatch.fnmatchcase(relative, c) for c in candidates):
        return True
    # Folder prefix with a boundary: target/** protects target/x.sql, not targets/x.sql.
    return any(relative == p[:-3] or relative.startswith(p[:-3] + '/') for p in candidates if p.endswith('/**'))

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

# --- Shell commands ---------------------------------------------------------------------------------------------------

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash',
               'PowerShell', 'powershell')
# Programs that only read: a command naming a protected path is allowed only when it runs nothing else.
READERS = {'cat', 'bat', 'less', 'more', 'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack', 'ls', 'll', 'dir', 'stat', 'file',
           'wc', 'diff', 'cmp', 'md5', 'md5sum', 'shasum', 'sha1sum', 'sha256sum', 'jq', 'yq', 'column', 'sort', 'uniq', 'cut', 'nl', 'od',
           'xxd', 'hexdump', 'strings', 'tree', 'du', 'realpath', 'readlink', 'basename', 'dirname', 'test', '[', 'echo', 'printf', 'true',
           'type', 'which', 'find', 'git', 'cp',  # not sed or awk: their scripts can write a file or run a command
           # PowerShell
           'get-content', 'gc', 'select-string', 'sls', 'get-childitem', 'gci', 'test-path', 'get-item', 'gi', 'get-filehash',
           'resolve-path', 'measure-object', 'write-output', 'write-host', 'out-string', 'format-list', 'select-object'}
GIT_READS = {'status', 'diff', 'log', 'show', 'blame', 'ls-files', 'grep', 'rev-parse', 'cat-file', 'describe'}
WRAPPERS = {'sudo', 'doas', 'env', 'xargs', 'nohup', 'time', 'command', 'exec', 'builtin', 'nice', '-exec', '-execdir', '-ok'}
RUNS_TEXT = re.compile(r'-[a-z]*c|-command|-encodedcommand', re.I)  # bash -c, sh -lc, pwsh -Command: the next word is run
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'pwsh', 'powershell'}
CMD = {'cmd', 'cmd.exe'}  # cmd /c program: the next word is run
# A run of > is read once from its start: no quadratic search on a long one.
REDIRECTION = re.compile(r'(?<!>)>+\|?\s*([^\s;|&<>]+)')
CHANGES_DIRECTORY = {'cd', 'pushd', 'chdir', 'set-location', 'sl', 'push-location'}
HEREDOC = re.compile(r'<<-?\s*["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?')
MAX_COMMAND = 50000  # longer: judged on its own (a pathological command is refused when it names a protected path)
BLOCKED = ('Blocked by the kit: this command touches "{}", configuration of the kit or of a CLI; the agent does not change it. '
           'Reading it with cat, grep or ls is fine. Tell the person what to change (then run ai-kit sync --offline).')

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
            # sudo bash <<EOF, cd x && sh <<EOF: any shell before the heredoc runs its body.
            if not any(w.strip('"\'').rsplit('/', 1)[-1].lower() in SHELLS for w in words):
                skip_until = match.group(1)
    return '\n'.join(out)

def normalised(text):
    """The text as the shell would resolve its paths: backslashes as /, quotes removed (~/".ai-kit"/x, overrides.tom'l'),
    // and /./ collapsed. Lower case: protected names compare without case (macOS, Windows)."""
    text = text.replace('\\', '/').replace('"', '').replace("'", '')
    previous = None
    while previous != text:
        previous, text = text, text.replace('/./', '/')
    return re.sub(r'/{2,}', '/', text).lower()

def shell_segments(command):
    """The pipelines of a shell line: split on new lines, ;, &&, || and &, after joining continued lines. A pipeline stays
    whole: in "echo path | xargs rm" the path and the write are in two commands of the same pipeline."""
    text = re.sub(r'(\\|`)\r?\n', ' ', command)
    return [s for s in re.split(r'\r?\n|;|&&|\|\||&', without_data_heredocs(text)) if s.strip()]

def command_words(pipeline):
    """(program, its words) for each program the shell runs in a pipeline, lower case, without the quote or bracket that
    opens them; after sudo, xargs, find -exec, bash -c… the next word is a program too."""
    expect, current, found = True, None, []
    for word in pipeline.replace('|', ' | ').split():
        if word == '|':
            expect = True
            continue
        opens = word.startswith(('(', '$(', '`', '{'))
        core = re.sub(r'^[\s"\'`({$]+', '', word).lower()
        if not (expect or opens):
            if found:
                found[-1][1].append(core)
            if (current in SHELLS and RUNS_TEXT.fullmatch(core)) or core in ('-exec', '-execdir', '-ok') or (current in CMD and core in ('/c', '/k')):
                expect = True  # bash -c '…', find … -exec, cmd /c: what follows is run
            continue
        if re.fullmatch(r'[a-z_][a-z0-9_]*=.*', core):
            found.append(('=', [core]))  # VAR=value: an assignment, not a program
            continue
        current = core.rsplit('/', 1)[-1]
        found.append((current, []))
        expect = current in WRAPPERS or (core.startswith('-') and expect)
    return found

def only_reads(program, words, mentions_in):
    """True when this program, with these words, only reads. cp reads when the protected path is not its destination."""
    if program not in READERS:
        return False
    positional = [w for w in words if not w.startswith('-')]
    if program == 'find':
        return not any(w in ('-delete', '-exec', '-execdir', '-ok', '-okdir', '-fprint', '-fprint0', '-fprintf', '-fls') for w in words)
    if program == 'git':
        _, subcommand, _ = git_call(words)  # git -C folder status: the folder is not the subcommand
        sets_config = any(w == '-c' and '=' in words[i + 1] for i, w in enumerate(words[:-1]))  # -c key=value can run a program
        return subcommand in GIT_READS and not sets_config and not any(w.startswith('--output') for w in words)
    if program == 'cp':
        if any(w == '-t' or w.startswith('--target-directory') for w in words):
            return False
        return bool(positional) and not mentions_in(positional[-1])
    # Readers that also write a file when asked to: their output option, or a second file name.
    if program in ('sort', 'tree'):
        return not any(w.startswith('--o') or re.match(r'-[a-z0-9]*o', w) for w in words)  # -o, and -uo: o glued to other options
    if program == 'uniq':
        return len(positional) < 2
    if program == 'xxd':
        return '-r' not in words and len(positional) < 2
    if program == 'yq':
        return not any(w in ('-i', '--inplace') for w in words)
    return True

PYTHONS = re.compile(r'(python[0-9.]*|py)(\.exe)?')
KIT_TOOLS = ('/.ai-kit/bin/friction.py', '/.ai-kit/bin/weakened_tests.py')  # run by /friction (writes only outside the protected paths) and /review (reads only)

# The kit's own subcommands that change the installation or bill a model call: the agent tells the person, it does not run them
# (0.52.0). Reading ones (doctor, usage, friction logging, --version, managed-settings into an empty folder) stay allowed.
KIT_REFUSED = {'init', 'sync', 'rollback', 'uninstall'}
# Every action of the command (installer/cli.py; a test compares the two lists).
KIT_ACTIONS = {'init', 'sync', 'team', 'status', 'doctor', 'rollback', 'user', 'uninstall', 'usage', 'friction', 'managed-settings', 'validate'}
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
    else:
        return None
    name = words[index].rsplit('/', 1)[-1] if index is not None else ''
    return (words[index + 1:], name) if name in LAUNCHERS else None

def kit_launcher_at(name, text, current):
    """True when the launcher a pipeline names sits with the kit's other launchers (scripts/ of a kit folder). The name alone
    does not tell: another project has its own bootstrap.sh."""
    script = next((w for w in text.replace('|', ' ').split() if w.rsplit('/', 1)[-1] == name), name)
    folder = os.path.dirname(where(re.sub(r'^\$\{?home\}?', '~', script), current))
    return all(os.path.isfile(os.path.join(folder, other)) for other in ('bootstrap.sh', 'launcher.py'))

def kit_command_reason(command, cwd):
    """Reason to refuse a kit subcommand the agent must not run, or None."""
    current = real(cwd)
    for pipeline in shell_segments(command):
        text = normalised(pipeline)
        for program, words in command_words(text):
            if program in CHANGES_DIRECTORY and words:
                current = where(words[-1], current)
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

def runs_kit_tool(program, words, mentions_in):
    """True when this program is Python running one of the kit's own tools, and its other words name no protected path."""
    if not PYTHONS.fullmatch(program):
        return False
    script = next((w for w in words if not w.startswith('-')), '')
    return script.endswith(KIT_TOOLS) and not any(mentions_in(w) for w in words if w != script)

def protected_names():
    return [entry.lower() for entry in CONFIG_PATHS + REPO_CONFIG + installed_files()]

def mention(text, names):
    """The first protected name a text mentions, or None. A file name must end there (.claude.json.bak is not .claude.json)."""
    for name in names:
        start = text.find(name.rstrip('/'))
        while start >= 0:
            end = start + len(name.rstrip('/'))
            if name.endswith('/') or end == len(text) or not re.match(r'[a-z0-9_.-]', text[end]):
                return name.rstrip('/')
            start = text.find(name.rstrip('/'), end)
    return None

def touches_config_folder(program, words, names):
    """cd into a configuration folder, a wildcard inside one, the folder kept in a variable, or a program aimed at the folder
    itself that does not only read (ln -s ~/.ai-kit x, rm -rf ~/.claude, find ~/.ai-kit -delete, cp x ~/.ai-kit/): the file
    it writes is not named, or what follows cannot be judged, so it counts as a write."""
    def is_folder(word):
        return any(word.rstrip('/').endswith('/' + f) or word.rstrip('/') == f for f in CONFIG_FOLDERS)
    if program in CHANGES_DIRECTORY and words:
        last = words[-1].rstrip('/')
        if is_folder(last) or any('/' + folder + '/' in last + '/' for folder in CONFIG_FOLDERS):
            return True
    if program == '=':
        # p=~/.ai-kit, c=$HOME/.ai-kit/context: a configuration folder, or a folder above a protected file.
        value = '/' + words[0].split('=', 1)[1].rstrip('/')
        tails = [value[value.rfind('/' + f) + 1:] for f in CONFIG_FOLDERS if '/' + f in value]
        return any(tail in CONFIG_FOLDERS or any(name.startswith(tail + '/') for name in names) for tail in tails)
    if any(is_folder(w) for w in words) and not only_reads(program, words, is_folder):
        return True
    return any(re.search(r'[*?\[]', w) and any('/' + f + '/' in '/' + w for f in CONFIG_FOLDERS) for w in words)

# --- The kit folder and git's configuration (0.51.1) -------------------------------------------------------------------
# The kit folder an installation came from (state.json kit_dir) is the source of the next update and of the session hook's
# remote read. Its .git/config and .git/hooks are always protected; the rest of it when the session starts outside it: a
# maintainer works on the kit with an agent inside the clone.

KIT_GIT = ('.git/config', '.git/hooks')
GIT_CONFIG_SENSITIVE = re.compile(r'(url|credential|core|include|includeif)\.')  # keys that redirect a fetch or run a program
GIT_CONFIG_WRITES = {'--add', '--replace-all', '--unset', '--unset-all', '--rename-section', '--remove-section', '-e', '--edit'}
GIT_CONFIG_VERBS = {'set', 'unset', 'edit', 'rename-section', 'remove-section'}
GIT_CONFIG_READS = {'get', 'list'}
GIT_REMOTE_WRITES = {'add', 'set-url', 'rename', 'remove', 'rm', 'set-head', 'set-branches'}
KIT_BLOCKED = ('Blocked by the kit: this touches the kit folder "{}", the source of the next update, from another repo; '
               'reading it is fine. Change it yourself, or work on the kit from a session started in its folder.')
KIT_GIT_BLOCKED = ('Blocked by the kit: this changes the git configuration of the kit folder ("{}"), which the kit runs git in; '
                   'make the change yourself in a terminal.')
GITCONFIG_BLOCKED = ('Blocked by the kit: this git setting ("{}") can redirect where the kit fetches from or run a program; '
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

def in_kit(path, folder):
    """inside(), also without case: a path taken from a normalised command is lower case, the file system may not be."""
    return inside(path, folder) or inside(path.lower(), folder.lower())

def names_folder(text, forms):
    """The first form of the folder a normalised text names, whole (followed by /, a space, an operator or the end)."""
    return next((f for f in forms if re.search(re.escape(f) + r'(?=$|[/\s;|&()<>])', text)), None)

def names_kit_git(text, forms, here):
    """True when a normalised text names the kit's .git/config or .git/hooks (relatively too, when the shell is in the kit)."""
    targets = [f + '/' + g for f in forms for g in KIT_GIT]
    if any(re.search(re.escape(t) + r'(?=$|[/\s;|&()<>])', text) for t in targets):
        return True
    return here and any(re.search(r'(^|[\s=<>|;&(])(\./)?' + re.escape(g) + r'(?=$|[/\s;|&()<>])', text) for g in KIT_GIT)

def git_call(words):
    """(directory given by -C or None, subcommand, the words after it) of a git call; lower case: -C and -c look alike,
    told apart by their argument (-c takes key=value)."""
    directory, index = None, 0
    while index < len(words) and words[index].startswith('-'):
        if words[index] == '-c' and index + 1 < len(words):
            if '=' not in words[index + 1]:
                directory = words[index + 1]
            index += 2
            continue
        index += 1
    if index >= len(words):
        return directory, '', []
    return directory, words[index], words[index + 1:]

def git_config_reason(rest, target_in_kit):
    """Reason to refuse a `git config` call: a write of a key that redirects or runs (any scope), or any write of the kit's config."""
    flags = [w for w in rest if w.startswith('-')]
    positional = [w for w in rest if not w.startswith('-')]
    verb = positional[0] if positional and positional[0] in GIT_CONFIG_VERBS | GIT_CONFIG_READS else ''
    keys = positional[1:] if verb else positional
    if verb in GIT_CONFIG_READS or any(f.startswith('--get') or f in ('--list', '-l') for f in flags):
        return None
    writes = verb in GIT_CONFIG_VERBS or any(f in GIT_CONFIG_WRITES for f in flags) or len(keys) >= 2
    if not writes:
        return None
    scoped = any(f in ('--global', '--system', '--file', '-f') or f.startswith('--file=') for f in flags)
    if scoped and (any(f in ('-e', '--edit') for f in flags) or verb == 'edit' or (keys and GIT_CONFIG_SENSITIVE.match(keys[0]))):
        return GITCONFIG_BLOCKED.format(keys[0] if keys else 'git config --edit')
    if not scoped and target_in_kit:
        return KIT_GIT_BLOCKED.format('git config')
    return None

def where(word, current):
    """The folder a cd or -C word leads to, from the current one (~ expanded)."""
    word = word.strip('"\'')
    if word.startswith('~'):
        word = os.path.expanduser('~') + word[1:]
    return real(word if os.path.isabs(word) else os.path.join(current, word))

def kit_shell_reason(command, cwd):
    """Reason to refuse a shell command for the kit folder or git's configuration, or None."""
    folder, forms = kit_dir()
    current = real(cwd)
    session_in_kit = bool(folder) and inside(current, folder)
    for pipeline in shell_segments(command):
        text = normalised(pipeline)
        programs = command_words(text)
        for program, words in programs:
            if program in CHANGES_DIRECTORY and words:
                current = where(words[-1], current)
            if program != 'git':
                continue
            directory, subcommand, rest = git_call(words)
            target_in_kit = bool(folder) and in_kit(where(directory, current) if directory else current, folder)
            if subcommand == 'config':
                reason = git_config_reason(rest, target_in_kit)
                if reason:
                    return reason
            if subcommand == 'remote' and target_in_kit and rest and rest[0] in GIT_REMOTE_WRITES:
                return KIT_GIT_BLOCKED.format('git remote ' + rest[0])
        if not folder:
            continue
        here = in_kit(current, folder)
        if names_kit_git(text, forms, here):
            if re.search(r'>+\|?\s*\S*\.git/(config|hooks)', text) or not all(only_reads(p, w, lambda t: names_kit_git(t, forms, here)) for p, w in programs):
                return KIT_GIT_BLOCKED.format('.git/config')
        name = None if session_in_kit else names_folder(text, forms)
        if name:
            if re.search(r'>+\|?\s*' + re.escape(name) + r'(?=$|/)', text) or not all(only_reads(p, w, lambda t: names_folder(t, forms)) for p, w in programs):
                return KIT_BLOCKED.format(name)
    return None

def writes_kit_variables(text, programs, command):
    """True when a pipeline writes a .env file (a redirection, or a program that does not only read) and its words set the
    kit's variables: the content the write tools are refused for. An assignment before a program (AI_KIT_NO_LIVE=1 python3 …)
    is that program's environment, not content; the body of a heredoc is content."""
    def is_dotenv(word):
        return word.rsplit('/', 1)[-1].startswith('.env')
    written = any(is_dotenv(m.group(1)) for m in REDIRECTION.finditer(text)) or any(
        any(is_dotenv(w) for w in words) and not only_reads(program, words, is_dotenv) for program, words in programs if program != '=')
    if not written:
        return False
    content = normalised(command) if '<<' in text else ' '.join(' '.join(words) for program, words in programs if program != '=')
    return bool(SETS_KIT_VARIABLE.search(content))

def shell_config_write(command, cwd=None):
    """Reason for refusal when a shell command may change the configuration of the kit or of a CLI, or a repo's."""
    names = protected_names()
    if len(command) > MAX_COMMAND:
        whole = normalised(command)
        name = mention(whole, names) or next((f for f in CONFIG_FOLDERS if f in whole), None)
        return BLOCKED.format(name) if name else None
    reason = kit_shell_reason(command, cwd or os.getcwd()) or kit_command_reason(command, cwd or os.getcwd())
    if reason:
        return reason
    for pipeline in shell_segments(command):
        text = normalised(pipeline)
        programs = command_words(text)
        for program, words in programs:
            if touches_config_folder(program, words, names):
                return BLOCKED.format(next(f for f in CONFIG_FOLDERS if f in text))
        if '.env' in text and writes_kit_variables(text, programs, command):
            return DOTENV_BLOCKED
        name = mention(text, names)
        if not name:
            continue
        # A redirection to the protected file writes it, whatever the program.
        for match in REDIRECTION.finditer(text):
            if mention(match.group(1), names):
                return BLOCKED.format(name)
        def allowed(program, words):
            # '@' closes a PowerShell here-string piped into the program (/friction on Windows).
            return program == '@' or only_reads(program, words, lambda t: mention(t, names)) or runs_kit_tool(program, words, lambda t: mention(t, names))
        if not programs or any(p == '=' for p, _ in programs) or not all(allowed(p, w) for p, w in programs):
            return BLOCKED.format(name)
    return None

# --- A repo's protected paths in shell commands ------------------------------------------------------------------------

# Programs that change or delete the files they name. A closed list: a tool that regenerates a file without naming it
# (poetry lock, dbt run) is not read, and neither is a path kept in a variable, a wildcard or a script that writes.
WRITES_ALL = {'tee', 'rm', 'rmdir', 'unlink', 'shred', 'truncate', 'touch', 'chmod', 'chown', 'mv', 'rename',
              # cmd and PowerShell
              'del', 'erase', 'rd', 'move', 'ren', 'remove-item', 'ri', 'set-content', 'add-content', 'clear-content', 'out-file',
              'new-item', 'ni', 'move-item', 'mi', 'rename-item', 'rni'}
WRITES_LAST = {'cp', 'ln', 'install', 'rsync', 'copy', 'copy-item', 'cpi'}  # the destination is the last name
GIT_WRITES = {'checkout', 'restore', 'rm', 'mv', 'clean'}  # they replace or delete the files they name
REPO_BLOCKED = ('Blocked by the kit: this command changes or deletes "{}", which matches the protected path "{}" declared in the repo '
                'protected paths (.ai-kit/protected-paths). Reading it is fine. Propose the change to a person instead.')

def written_names(program, words):
    """The names a program of the closed list writes, among its words (lower case, quotes removed)."""
    names = [w for w in words if not w.startswith('-')]
    if program in WRITES_ALL:
        return names
    if program in WRITES_LAST:
        return names[-1:]
    if program == 'sed' and any(w.startswith(('-i', '--in-place')) or re.fullmatch(r'-[a-z]+i', w) for w in words):
        return names
    if program == 'perl' and any(re.fullmatch(r'-[a-z0-9]*i[a-z0-9.]*', w) for w in words):
        return names
    if program == 'dd':
        return [w[3:] for w in words if w.startswith('of=')]
    if program == 'git':
        _, subcommand, rest = git_call(words)
        return [w for w in rest if not w.startswith('-')] if subcommand in GIT_WRITES else []
    return []

def repo_pattern_of(name, cwd, directories):
    """(path relative to the folder, pattern) when this name, read from cwd, falls under a pattern a folder declares."""
    if name.startswith('~'):
        name = os.path.expanduser(name)
    absolute = os.path.normpath(name if os.path.isabs(name) else os.path.join(cwd, name)).replace(os.sep, '/').lower()
    for directory in directories:
        declared = patterns(directory)
        if not declared:
            continue
        for root in dict.fromkeys((real(directory), os.path.abspath(directory))):  # a temp folder behind a link (macOS /var)
            root = root.replace(os.sep, '/').lower().rstrip('/')
            if not absolute.startswith(root + '/'):
                continue
            relative = absolute[len(root) + 1:]
            for pattern in declared:
                if matches(relative, pattern):
                    return relative, pattern
    return None

def repo_shell_reason(command, cwd):
    """Reason for refusal when a shell command changes or deletes a file it names that the repo declares protected
    (.ai-kit/protected-paths): a redirection to it, or a program of the closed list. Anything unexpected lets it run."""
    try:
        if len(command) > MAX_COMMAND:
            return None
        directories = pattern_dirs(cwd)
        if not any(patterns(d) for d in directories):
            return None
        for pipeline in shell_segments(command):
            text = normalised(pipeline)
            targets = [m.group(1) for m in REDIRECTION.finditer(text)]
            for program, words in command_words(text):
                targets += written_names(program, words)
            for name in targets:
                found = repo_pattern_of(name, cwd, directories)
                if found:
                    return REPO_BLOCKED.format(*found)
    except Exception:
        return None
    return None

# --- Write tools -------------------------------------------------------------------------------------------------------

def real(path):
    """Absolute path with symbolic links resolved (a link to a protected folder is that folder)."""
    return os.path.realpath(os.path.abspath(path))

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

def check(file_path, cwd, content=''):
    """Reason for refusal if the file falls under a protected path, otherwise None. The repo is found from the file itself
    (and from the launch folder): a file of another repo keeps that repo's protection."""
    absolute = real(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    directories = list(dict.fromkeys(pattern_dirs(os.path.dirname(absolute)) + pattern_dirs(cwd)))
    reason = config_reason(absolute, directories, content)
    if reason:
        return reason
    folder, _ = kit_dir()
    if folder and any(inside(absolute, os.path.join(folder, *g.split('/'))) for g in KIT_GIT):
        return KIT_GIT_BLOCKED.format(os.path.relpath(absolute, folder).replace(os.sep, '/'))
    if folder and inside(absolute, folder) and not inside(real(cwd), folder):
        return KIT_BLOCKED.format(folder)
    for directory in directories:
        try:
            relative = os.path.relpath(absolute, real(directory)).replace(os.sep, '/')
        except ValueError:
            # Windows: a different drive from this folder, so outside its patterns.
            continue
        if relative == '..' or relative.startswith('../'):
            continue
        for pattern in patterns(directory):
            if not matches(relative, pattern):
                continue
            return 'Blocked by the kit: "' + relative + '" matches the protected path "' + pattern + '" declared in the repo protected paths (.ai-kit/protected-paths). Propose the change to a person instead of writing it.'
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
    required) and refuses an empty object without a reason; "allow" hands the call to agy's own permissions. The other
    CLIs read an empty object as nothing to say."""
    answer = dict(note or {})
    if isinstance(payload, dict) and 'toolCall' in payload:
        answer['decision'] = 'allow'
    return json.dumps(answer, ensure_ascii=False)

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
        # An unexpected input never lets a protected write through: refuse when the call names a protected path.
        text = normalised(json.dumps(payload))
        name = mention(text, [e.lower() for e in CONFIG_PATHS])
        decision = BLOCKED.format(name) if name else None
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
        return shell_config_write(command, folder) or repo_shell_reason(command, folder)
    if not re.search(r'write|replace|edit|patch', tool, re.I):
        return None
    paths = target_paths(tool, args)
    content = ' '.join(str(v) for k, v in (args.items() if isinstance(args, dict) else []) if k in ('content', 'new_string', 'CodeContent', 'ReplacementContent', 'edits'))
    for file_path in paths:
        decision = check(file_path, cwd, content)
        if decision:
            return decision
    return None

if __name__ == '__main__':
    main()
