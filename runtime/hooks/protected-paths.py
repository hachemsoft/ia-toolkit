#!/usr/bin/env python3
"""Gemini guardrail (BeforeTool, write_file|replace): blocks writes under a protected path.

Protected paths are glob patterns, one per line, in <repo>/.ai-kit/protected-paths (or the legacy <repo>/.gemini/protected-paths), comments with #.
Example: target/**  ·  models/legacy/**  ·  *.lock  ·  dbt_project.yml
Without a patterns file, everything is allowed. Output: JSON {"decision": "deny", "reason": ...} or {}.
"""
import fnmatch
import json
import os
import re
import sys

# Protected-paths file of a folder: .ai-kit/protected-paths (neutral, all CLIs), and the legacy .gemini/protected-paths, also read.
PATTERN_FILES = (os.path.join('.ai-kit', 'protected-paths'), os.path.join('.gemini', 'protected-paths'))

def patterns(directory):
    found = []
    for name in PATTERN_FILES:
        try:
            with open(os.path.join(directory, name), encoding='utf-8') as handle:
                found += [line.strip() for line in handle if line.strip() and not line.lstrip().startswith('#')]
        except OSError:
            continue
    return found

def pattern_dirs(cwd):
    """Folders whose protected-paths file applies: from the launch folder up to the repo root
    (the first folder that contains .git). A monorepo started from a subfolder stays protected by the root."""
    dirs, current = [], os.path.abspath(cwd)
    while True:
        dirs.append(current)
        if os.path.exists(os.path.join(current, '.git')):
            return dirs
        parent = os.path.dirname(current)
        if parent == current:
            return [os.path.abspath(cwd)]
        current = parent

def matches(relative, pattern):
    # '**' also covers zero folders; fnmatch does not do that on its own. Case-insensitive comparison (macOS, Windows).
    relative, pattern = relative.lower(), pattern.lower()
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
    """Files a tool call will write: a direct path (Gemini, agy, CLIs using the Write/Edit format) or the headers of a patch (Codex apply_patch)."""
    if not isinstance(args, dict):
        args = {'input': args}
    for key in ('file_path', 'TargetFile', 'AbsolutePath', 'FilePath', 'path', 'Path'):
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

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash')

# Shell operations that change a file; reading (cat, less, grep) stays allowed.
WRITE_COMMANDS = re.compile(r'(\btee\b|\bsed\b[^|;&]*\s(-[a-z]*i\b|--in-place)|\b(cp|mv|rm|chmod|chown|truncate|ln|dd|install|del|erase)\b'
                            r'|\b(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|Rename-Item)\b)', re.I)

def shell_config_write(command):
    """Reason for refusal when a shell command writes to the kit or CLI configuration (simple cases: redirection, tee, sed -i, cp, mv, rm…)."""
    text = command.replace('\\', '/')
    for entry in CONFIG_PATHS + ('.ai-kit/protected-paths',):
        name = re.escape(entry.rstrip('/'))
        if not re.search(name, text, re.I):
            continue
        redirected = re.search(r'>>?\s*["\']?[^\s;|&]*' + name, text, re.I)
        if redirected or WRITE_COMMANDS.search(text):
            return ('Blocked by the kit: this command changes "' + entry.rstrip('/') + '", configuration of the kit or of a CLI; '
                    'the agent does not change it. Tell the person what to change (then run update).')
    return None

def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    # Input shapes: Gemini CLI (tool_name / tool_input.file_path), Antigravity (toolCall.name / toolCall.args.TargetFile...),
    # Codex (hook_event_name PreToolUse, apply_patch whose paths are in the patch headers).
    call = payload.get('toolCall') or {}
    tool = str(payload.get('tool_name') or call.get('name') or '')
    if tool in SHELL_TOOLS:
        args = payload.get('tool_input') or call.get('args') or {}
        if not isinstance(args, dict):
            args = {'command': args}
        reason = shell_config_write(as_text(args.get('command') or args.get('cmd') or args.get('CommandLine')))
        print(json.dumps(deny_output(payload, reason), ensure_ascii=False) if reason else '{}')
        return
    if not re.search(r'write|replace|edit|patch', tool, re.I):
        print('{}')
        return
    args = payload.get('tool_input') or call.get('args') or {}
    paths = target_paths(tool, args)
    workspace = (payload.get('workspacePaths') or [None])[0]
    cwd = payload.get('cwd') or workspace or os.getcwd()
    if not paths:
        print('{}')
        return
    for file_path in paths:
        decision = check(file_path, cwd)
        if decision:
            print(json.dumps(deny_output(payload, decision), ensure_ascii=False))
            return
    print('{}')

# Configuration of the kit and of the CLIs, always protected: an agent must not be able to switch off its own guardrails.
# Relative to the home folder; a trailing / protects a whole folder. ~/.ai-kit/learn/ (personal /learn progress) stays writable.
CONFIG_PATHS = ('.ai-kit/overrides.json', '.ai-kit/state.json', '.ai-kit/hooks/', '.ai-kit/bin/', '.ai-kit/backups/', '.ai-kit/context/00_',
                '.ai-kit/context/10_', '.ai-kit/context/20_', '.gemini/settings.json', '.gemini/.env', '.gemini/config/plugins/ai-kit/',
                '.codex/config.toml', '.codex/AGENTS.md')

def real(path):
    """Absolute path with symbolic links resolved (a link to a protected folder is that folder)."""
    return os.path.realpath(os.path.abspath(path))

def config_reason(absolute, directories):
    home = real(os.path.expanduser('~'))
    try:
        relative = os.path.relpath(absolute, home).replace(os.sep, '/')
    except ValueError:
        relative = '..'
    if not relative.startswith('..'):
        for entry in CONFIG_PATHS:
            if relative.lower() == entry.lower().rstrip('/') or relative.lower().startswith(entry.lower()):
                return 'Blocked by the kit: "~/' + relative + '" is configuration of the kit or of a CLI; the agent does not change it. Make the change yourself (then run update).'
    for directory in directories:
        if absolute.lower() == os.path.join(real(directory), '.ai-kit', 'protected-paths').lower():
            return 'Blocked by the kit: the repo protected paths (.ai-kit/protected-paths) are changed by a person, through a merge request.'
    return None

def check(file_path, cwd):
    """Reason for refusal if the file falls under a protected path, otherwise None."""
    absolute = real(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    directories = pattern_dirs(cwd)
    reason = config_reason(absolute, directories)
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

if __name__ == '__main__':
    main()
