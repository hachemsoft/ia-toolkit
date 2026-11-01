#!/usr/bin/env python3
"""Kit guardrail (before a tool call): blocks agent writes to the configuration of the kit and of the CLIs, and under the
paths a repo protects.

Protected paths of a repo are glob patterns, one per line, in <repo>/.ai-kit/protected-paths (or the legacy
<repo>/.gemini/protected-paths), comments with #. Example: target/**  ·  models/legacy/**  ·  *.lock  ·  dbt_project.yml
A shell command that names a protected path is allowed only when every program it runs only reads (cat, grep, ls…):
the list of what is allowed is closed, not the list of what writes. Output: JSON {"decision": "deny", "reason": ...} or {}.
"""
import fnmatch
import json
import os
import re
import sys

# Protected-paths file of a folder: .ai-kit/protected-paths (neutral, all CLIs), and the legacy .gemini/protected-paths, also read.
PATTERN_FILES = (os.path.join('.ai-kit', 'protected-paths'), os.path.join('.gemini', 'protected-paths'))

# Configuration of the kit and of the CLIs, always protected: an agent must not be able to switch off its own guardrails.
# Relative to the home folder; a trailing / protects a whole folder. ~/.ai-kit/learning/ (personal /learn progress) and
# ~/.ai-kit/context/30_USER.md (the person's own file) stay writable. Every file the kit installed (state.json) is protected too.
CONFIG_PATHS = ('.ai-kit/overrides.toml', '.ai-kit/overrides.json', '.ai-kit/state.json', '.ai-kit/hooks/', '.ai-kit/bin/', '.ai-kit/backups/',
                '.ai-kit/runtime/', '.ai-kit/schemas/', '.ai-kit/context/00_', '.ai-kit/context/10_', '.ai-kit/context/20_',
                '.gemini/00_', '.gemini/10_', '.gemini/20_', '.gemini/settings.json', '.gemini/.env', '.gemini/config/plugins/ai-kit/',
                '.codex/config.toml', '.codex/AGENTS.md', '.codex/ai-kit/', '.claude/settings.json', '.claude/CLAUDE.md', '.claude/agents/ai-kit-',
                '.claude.json')
# The folders that hold that configuration: a `cd` into one of them, or a wildcard inside one, is treated as touching it.
CONFIG_FOLDERS = ('.ai-kit', '.gemini', '.codex', '.claude')
# Configuration of a repo, protected in every repo: a project setting can turn hooks off or change the environment the
# guardrails read (a .env setting the kit's variables is refused through its content).
REPO_CONFIG = ('.ai-kit/protected-paths', '.gemini/protected-paths', '.claude/settings.json', '.claude/settings.local.json',
               '.gemini/settings.json', '.gemini/.env', '.codex/config.toml')
KIT_VARIABLES = re.compile(r'^\s*(export\s+)?(AI_KIT_[A-Z_]*|DBT_TARGET)\s*=', re.M)

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
    return tuple(rel for rel in files if isinstance(rel, str) and not rel.endswith('/30_USER.md'))

# --- Shell commands ---------------------------------------------------------------------------------------------------

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash',
               'PowerShell', 'powershell')
# Programs that only read: a command naming a protected path is allowed only when it runs nothing else.
READERS = {'cat', 'bat', 'less', 'more', 'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack', 'ls', 'll', 'dir', 'stat', 'file',
           'wc', 'diff', 'cmp', 'md5', 'md5sum', 'shasum', 'sha1sum', 'sha256sum', 'jq', 'yq', 'column', 'sort', 'uniq', 'cut', 'nl', 'od',
           'xxd', 'hexdump', 'strings', 'tree', 'realpath', 'readlink', 'basename', 'dirname', 'test', '[', 'echo', 'printf', 'true',
           'type', 'which', 'find', 'sed', 'awk', 'git', 'cp',
           # PowerShell
           'get-content', 'gc', 'select-string', 'sls', 'get-childitem', 'gci', 'test-path', 'get-item', 'gi', 'get-filehash',
           'resolve-path', 'measure-object', 'write-output', 'write-host', 'out-string', 'format-list', 'select-object'}
