"""Antigravity CLI (agy) adapter: plugin ~/.gemini/config/plugins/ai-kit (rules, agents, guardrails, MCP) and command skills."""
import json
import shutil
import subprocess

from pathlib import Path
from typing import Optional

from . import gemini
from ..interface import DoctorContext, Plan, Status
from ..core import (ROOT, USER_CONTEXT, json_bytes,
                    hook_command, command_skill_text)

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
        # agy reads skills from ~/.gemini/skills and its agents use the Gemini format: without Gemini, put them here.
        gemini.write_skills(p)
        for agent, definition in p.agents:
            p.agent_markdown['ai-kit-'+agent] = gemini.agent_markdown(p, agent, definition)
    skill_names = set(p.selected)
    for command in p.commands:
        if command['name'] in skill_names:
            continue  # a skill with the same name already exists: it serves as the command in agy
        # In the plugin, not in the shared ~/.gemini/skills: Gemini CLI would turn it into a second /<command> next to its own.
        p.managed_write(plugin/'skills'/command['name']/'SKILL.md', command_skill_text(command).encode('utf-8'), 'Command skill')
    for agent_name, agent_bytes in p.agent_markdown.items():
        p.managed_write(plugin/'agents'/(agent_name+'.md'), agent_bytes, 'Plugin agy')
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
