#!/usr/bin/env python3
"""Gemini guardrail (BeforeTool, run_shell_command): blocks a dbt command aimed at a production target.

One-off permission: AI_KIT_ALLOW_PROD=1 exported in the shell that starts the CLI (ignored when it comes from a .env file the CLI loads,
which the agent could write). A target only known at run time ($VAR, $(…)) is blocked.
Targets treated as production: prod, production, prd, or the AI_KIT_PROD_TARGETS list (comma-separated).
Output: JSON {"decision": "deny", "reason": ...} or {} to let it through. Never an exception towards Gemini.
"""
import json
import os
import re
import sys

class _Hit:
    def __init__(self, target):
        self._target = target
    def group(self, _index):
        return self._target

def default_target_hit(command, targets, payload):
    """Without --target or DBT_TARGET, the default target comes from profiles.yml (--profiles-dir, DBT_PROFILES_DIR, ~/.dbt): block it if it is production."""
    if re.search(r'(?:--target|-t)(?:[\s=]|$)|\bDBT_TARGET=', command, re.I):
        return None
    match = re.search(r'--profiles-dir[\s=]+[\'"]?([^\s\'"]+)', command)
    cwd = payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()
    candidates = []
    if match:
        candidates.append(os.path.join(cwd, match.group(1)) if not os.path.isabs(match.group(1)) else match.group(1))
    if os.environ.get('DBT_PROFILES_DIR'):
        candidates.append(os.environ['DBT_PROFILES_DIR'])
    candidates += [cwd, os.path.join(os.path.expanduser('~'), '.dbt')]
    for directory in candidates:
        path = os.path.join(directory, 'profiles.yml')
        try:
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
        except OSError:
            continue
        # Minimal reading without PyYAML: the `target: <name>` lines indented one level under a profile.
        for found in re.findall(r'^[ \t]+target:[ \t]*[\'"]?([A-Za-z0-9_-]+)', text, re.M):
            if found.lower() in targets:
                return _Hit(found + ' (default target from ' + path + ')')
        return None
    return None

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

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash')

def use_utf8():
    """The CLIs send and read UTF-8; on Windows the console defaults to cp1252: force UTF-8 for input and output."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

def unreadable_target(command):
    """Target value that is only resolved by the shell ($VAR, $(…), backticks, glued quotes): unknown, so treated as unsafe."""
    for match in re.finditer(r'(?:(?<![\w-])--target|(?<![\w-])-t|\bDBT_TARGET)(?:[\s=]+|(?<=-t))(\S+)', command):
        value = match.group(1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        if re.search(r'[$`"\']', value):
            return match.group(1)
    return None

def allow_from_env_file(payload):
    """File that sets AI_KIT_ALLOW_PROD among the .env files Gemini loads (repo folders up to the root, then ~/.gemini/.env), or None."""
    cwd = payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()
    candidates, current = [], os.path.abspath(cwd)
    while True:
        candidates += [os.path.join(current, '.gemini', '.env'), os.path.join(current, '.env')]
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    candidates.append(os.path.join(os.path.expanduser('~'), '.gemini', '.env'))
    for path in candidates:
        try:
            with open(path, encoding='utf-8', errors='replace') as handle:
                if re.search(r'^\s*(export\s+)?AI_KIT_ALLOW_PROD\s*=', handle.read(), re.M):
                    return path
        except OSError:
            continue
    return None

def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    # Three input shapes: Gemini CLI (tool_name / tool_input.command), Antigravity (toolCall.name / toolCall.args.CommandLine),
    # Codex (hook_event_name PreToolUse, tool_name / tool_input.command as a string or a list).
    call = payload.get('toolCall') or {}
    tool = payload.get('tool_name') or call.get('name')
    if tool not in SHELL_TOOLS:
        print('{}')
        return
    args = payload.get('tool_input') or call.get('args') or {}
    if not isinstance(args, dict):
        args = {'command': args}
    command = as_text(args.get('command') or args.get('cmd') or args.get('CommandLine'))
    # `dbt`, `./dbt`, `/path/dbt`, `dbt.exe`, any case; also right after a quote, a backtick or a parenthesis (`sh -c "dbt …"`, `$(dbt …)`).
    if not re.search(r'(^|[\s;&|/\\"\'`(])dbt(\.exe)?(\s|$|["\'`)])', command, re.I):
        print('{}')
        return
    targets = [t.strip().lower() for t in os.environ.get('AI_KIT_PROD_TARGETS', 'prod,production,prd').split(',') if t.strip()]
    alternation = '|'.join(re.escape(t) for t in targets)
    # --target prod, --target=prod, -t prod, -tprod, single or double quotes around the value.
    hits = (re.search(r'(?:--target|-t)(?:[\s=]+|(?<=-t))[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I)
            or re.search(r'\bDBT_TARGET=[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I))
    if not hits:
        unreadable = unreadable_target(command)
        if unreadable:
            print(json.dumps(deny_output(payload, 'Blocked by the kit: the dbt target "' + unreadable + '" is only known when the command runs, so the kit cannot tell whether it is production. Write the target in plain text, for example --target dev.'), ensure_ascii=False))
            return
        hits = default_target_hit(command, targets, payload)
    if not hits:
        print('{}')
        return
    if os.environ.get('AI_KIT_ALLOW_PROD') == '1':
        origin = allow_from_env_file(payload)
        if not origin:
            print(json.dumps({'systemMessage': 'ai-kit: dbt command on a production target allowed by AI_KIT_ALLOW_PROD=1.'}))
            return
        print(json.dumps(deny_output(payload, 'Blocked by the kit: AI_KIT_ALLOW_PROD is set in ' + origin + ', a file the agent can write. Export it in the shell that starts the CLI instead.'), ensure_ascii=False))
        return
    print(json.dumps(deny_output(payload, 'Blocked by the kit: dbt command on the production target "' + hits.group(1) + '". Use the development target declared in AGENTS.md. An authorised person can export AI_KIT_ALLOW_PROD=1 for this session.'), ensure_ascii=False))

if __name__ == '__main__':
    main()
