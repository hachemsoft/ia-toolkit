"""Antigravity CLI (agy) adapter: plugin ~/.gemini/config/plugins/ai-kit (rules, agents, guardrails, MCP) and command skills."""
import contextlib
import json
import re
import shutil
import subprocess

from pathlib import Path
from typing import Optional

from . import gemini
from ..interface import DoctorContext, Plan, Status
from ..core import (ROOT, USER_CONTEXT, json_bytes, hook_command, command_skill_text, skill_prefix, free_name, rename_references,
                    renamed_notice, live_call, LIVE_PROMPT, skills_read)

AGY_PLUGIN = '.gemini/config/plugins/ai-kit'

def agy_rules_text(context_names, context_dir='.gemini'):
    lines = ['# AI Kit', '', 'Always-on kit rules, shared with the other CLIs. The files included below are the source: do not copy them here.', '']
    for name in list(context_names)+[USER_CONTEXT]:
        lines.append('@['+name[:-3].lower()+'](~/'+context_dir+'/'+name+')')
        lines.append('')
    lines += ['Kit commands: each command is a skill with the same name; `/guide` explains where to start. Also read `AGENTS.md`, `GLOSSARY.md` and `REVIEW.md` in the current repo.']
    return '\n'.join(lines)+'\n'

# --- Adapter interface ---------------------------------------------------------------------------------------------
NAME = 'agy'
LABEL = 'Antigravity CLI'
COMMAND = 'agy'
HOME_DIR = '.gemini'
BUILTIN_COMMANDS = {'help', 'planning', 'agents', 'model', 'models', 'permissions', 'config', 'diff', 'keybindings', 'remote-control', 'login', 'logout', 'clear', 'quit', 'exit'}
MANAGED_PREFIXES = (AGY_PLUGIN+'/',)
AGENT_TOOLS = 'native'  # agy reads "tools" in an agent's header (a field of its agent definitions, read on agy 1.4.12)
# The kit's tool names (Gemini's) in agy's: one kit tool can be several in agy.
AGY_TOOLS = {'read_file': ['view_file', 'read_file'], 'grep_search': ['grep_search'], 'list_directory': ['list_dir', 'find_by_name'],
             'run_shell_command': ['run_command', 'command_status']}
# history.jsonl holds the prompts; each conversation (SQLite, one row per step) holds the tool calls with their JSON
# arguments: skill files read, invoke_subagent with the agent's TypeName (format read on agy 1.4.12).
OBSERVES = {'prompt', 'skill', 'agent'}
AGENT_CALL = re.compile(rb'\{[^{}]*"TypeName"\s*:\s*"(ai-kit-[a-z0-9-]+)"[^{}]*\}')
# A file-read call and its arguments; the conversation's other steps (context, listings) also name skill paths.
SKILL_CALL = re.compile(rb'(?:read_file|view_file)[^{]{0,8}(\{[^{}]*SKILL\.md[^{}]*\})')

def is_managed(rel):
    return rel.startswith(MANAGED_PREFIXES)

def active_account(home):
    return None

def doctor_hint():
    return None

def present(home):
    return bool(shutil.which('agy')) or (home/'.gemini/config').is_dir()

agy_present = present

def install(p: Plan) -> None:
    """ai-kit plugin (rules that include the layers by path, agents, guardrails, MCP) and command skills."""
    plugin = p.home/AGY_PLUGIN
    manifest_json = {'name': 'ai-kit', 'displayName': 'AI Kit', 'description': 'AI Kit context, commands, guardrails and agents, shared with the other CLIs.', 'version': (ROOT/'VERSION').read_text(encoding='utf-8').strip()}
    p.managed_write(plugin/'plugin.json', json_bytes(manifest_json), 'Plugin agy')
    p.managed_write(plugin/'rules'/'AGENTS.md', agy_rules_text(p.context_names, p.context_dir.relative_to(p.home).as_posix()).encode('utf-8'), 'Plugin agy')
    if gemini.NAME not in p.active:
        # agy reads skills from ~/.gemini/skills: without Gemini, put them there.
        gemini.write_skills(p)
    names = gemini.skill_names(p)
    # A command skill lives in the plugin; one of the person's skills with its name in ~/.gemini/skills would be ambiguous in agy.
    personal = p.home/'.gemini'/'skills'
    commands = {c['name']: free_name(c['name'], lambda n: personal/n, lambda n: '.gemini/skills/'+n, p.old_files, skill_prefix(p.overrides), 'command')
                for c in p.commands if c['name'] not in p.selected}
    mapping = {**{o: n for o, n in names.items() if o != n}, **{o: n for o, n in commands.items() if o != n}}
    for command in p.commands:
        if command['name'] in p.selected:
            continue  # a skill with the same name already exists: it serves as the command in agy
        # In the plugin, not in the shared ~/.gemini/skills: Gemini CLI would turn it into a second /<command> next to its own.
        named = {**command, 'name': commands[command['name']], 'prompt': rename_references(command['prompt'], mapping)}
        p.managed_write(plugin/'skills'/named['name']/'SKILL.md', command_skill_text(named).encode('utf-8'), 'Command skill')
    for agent, definition in p.agents:
        # agy reads the "tools" of an agent's header with its own tool names (checked on agy 1.4.12).
        p.managed_write(plugin/'agents'/('ai-kit-'+agent+'.md'), gemini.agent_markdown(p, agent, definition, AGY_TOOLS), 'Plugin agy')
    notice = renamed_notice(LABEL, names if gemini.NAME not in p.active else {}, commands)
    if notice:
        p.notices.append(notice)
    agy_hooks = {}
    for name, spec in p.hook_manifest.items():
        script = p.hooks_dir/spec['script']
        # agy tool names: run_command for the shell, *write*/*replace*/*edit* for file writes.
        parts = spec['matcher'].split('|')
        matcher = '|'.join((['.*(write|replace|edit).*'] if any(p != 'run_shell_command' for p in parts) else []) + (['run_command'] if 'run_shell_command' in parts else []))
        agy_hooks['ai-kit-'+name] = {'enabled': name in p.enabled_hooks, 'PreToolUse': [{'matcher': matcher, 'hooks': [{'type': 'command', 'command': hook_command(script), 'timeout': 20}]}]}
    p.managed_write(plugin/'hooks.json', json_bytes(agy_hooks), 'Plugin agy')
    if p.enabled_mcp:
        p.managed_write(plugin/'mcp_config.json', json_bytes({'mcpServers': p.enabled_mcp}), 'Plugin agy')