GIT_READS = {'status', 'diff', 'log', 'show', 'blame', 'ls-files', 'grep', 'rev-parse', 'cat-file', 'describe'}
WRAPPERS = {'sudo', 'doas', 'env', 'xargs', 'nohup', 'time', 'command', 'exec', 'builtin', 'nice', '-exec', '-execdir', '-ok'}
RUNS_TEXT = re.compile(r'-[a-z]*c|-command|-encodedcommand', re.I)  # bash -c, sh -lc, pwsh -Command: the next word is run
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'pwsh', 'powershell'}
CHANGES_DIRECTORY = {'cd', 'pushd', 'chdir', 'set-location', 'sl', 'push-location'}
HEREDOC = re.compile(r'<<-?\s*["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?')
MAX_COMMAND = 50000  # longer: judged on its own (a pathological command is refused when it names a protected path)
BLOCKED = ('Blocked by the kit: this command touches "{}", configuration of the kit or of a CLI; the agent does not change it. '
           'Reading it with cat, grep or ls is fine. Tell the person what to change (then run update).')

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
            if (current in SHELLS and RUNS_TEXT.fullmatch(core)) or core in ('-exec', '-execdir', '-ok'):
                expect = True  # bash -c '…', find … -exec: what follows is run
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
    if program == 'sed':
        # In place, or a script that writes a file or runs a command (w, W, e, s///w).
        return not any(re.match(r'-[a-z]*i|--in-place', w, re.I) or re.fullmatch(r'(\d+|\$|/[^/]*/)?[we]', w)
                       or re.fullmatch(r's(.).*\1.*\1[a-z0-9]*w[a-z0-9]*', w) for w in words)
    if program == 'awk':
        return not any('inplace' in w or 'system(' in w or '|' in w for w in words)
    if program == 'find':
        return not any(w in ('-delete', '-exec', '-execdir', '-ok', '-okdir', '-fprint', '-fprint0', '-fprintf', '-fls') for w in words)
    if program == 'git':
        subcommand = next((w for w in words if not w.startswith('-') and w not in ('-c',)), '')
        return subcommand in GIT_READS and not any(w.startswith('--output') for w in words)
    if program == 'cp':
        if any(w == '-t' or w.startswith('--target-directory') for w in words):
            return False
        return bool(positional) and not mentions_in(positional[-1])
    # Readers that also write a file when asked to: their output option, or a second file name.
    if program in ('sort', 'tree'):
        return not any(w.startswith('-o') or w.startswith('--output') for w in words)
    if program == 'uniq':
        return len(positional) < 2
    if program == 'xxd':
        return '-r' not in words and len(positional) < 2
    if program == 'yq':
        return not any(w in ('-i', '--inplace') for w in words)
    return True

PYTHONS = re.compile(r'(python[0-9.]*|py)(\.exe)?')
KIT_TOOLS = ('/.ai-kit/bin/friction.py',)  # run by the kit's own commands (/friction): they write only outside the protected paths

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

def touches_config_folder(program, words):
    """cd into a configuration folder, a wildcard inside one, or a program that is not a reader aimed at the folder itself
    (ln -s ~/.ai-kit x, rm -rf ~/.claude): what follows cannot be judged, so it counts as a write."""
    def is_folder(word):
        return any(word.rstrip('/').endswith('/' + f) or word.rstrip('/') == f for f in CONFIG_FOLDERS)
    if program in CHANGES_DIRECTORY and words:
        last = words[-1].rstrip('/')
        if is_folder(last) or any('/' + folder + '/' in last + '/' for folder in CONFIG_FOLDERS):
            return True
    if program not in READERS and program != '=' and any(is_folder(w) for w in words):
        return True
    # cp into a configuration folder (cp overrides.toml ~/.ai-kit/, cp -t ~/.ai-kit x): the file it writes is not named.
    if program == 'cp':
        destinations = [w.split('=', 1)[-1] for w in words if w.startswith('--target-directory')]
        destinations += [words[i + 1] for i, w in enumerate(words[:-1]) if w == '-t']
        positional = [w for w in words if not w.startswith('-')]
        destinations += positional[-1:] if len(positional) >= 2 else []
        if any(is_folder(d) for d in destinations):
            return True
    return any(re.search(r'[*?\[]', w) and any('/' + f + '/' in '/' + w for f in CONFIG_FOLDERS) for w in words)

