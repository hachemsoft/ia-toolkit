#!/usr/bin/env python3
"""Kit guardrail (before a tool call): refuses a write tool aimed at the configuration of the kit or of a CLI (the path is
exact), and the kit's own commands that change the installation or bill a model call. It reads no other shell command:
what a command changes is reported by the integrity check after the tool call and at session start (ADR 0030).
Output: JSON {"decision": "deny", "reason": ...} or {} ({"decision": "ask"} for agy).
"""
import json
import os
import re
import sys
import time

# --- Configuration -----------------------------------------------------------------------------------------------

# Configuration of the kit and of the CLIs, always protected: an agent must not be able to switch off its own guardrails.
# Relative to the home folder; a trailing / protects a whole folder. ~/.ai-kit/learning/ (personal /learn progress) and
# ~/.ai-kit/context/USER.md (the person's own file) stay writable. Every file the kit installed (state.json) is protected too.
CONFIG_PATHS = ('.ai-kit/aikit.toml', '.ai-kit/lock.toml', '.ai-kit/sources/', '.ai-kit/state.json', '.ai-kit/hooks/', '.ai-kit/bin/', '.ai-kit/backups/',
                '.ai-kit/runtime/', '.ai-kit/schemas/', '.ai-kit/context/00_', '.ai-kit/context/10_', '.ai-kit/context/20_',
                # the news the session hook shows (their text enters the next session) and its marker
                '.ai-kit/news/', '.ai-kit/news.json', '.ai-kit/integrity.json',
                '.gemini/00_', '.gemini/10_', '.gemini/20_', '.gemini/settings.json', '.gemini/.env', '.gemini/config/plugins/ai-kit/',
                '.gemini/antigravity-cli/settings.json',  # agy's permissions: the person's answers, never the agent's
                '.codex/config.toml', '.codex/AGENTS.md', '.codex/ai-kit/', '.claude/settings.json', '.claude/CLAUDE.md', '.claude/agents/ai-kit-',
                '.claude.json',
                # git's own configuration can redirect the kit's next fetch (url.insteadOf) or run a program (core.fsmonitor) (0.51.1).
                '.gitconfig', '.config/git/config')

# Configuration of a repo, protected in every repo: a project setting can turn hooks off or change the environment the
# guardrails read (a .env setting the kit's variables is refused through its content).
REPO_CONFIG = ('.claude/settings.json', '.claude/settings.local.json',
               '.gemini/settings.json', '.gemini/.env', '.codex/config.toml')

KIT_VARIABLES = re.compile(r'^\s*(export\s+)?(AI_KIT_[A-Z_]*|DBT_TARGET)\s*=', re.M)

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

CHANGES_DIRECTORY = {'cd', 'pushd', 'chdir', 'set-location', 'sl', 'push-location'}

HEREDOC = re.compile(r'<<-?\s*["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?')

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

PYTHONS = re.compile(r'(python[0-9.]*|py)(\.exe)?')

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

def in_kit(path, folder):
    """inside(), also without case: a path taken from a normalised command is lower case, the file system may not be."""
    return inside(path, folder) or inside(path.lower(), folder.lower())

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

def check(file_path, cwd, content=''):
    """Reason for refusal if a write tool's file is protected configuration, otherwise None. The repo is found from the
    file itself (and from the launch folder): a file of another repo keeps that repo's CLI settings protected."""
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
    content = ' '.join(str(v) for k, v in (args.items() if isinstance(args, dict) else []) if k in ('content', 'new_string', 'CodeContent', 'ReplacementContent', 'edits'))
    for file_path in paths:
        decision = check(file_path, cwd, content)
        if decision:
            return decision
    return None

if __name__ == '__main__':
    main()