def finalize(p: Plan, active: bool = True) -> None:
    return None

def summary(p: Plan) -> Optional[str]:
    return 'Antigravity: ai-kit plugin installed in ~/'+AGY_PLUGIN+' (restart agy to see it).'

def doctor(home: Path, state: dict, status: Status, ctx: DoctorContext) -> None:
    plugin_dir = home/AGY_PLUGIN
    if not plugin_dir.is_dir():
        return
    if shutil.which('agy'):
        try:
            proc = subprocess.run(['agy','plugin','validate',str(plugin_dir)],capture_output=True,text=True,encoding='utf-8',timeout=60)
            status('Validation passed' in proc.stdout+proc.stderr,'Antigravity ai-kit plugin valid (agy plugin validate)')
        except (OSError, subprocess.SubprocessError):
            print('[Info] agy plugin validate could not be run.')
    else:
        print('[Info] Antigravity plugin installed; agy not on the PATH, validation not done.')

LIVE_RULES = (
    (r'not (authenticated|logged in|signed in)|please (log|sign) in|login required|unauthenticated|401', 'agy is not signed in.', 'Start agy and sign in with your Google account, or use the Google Cloud project your IT procedure gives (see docs/cli/agy.md).'),
    (r'RESOURCE_EXHAUSTED|quota|429', 'agy quota reached.', 'Wait, or ask for a higher quota on the project.'),
    (r'PERMISSION_DENIED|403|has not been used in project', 'Access denied by the API (HTTP 403): the API or the IAM right is missing on the project.', 'Ask the project administrator; docs/cli/agy.md lists what the project needs.'),
)

def live(home):
    """doctor --live: one real call with agy in print mode; 0 when the model answers."""
    return live_call(home, NAME, LABEL, [COMMAND, '-p', LIVE_PROMPT, '--print-timeout', '90s'], LIVE_RULES)

def history(home, state):
    """~/.gemini/antigravity-cli/history.jsonl: one JSON line per typed prompt (display, timestamp in ms, conversationId)."""
    path = home/'.gemini/antigravity-cli/history.jsonl'
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        stamp = entry.get('timestamp', 0)
        if not isinstance(stamp, (int, float)):
            continue
        yield {'kind': 'prompt', 'session': ('agy:'+str(entry['conversationId'])) if entry.get('conversationId') else None, 'ts': stamp/1000, 'text': str(entry.get('display', '')).strip()}
    yield from conversation_events(home, state)

def conversation_events(home, state):
    """~/.gemini/antigravity-cli/conversations/<id>.db, opened read-only: kit skills read and ai-kit-* agents invoked,
    dated by the conversation's last write (the steps' own times are not readable)."""
    import sqlite3
    kit_skills = set((state.get('installed') or {}).get('skills', []))
    for path in sorted((home/'.gemini/antigravity-cli/conversations').glob('*.db')):
        session, ts = 'agy:'+path.stem, path.stat().st_mtime
        try:
            with contextlib.closing(sqlite3.connect('file:'+path.as_posix()+'?mode=ro', uri=True)) as db:
                payloads = [row[0] for row in db.execute('select step_payload from steps order by idx') if isinstance(row[0], bytes)]
        except sqlite3.Error:
            continue  # another format, or a conversation being written: left out
        seen = set()  # a call's arguments can be stored again in a later step: one event per distinct call
        for payload in payloads:
            for match in AGENT_CALL.finditer(payload):
                call = match.group(0)
                if call not in seen:
                    seen.add(call)
                    yield {'kind': 'agent', 'session': session, 'ts': ts, 'name': match.group(1).decode()}
            for call in SKILL_CALL.finditer(payload):
                if call.group(1) in seen:
                    continue
                seen.add(call.group(1))
                for name in skills_read(call.group(1).decode('utf-8', 'replace'), kit_skills):
                    yield {'kind': 'skill', 'session': session, 'ts': ts, 'name': name}