def shell_config_write(command):
    """Reason for refusal when a shell command may change the configuration of the kit or of a CLI, or a repo's."""
    names = protected_names()
    if len(command) > MAX_COMMAND:
        whole = normalised(command)
        name = mention(whole, names) or next((f for f in CONFIG_FOLDERS if f in whole), None)
        return BLOCKED.format(name) if name else None
    for pipeline in shell_segments(command):
        text = normalised(pipeline)
        programs = command_words(text)
        for program, words in programs:
            if touches_config_folder(program, words):
                return BLOCKED.format(next(f for f in CONFIG_FOLDERS if f in text))
        name = mention(text, names)
        if not name:
            continue
        # A redirection to the protected file writes it, whatever the program.
        for match in re.finditer(r'>+\|?\s*([^\s;|&<>]+)', text):
            if mention(match.group(1), names):
                return BLOCKED.format(name)
        def allowed(program, words):
            # '@' closes a PowerShell here-string piped into the program (/friction on Windows).
            return program == '@' or only_reads(program, words, lambda t: mention(t, names)) or runs_kit_tool(program, words, lambda t: mention(t, names))
        if not programs or any(p == '=' for p, _ in programs) or not all(allowed(p, w) for p, w in programs):
            return BLOCKED.format(name)
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
                return 'Blocked by the kit: "~/' + relative + '" is configuration of the kit or of a CLI; the agent does not change it. Make the change yourself (then run update).'
    for directory in directories:
        try:
            inner = os.path.relpath(absolute, real(directory)).replace(os.sep, '/').lower()
        except ValueError:
            continue
        if inner in REPO_CONFIG:
            return ('Blocked by the kit: "' + inner + '" configures the repo\'s guardrails or agent settings; a person changes it, '
                    'through a merge request.')
    if os.path.basename(absolute).lower().startswith('.env') and KIT_VARIABLES.search(content):
        return 'Blocked by the kit: a .env file the agent writes must not set the kit\'s variables (AI_KIT_*) or DBT_TARGET.'
    return None

def check(file_path, cwd, content=''):
    """Reason for refusal if the file falls under a protected path, otherwise None. The repo is found from the file itself
    (and from the launch folder): a file of another repo keeps that repo's protection."""
    absolute = real(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    directories = list(dict.fromkeys(pattern_dirs(os.path.dirname(absolute)) + pattern_dirs(cwd)))
    reason = config_reason(absolute, directories, content)
    if reason:
        return reason
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
    print(json.dumps(deny_output(payload, decision), ensure_ascii=False) if decision else '{}')

def decide(payload):
    # Input shapes: Gemini CLI (tool_name / tool_input.file_path), Antigravity (toolCall.name / toolCall.args.TargetFile...),
    # Codex (hook_event_name PreToolUse, apply_patch whose paths are in the patch headers), Claude Code (Bash, PowerShell, Write…).
    call = payload.get('toolCall') or {}
    tool = str(payload.get('tool_name') or call.get('name') or '')
    args = payload.get('tool_input') or call.get('args') or {}
    if tool in SHELL_TOOLS:
        if not isinstance(args, dict):
            args = {'command': args}
        return shell_config_write(as_text(args.get('command') or args.get('cmd') or args.get('CommandLine')))
    if not re.search(r'write|replace|edit|patch', tool, re.I):
        return None
    paths = target_paths(tool, args)
    workspace = (payload.get('workspacePaths') or [None])[0]
    cwd = payload.get('cwd') or workspace or os.getcwd()
    content = ' '.join(str(v) for k, v in (args.items() if isinstance(args, dict) else []) if k in ('content', 'new_string', 'CodeContent', 'ReplacementContent', 'edits'))
    for file_path in paths:
        decision = check(file_path, cwd, content)
        if decision:
            return decision
    return None

if __name__ == '__main__':
    main()
