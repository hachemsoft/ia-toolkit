"""Adaptateur Antigravity CLI (agy) : plugin ~/.gemini/config/plugins/ai-kit (règles, agents, garde-fous, MCP) et skills de commande."""
import json
import shutil
import subprocess
import sys

from ..core import (ROOT, USER_CONTEXT, json_bytes,
                    quote_path, command_skill_text)

AGY_PLUGIN = '.gemini/config/plugins/ai-kit'

def agy_rules_text(context_names, context_dir='.gemini'):
    lines = ['# Kit IA', '', 'Règles toujours actives du kit, partagées avec les autres CLI. Les fichiers inclus ci-dessous sont la source : ne pas les copier ici.', '']
    for name in list(context_names)+[USER_CONTEXT]:
        lines.append('@['+name[:-3].lower()+'](~/'+context_dir+'/'+name+')')
        lines.append('')
    lines += ['Commandes du kit : chaque commande est un skill du même nom ; `/guide` explique par quoi commencer. Lire aussi `AGENTS.md`, `GLOSSARY.md` et `REVIEW.md` du repo courant.']
    return '\n'.join(lines)+'\n'

# --- Interface d'adaptateur ---------------------------------------------------------------------------------------
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

def install(p):
    """Plugin ai-kit (règles qui incluent les couches par chemin, agents, garde-fous, MCP) et skills de commande."""
    plugin = p.home/AGY_PLUGIN
    manifest_json = {'name': 'ai-kit', 'displayName': 'Kit IA', 'description': 'Contexte, commandes, garde-fous et agents du kit IA Data, partagés avec Gemini CLI.', 'version': (ROOT/'VERSION').read_text().strip()}
    p.managed_write(plugin/'plugin.json', json_bytes(manifest_json), 'Plugin agy')
    p.managed_write(plugin/'rules'/'AGENTS.md', agy_rules_text(p.context_names, p.context_dir.relative_to(p.home).as_posix()).encode('utf-8'), 'Plugin agy')
    skill_names = set(p.selected)
    for command in p.commands:
        if command['name'] in skill_names:
            continue  # un skill du même nom existe déjà : il sert de commande dans agy
        p.managed_write(p.home/'.gemini'/'skills'/command['name']/'SKILL.md', command_skill_text(command).encode('utf-8'), 'Skill de commande')
    for agent_name, agent_bytes in p.agent_markdown.items():
        p.managed_write(plugin/'agents'/(agent_name+'.md'), agent_bytes, 'Plugin agy')
    agy_hooks = {}
    for name, spec in p.hook_manifest.items():
        script = p.hooks_dir/spec['script']
        matcher = 'run_command' if spec['matcher'] == 'run_shell_command' else '.*(write|replace|edit).*'
        agy_hooks['ai-kit-'+name] = {'enabled': name in p.enabled_hooks, 'PreToolUse': [{'matcher': matcher, 'hooks': [{'type': 'command', 'command': quote_path(sys.executable)+' '+quote_path(script), 'timeout': 20}]}]}
    p.managed_write(plugin/'hooks.json', json_bytes(agy_hooks), 'Plugin agy')
    if p.enabled_mcp:
        p.managed_write(plugin/'mcp_config.json', json_bytes({'mcpServers': p.enabled_mcp}), 'Plugin agy')

def finalize(p, active=True):
    return None

def summary(p):
    return 'Antigravity : plugin ai-kit installé dans ~/'+AGY_PLUGIN+' (redémarrer agy pour le voir).'

def doctor(home, state, status, ctx):
    plugin_dir = home/AGY_PLUGIN
    if not plugin_dir.is_dir():
        return
    if shutil.which('agy'):
        try:
            proc = subprocess.run(['agy','plugin','validate',str(plugin_dir)],capture_output=True,text=True,encoding='utf-8',timeout=60)
            status('Validation passed' in proc.stdout+proc.stderr,'Plugin Antigravity ai-kit valide (agy plugin validate)')
        except (OSError, subprocess.SubprocessError):
            print('[Info] agy plugin validate n’a pas pu être lancé.')
    else:
        print('[Info] Plugin Antigravity installé ; agy absent du PATH, validation non faite.')

def history(home, state):
    """~/.gemini/antigravity-cli/history.jsonl : une ligne JSON par prompt tapé (display, timestamp en ms, conversationId)."""
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
