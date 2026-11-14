"""Gemini CLI adapter: layers in ~/.gemini, skills, TOML commands, agents, settings, authentication, logs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from typing import Optional

from ..interface import DoctorContext, Plan, Status
from .. import resolve
from ..core import (hook_parts, content_root, user_context_refusal, adopt_user_copy, LIVE_PROMPT, network_problem, EMAIL, USER_CONTEXT, CONTEXT_NAME, KitError, read_json, json_bytes, skill_prefix, free_name,
                    rename_references, renamed_skill_file, renamed_notice, kit_name,
                    digest, merge_defaults, run_timed,
                    record_auto_friction, _ts)

PROJECT_CONTEXT = ('GEMINI.md', 'AGENTS.md')  # repo context files Gemini must read

def merge_context_filenames(settings, managed=(), retired=()):
    """Ensure the kit and project context, without removing personal files; remove the layers the kit used to manage and no longer produces."""
    context = settings.setdefault('context', {})
    if not isinstance(context, dict):
        raise KitError('context must be an object; configuration left untouched.')
    names = context.get('fileName', [])
    if isinstance(names, str):
        names = [names]
    if not isinstance(names, list) or not all(isinstance(name, str) and name.strip() for name in names):
        raise KitError('context.fileName must be a name or a list of non-empty names; configuration left untouched.')
    stale = set(retired) - set(managed)
    context['fileName'] = list(dict.fromkeys(list(managed) + [USER_CONTEXT] + list(PROJECT_CONTEXT) + [n for n in names if n not in stale]))
    return settings

def gemini_active_account(home):
    """Active Google account of Gemini, or None. Read only, never the tokens."""
    path = home/'.gemini/google_accounts.json'
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError):
        return None
    active = value.get('active') if isinstance(value, dict) else None
    return active if isinstance(active, str) and EMAIL.fullmatch(active) else None

def gemini_command_toml(command):
    """Gemini CLI adapter: TOML command file (description, prompt with {{args}})."""
    return 'description = ' + json.dumps(command['description'], ensure_ascii=False) + '\n\nprompt = """\n' + command['prompt'] + '"""\n'

def kit_hook_groups(groups):
    """Indexes of the hook groups added by the kit in a settings list."""
    return [i for i,g in enumerate(groups) if isinstance(g,dict) and any(isinstance(h,dict) and str(h.get('name','')).startswith('ai-kit-') for h in g.get('hooks',[]))]


def diagnose_live(returncode, output, timed_out, settings):
    """A one-sentence diagnosis and the fix, from the output of a real call to Gemini."""
    network = network_problem(output, 'Gemini (Node.js)', 'the Google APIs', 'the Google API hosts (googleapis.com)')
    if network:
        return network
    if timed_out:
        return ('Gemini does not answer in time: the default model is probably unavailable for your access and Gemini is looping on a fallback.',
                'Choose a model your access allows: /model in gemini, or model.name in ~/.gemini/settings.json (ask IT which one).')
    if 'prepayment credits are depleted' in output or ('402' in output and 'credits' in output):
        return ('AI Studio credits depleted: the configured API key has no balance left (HTTP 402).',
                'Top up the AI Studio project, or switch to Google sign-in (/auth in gemini), or to Vertex AI (selectedType vertex-ai, GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT).')
    if 'API Keys are Disallowed' in output or 'API keys are not supported' in output:
        return ('Your Google Cloud organization policy forbids API keys.',
                'Use application default credentials: gcloud auth application-default login, selectedType vertex-ai, and remove GEMINI_API_KEY / GOOGLE_API_KEY from the environment.')
    if 'aiplatform.googleapis.com' in output and ('has not been used' in output or 'is disabled' in output):
        match = re.search(r'project=([a-z0-9-]+)', output)
        project = match.group(1) if match else os.environ.get('GOOGLE_CLOUD_PROJECT', '<project>')
        return ('The Vertex AI API is not enabled on project ' + project + ' (HTTP 403).',
                'gcloud services enable aiplatform.googleapis.com --project ' + project)
    if 'When using Vertex AI, you must specify' in output:
        return ('Vertex AI authentication without a project or region.',
                'Set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in ~/.gemini/.env or in your environment, as your IT procedure says.')
    if 'requires setting the GOOGLE_CLOUD_PROJECT' in output:
        return ('Your Gemini Code Assist account (Standard or Enterprise licence) requires a Google Cloud project.',
                'Set GOOGLE_CLOUD_PROJECT in ~/.gemini/.env or in your environment, as your IT procedure says.')
    if 'Please set an Auth method' in output:
        return ('No Gemini authentication configured.',
                'Run gemini then /auth, or set GEMINI_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI=true with GOOGLE_CLOUD_PROJECT.')
    if re.search(r'status: 403|"code": 403', output):
        return ('Access denied by the API (HTTP 403): missing IAM permission on the project or the model.',
                'Ask the project administrator for the Vertex AI User role.')
    if re.search(r'status: 401|"code": 401', output):
        return ('Authentication refused (HTTP 401).', 'Run /auth again in gemini; if you use Vertex, gcloud auth application-default login.')
    if re.search(r'status: 429|"code": 429|RESOURCE_EXHAUSTED', output):
        return ('Quota exceeded (HTTP 429).', 'Wait, or ask for a higher quota on the project.')
    if returncode == 0 and 'OK' in output:
        return (None, None)
    return ('Gemini answered but not as expected (code ' + str(returncode) + ').', 'Read the full output: gemini --debug -p "' + LIVE_PROMPT + '"')

def parse_env_file(path):
    """Reads a .env file the way dotenv does: `export` ignored, quotes removed, end-of-line comment outside quotes ignored."""
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            continue
        if value[:1] in ('"', "'") and value.find(value[0], 1) > 0:
            value = value[1:value.find(value[0], 1)]
        else:
            value = value.split(' #', 1)[0].rstrip()
        values[key] = value
    return values

def live_check(home, timeout=90):
    """Real call to the model from an empty folder. Returns (ok, diagnosis, fix, warnings)."""
    settings = read_json(home/'.gemini/settings.json')
    warnings = []
    # Same reading as Gemini (dotenv): the shell environment wins over ~/.gemini/.env; nothing is written to os.environ.
    env = dict(os.environ)
    for key, value in parse_env_file(home/'.gemini/.env').items():
        env.setdefault(key, value)
    auth = (settings.get('security') or {}).get('auth', {}).get('selectedType')
    if auth == 'gemini-api-key' and env.get('GOOGLE_GENAI_USE_VERTEXAI', '').lower() in ('true', '1', 'yes'):
        warnings.append('selectedType is gemini-api-key: the Vertex variables in the environment are ignored. Set selectedType to vertex-ai to use Vertex.')
    if auth == 'vertex-ai' and not env.get('GOOGLE_CLOUD_PROJECT'):
        warnings.append('selectedType is vertex-ai without GOOGLE_CLOUD_PROJECT in the environment.')
    if auth == 'vertex-ai' and (env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY')):
        warnings.append('An API key is present in the environment while authentication is Vertex: remove GEMINI_API_KEY / GOOGLE_API_KEY if the organization forbids keys.')
    if not shutil.which('gemini'):
        return False, 'Gemini CLI not on the PATH.', 'Install Gemini CLI following the IT procedure.', warnings
    model = (settings.get('model') or {}).get('name')
    with tempfile.TemporaryDirectory() as tmp:
        command = ['gemini', '--approval-mode', 'plan', '--skip-trust'] + (['-m', model] if model else []) + ['-p', LIVE_PROMPT]
        try:
            proc = run_timed(command, timeout, cwd=tmp, text=True, encoding='utf-8', stdin=subprocess.DEVNULL, env=env)
            output, code, timed_out = proc.stdout + '\n' + proc.stderr, proc.returncode, False
        except subprocess.TimeoutExpired as exc:
            def text(v):
                return v.decode('utf-8', 'replace') if isinstance(v, bytes) else (v or '')
            output, code, timed_out = text(exc.stdout) + '\n' + text(exc.stderr), None, True
        except OSError as exc:
            return False, 'Cannot run gemini: ' + str(exc), 'Check the Gemini CLI installation.', warnings
    diagnostic, remedy = diagnose_live(code, output, timed_out, settings)
    return diagnostic is None, diagnostic, remedy, warnings

def print_live(home, timeout=90):
    ok, diagnostic, remedy, warnings = live_check(home, timeout)
    for warning in warnings:
        print('[Check] '+warning)
    if ok:
        print('[OK] Real call to the model: Gemini answers.')
        return 0
    print('[Check] '+diagnostic)
    print('        Fix: '+remedy)
    record_auto_friction(home, diagnostic, 'gemini')
    return 1

# --- Adapter interface ---------------------------------------------------------------------------------------------
NAME = 'gemini'

# V2 slice 4: what this CLI does with each kit capability (docs/v2/resources.md, measured); doctor shows it.
CAPABILITIES = {
    'context': ('DEGRADED', 'a copy: run ai-kit sync --offline after a change'),
    'skills': ('OK', 'each skill is also a command'),
    'user-only skills': ('BLOCKED', 'ignored: the model may activate any skill'),
    'commands': ('OK', '/name'),
    'sub-agents': ('OK', 'tool list applied; can be turned off'),
    'guardrails': ('OK', 'native hooks'),
}
LABEL = 'Gemini CLI'
COMMAND = 'gemini'
VERIFIED = '0.65.0'  # the CLI version the kit was last checked on (docs/cli/matrice.md); doctor says when a newer one runs
HOME_DIR = '.gemini'
OBSERVES = {'prompt', 'skill', 'agent', 'error'}  # chat logs hold every tool call, activate_skill and agents included
LOGS = ('.gemini/tmp/*/chats/*.json',)  # read by history; usage says when they exist but give nothing
AGENT_TOOLS = 'native'  # the agent's front matter "tools" list is the only set of tools Gemini gives it
MANAGED_PREFIXES = ('.gemini/skills/', '.gemini/agents/', '.gemini/commands/', '.gemini/hooks/ai-kit/')  # the last one: former location of the guardrails

# Built-in commands: not counted as unknown commands in the usage report.
BUILTIN_COMMANDS = {'about','agents','auth','bug','chat','clear','commands','compress','copy','corgi','directory','docs','editor','extensions','help','hooks','ide','init','mcp','memory','model','permissions','plan','planning','policies','privacy','quit','exit','restore','resume','settings','setup-github','skills','stats','terminal-setup','theme','tools','vim','config','diff','keybindings','remote-control','login','logout'}

def present(home):
    return bool(shutil.which(COMMAND)) or (home/HOME_DIR/'settings.json').is_file()

def is_managed(rel):
    """Path a kit installation may have put in place for Gemini, so one it can remove if intact."""
    if rel.startswith(MANAGED_PREFIXES):
        return True
    return rel.startswith('.gemini/') and bool(CONTEXT_NAME.fullmatch(rel[len('.gemini/'):]))  # USER.md included: a copy

def active_account(home):
    return gemini_active_account(home)

def copy_context(p: Plan) -> None:
    """Copies of the layers and of USER.md in ~/.gemini, the only folder Gemini reads them from. A layer copy edited by
    hand is put back, as the layers are. The USER.md copy edited by hand while the file itself did not change since
    the last copy: the person edited the wrong file, so the edit goes into the file itself; if both changed, the file wins
    and the edited copy is in the backup."""
    gemini = p.home/HOME_DIR
    for name in p.context_names:
        source = p.context_dir/name
        data = p.writes[source] if source in p.writes else source.read_bytes()
        p.managed_write(gemini/name, data, 'Context file (copy)', restore=True)
    data = p.writes[p.user_file] if p.user_file in p.writes else p.user_file.read_bytes() if p.user_file.exists() else b''
    if user_context_refusal(data):
        return  # the orchestrator already says why; the previous copy stays
    copy, rel = gemini/USER_CONTEXT, HOME_DIR+'/'+USER_CONTEXT
    last = p.old_files.get(rel)
    if copy.exists() and last and digest(copy.read_bytes()) != last and adopt_user_copy(p, copy, last):
        data = p.writes[p.user_file]
    p.managed_write(copy, data, 'Personal context (copy)', replace_edited=True)

def install(p: Plan) -> None:
    """Skills, TOML commands and agents in ~/.gemini, and a copy of the context files."""
    gemini = p.home/'.gemini'
    copy_context(p)
    names = skill_names(p)
    # Gemini turns every skill into a /command too: a personal skill takes the command's name as well.
    personal_skill = ((lambda n: gemini/'skills'/n, lambda n: '.gemini/skills/'+n),)
    commands = {c['name']: free_name(c['name'], lambda n: gemini/'commands'/(n+'.toml'), lambda n: '.gemini/commands/'+n+'.toml', p.old_files,
                                     skill_prefix(p.overrides), 'command', personal_skill) for c in p.commands}
    mapping = {**{o: n for o, n in names.items() if o != n}, **{o: n for o, n in commands.items() if o != n}}
    p.adapter_data.setdefault(NAME, {})['mapping'] = mapping
    write_skills(p)
    for command in p.commands:
        text = gemini_command_toml({**command, 'prompt': rename_references(command['prompt'], mapping)})
        p.managed_write(gemini/'commands'/(commands[command['name']]+'.toml'), text.encode('utf-8'), 'Command')
    notice = renamed_notice(LABEL, names, commands)
    if notice:
        p.notices.append(notice)
    for agent, definition in p.agents:
        name = 'ai-kit-'+agent
        data = agent_markdown(p, agent, definition)
        p.managed_write(gemini/'agents'/(name+'.md'), data, 'Agent')
        p.agent_markdown[name] = data

def skill_names(p: Plan) -> dict:
    """Each kit skill's name in ~/.gemini/skills (shared by Gemini and agy): its own, or prefixed when one of the person's
    skills already has it. Computed once per installation."""
    shared = p.adapter_data.setdefault('gemini-skills', {})
    if 'names' not in shared:
        root, prefix = p.home/'.gemini'/'skills', skill_prefix(p.overrides)
        shared['names'] = {s: free_name(s, lambda n: root/n, lambda n: '.gemini/skills/'+n, p.old_files, prefix, 'skill') for s in p.selected}
    return shared['names']

def write_skills(p: Plan) -> None:
    """Profile skills in ~/.gemini/skills, a folder read by Gemini and by agy."""
    names = skill_names(p)
    mapping = {o: n for o, n in names.items() if o != n}
    for skill, source in p.skill_sources:
        for src in source.rglob('*'):
            if src.is_file():
                data = renamed_skill_file(p.skill_file(skill, source, src), src, source, mapping, names[skill] if names[skill] != skill else None)
                p.managed_write(p.home/'.gemini'/'skills'/names[skill]/src.relative_to(source), data, 'Skill')

def agent_markdown(p: Plan, agent: str, definition: dict, tool_names=None) -> bytes:
    """Agent in Markdown with front matter, the format of Gemini and agy; tool_names translates the kit's tool names
    (Gemini's) into the CLI's own, one kit tool giving one or more."""
    agent_defaults = read_json(content_root()/'agents/defaults.json')
    tools = definition.get('tools', agent_defaults['tools'])
    if tool_names:
        tools = list(dict.fromkeys(t for tool in tools for t in tool_names.get(tool, [tool])))
    # Identifiers are validated slugs; a JSON string is also a valid YAML string.
    header = ['---', 'name: ai-kit-'+agent, 'description: '+json.dumps(definition['description'], ensure_ascii=False),
              'kind: local', 'tools: '+json.dumps(tools),
              'max_turns: '+str(definition.get('max_turns', agent_defaults['max_turns']))]
    header += ['timeout_mins: '+str(definition.get('timeout_mins', agent_defaults['timeout_mins'])), '---']
    return ('\n'.join(header)+'\n\n'+p.agent_body(definition)).encode('utf-8')

def was_installed(state):
    """Gemini was a target of the previous installation."""
    return NAME in ((state.get('installed') or {}).get('clis') or [])

def remove_kit_settings(p: Plan) -> None:
    """Gemini no longer a target: its settings lose what the kit added (guardrail groups, kit MCP servers, the kit layers
    in context.fileName and the USER.md copy); the person's own settings stay. A kit entry edited by hand stops the change."""
    gemini = p.home/'.gemini'
    settings_file = gemini/'settings.json'
    if settings_file.is_file():
        settings = read_json(settings_file)
        hooks = settings.get('hooks')
        if isinstance(hooks, dict):
            for name, old in p.state.get('hooks', {}).items():
                groups = hooks.get(old['event'], [])
                if isinstance(groups, list) and any(any(h.get('name') == old['group']['hooks'][0].get('name') for h in g.get('hooks', [])) and g != old['group'] for g in (groups[i] for i in kit_hook_groups(groups))):
                    if not p.restore:  # sync --restore: the kit's entry is replaced
                        raise KitError('Kit guardrail modified in settings.json: '+name)
                    else:
                        p.notices.append('[Check] a kit entry in ~/.gemini/settings.json was edited by hand: restored; your copy is in ~/.ai-kit/backups/ (the folder of this run).')
            for event, groups in list(hooks.items()):
                if isinstance(groups, list) and kit_hook_groups(groups):
                    kept = [g for i, g in enumerate(groups) if i not in kit_hook_groups(groups)]
                    if kept:
                        hooks[event] = kept
                    else:
                        hooks.pop(event)
            if not hooks:
                settings.pop('hooks')
        servers = settings.get('mcpServers')
        if isinstance(servers, dict):
            for name, old in p.state.get('mcp', {}).items():
                if name in servers and servers[name] != old:
                    if not p.restore:  # sync --restore: the kit's entry is replaced
                        raise KitError('Kit MCP modified in settings.json: '+name)
                    else:
                        p.notices.append('[Check] a kit entry in ~/.gemini/settings.json was edited by hand: restored; your copy is in ~/.ai-kit/backups/ (the folder of this run).')
                servers.pop(name, None)
        context = settings.get('context')
        if isinstance(context, dict) and isinstance(context.get('fileName'), list):
            layers = {rel.split('/', 1)[1] for rel in p.old_files if re.fullmatch(r'\.gemini/\d\d_[A-Z_]+\.md', rel)}
            context['fileName'] = [n for n in context['fileName'] if n not in layers and n != USER_CONTEXT]
        p.writes[settings_file] = json_bytes(settings)

def finalize(p: Plan, active: bool = True) -> None:
    """Settings ~/.gemini/settings.json (defaults, layers, guardrails, MCP); authentication and model are left to the person.
    Inactive: removes what a previous installation had added there."""
    if not active:
        if was_installed(p.state):
            remove_kit_settings(p)
        return
    gemini = p.home/'.gemini'
    state = p.state
    settings_file = gemini/'settings.json'
    settings = read_json(settings_file)
    merge_defaults(settings, read_json(Path(__file__).resolve().parent/'gemini_defaults.json'))
    # Authentication and model belong to the CLI and the IT procedure: the kit writes neither.
    retired = [rel.split('/',1)[1] for rel in p.old_files if re.fullmatch(r'\.gemini/\d\d_[A-Z_]+\.md', rel)]
    merge_context_filenames(settings, p.context_names, retired)
    original_hooks = settings.get('hooks')
    if original_hooks is not None and not isinstance(original_hooks, dict):
        raise KitError('hooks must be an object in settings.json.')
    original_hooks = original_hooks or {}
    old_hooks = state.get('hooks', {})
    for name, old in old_hooks.items():
        groups = original_hooks.get(old['event'], [])
        if not isinstance(groups, list):
            raise KitError('settings.json: hooks.'+old['event']+' must be a list.')
        for i in kit_hook_groups(groups):
            if any(h.get('name') == old['group']['hooks'][0].get('name') for h in groups[i].get('hooks', [])) and groups[i] != old['group']:
                if not p.restore:  # sync --restore: the kit's entry is replaced
                    raise KitError('Kit guardrail modified in settings.json: '+name)
                else:
                    p.notices.append('[Check] a kit entry in ~/.gemini/settings.json was edited by hand: restored; your copy is in ~/.ai-kit/backups/ (the folder of this run).')
    merged_hooks = {}
    for event, groups in original_hooks.items():
        if not isinstance(groups, list):
            merged_hooks[event] = groups
            continue
        kept = [g for i, g in enumerate(groups) if i not in kit_hook_groups(groups)]
        if kept or not groups:
            merged_hooks[event] = kept
    for name, spec in p.enabled_hooks.items():
        if spec['group'] not in merged_hooks.setdefault(spec['event'], []):  # guardrails served by one script: one hook
            merged_hooks[spec['event']].append(spec['group'])
    if merged_hooks or ('hooks' in settings and not any(kit_hook_groups(g) for g in original_hooks.values() if isinstance(g, list))):
        settings['hooks'] = merged_hooks
    else:
        settings.pop('hooks', None)
    servers = settings.get('mcpServers',{})
    if not isinstance(servers,dict):
        raise KitError('mcpServers must be an object.')
    old_mcp = state.get('mcp',{})
    for name,old in old_mcp.items():
        if name in servers and servers[name] != old:
            if not p.restore:  # sync --restore: the kit's entry is replaced
                raise KitError('Kit MCP modified in settings.json: '+name)
            else:
                p.notices.append('[Check] a kit entry in ~/.gemini/settings.json was edited by hand: restored; your copy is in ~/.ai-kit/backups/ (the folder of this run).')
        servers.pop(name,None)
    for name,server in p.enabled_mcp.items():
        if name in servers and servers[name] != server:
            raise KitError('MCP name already in use: '+name)
        servers[name] = server
    if servers or 'mcpServers' in settings:
        settings['mcpServers'] = servers
    p.writes[settings_file] = json_bytes(settings)

def summary(p: Plan) -> Optional[str]:
    return None

def skill_description_weight(home, skill_names):
    """Bytes of descriptions Gemini injects on every turn for the installed skills."""
    total = 0
    for name in skill_names:
        path = home/'.gemini/skills'/name/'SKILL.md'
        if not path.is_file():
            continue
        match = re.search(r'^description:\s*(.+?)\s*$', path.read_text(encoding='utf-8'), re.M)
        total += len((match.group(1) if match else '').encode('utf-8')) + len(name)
    return total

def installed_skills(home, state):
    names = sorted({rel.split('/')[2] for rel in state.get('files',{}) if rel.startswith('.gemini/skills/')})
    return [s for s in names if (home/'.gemini/skills'/s/'SKILL.md').is_file()]

def changed_blocks(home: Path, state: dict) -> list:
    """~/.gemini/settings.json when a hook the kit declared there is gone or changed (integrity check); the rest of the file
    is the person's."""
    if NAME not in state.get('targets', [NAME]) or not state.get('hooks'):
        return []
    try:
        settings = read_json(home/'.gemini/settings.json')
    except (KitError, OSError, ValueError):
        return ['.gemini/settings.json']
    hooks = settings.get('hooks') if isinstance(settings, dict) and isinstance(settings.get('hooks'), dict) else {}
    present = all(isinstance(hooks.get(h['event']), list) and h['group'] in hooks[h['event']] for h in state['hooks'].values())
    return [] if present else ['.gemini/settings.json']

def doctor(home: Path, state: dict, status: Status, ctx: DoctorContext) -> None:
    """Gemini-specific checks: executable, active account, personal context, commands, shadowed skills, settings."""
    status(bool(shutil.which(COMMAND)),'Gemini CLI on the PATH. If missing: follow the approved IT procedure.')
    active = gemini_active_account(home)
    identity = state.get('user', {})
    if active:
        status(not identity.get('email') or active.lower() == identity['email'].lower(),'Active Gemini account matches the recorded identity: '+active)
    else:
        print('[Info] No active Gemini account detected (not signed in, or API key / Vertex mode).')
    skills = installed_skills(home, state)
    installed_commands = sorted(rel.split('/')[2][:-5] for rel in state.get('files',{}) if rel.startswith('.gemini/commands/'))
    by_name = {c['name']: c for c in ctx.load_commands()}
    # Installed names may carry the prefix given on a collision with one of the person's own: compare by kit name.
    present_skills = {kit_name(s, set((state.get('installed') or {}).get('skills', []))) for s in skills}
    for installed_name in installed_commands:
        name = kit_name(installed_name, by_name)
        missing = [s for s in by_name.get(name,{}).get('skills',[]) if s not in present_skills]
        status(name in by_name and not missing,'Command /'+installed_name+': skills present'+(' (missing '+', '.join(missing)+')' if missing else ''))
    print('[Info] '+str(len(skills))+' skills, '+str(len(installed_commands))+' commands; skill descriptions injected on every turn: '+str(skill_description_weight(home, skills))+' bytes.')
    shadowed = [s for s in skills if (home/'.agents/skills'/s/'SKILL.md').is_file()]
    status(not shadowed,'No kit skill shadowed by a copy in ~/.agents/skills'+(' (shadowed: '+', '.join(shadowed)+')' if shadowed else ''))
    settings = read_json(home/'.gemini/settings.json')
    names = settings.get('context',{}).get('fileName',[])
    names = [names] if isinstance(names,str) else names
    expected_names = list(ctx.context_names)+[USER_CONTEXT]+list(PROJECT_CONTEXT)
    status(isinstance(names,list) and all(n in names for n in expected_names),'context.fileName contains the kit layers, GEMINI.md and AGENTS.md')
    status(settings.get('skills',{}).get('enabled',True) is not False,'Skills not disabled in the user settings')
    agents_enabled = settings.get('experimental',{}).get('enableAgents',True) is not False
    status(agents_enabled,'Agents not disabled in the user settings')
    if not agents_enabled:
        catalog = resolve.skill_catalog(content_root())
        needing = sorted(s for s in skills if catalog.get(s,{}).get('needs_agents'))
        if needing:
            print('[Info] Skills that delegate to subagents, degraded without them: '+', '.join(needing))
    for name,hook in state.get('hooks',{}).items():
        groups = (settings.get('hooks') or {}).get(hook['event'], [])
        script = hook_parts(hook['group']['hooks'][0]['command'])[0]
        status(isinstance(groups,list) and hook['group'] in groups and script.is_file(),('Guardrail' if hook.get('event') == 'BeforeTool' else 'Hook')+' configured in settings.json: '+name)
    if not any(h.get('event') == 'BeforeTool' for h in state.get('hooks',{}).values()):
        print('[Info] No guardrail enabled; see docs/hooks.md (protected-paths, dbt-prod-guard, git-guard, bq-cost-guard, infra-prod-guard).')
    for name,server in state.get('mcp',{}).items():
        status(settings.get('mcpServers',{}).get(name)==server,'MCP configuration: '+name)
        if server.get('command'):
            status(bool(shutil.which(server['command'])),'MCP executable available: '+name)

def doctor_hint():
    return 'Gemini: check /memory show, /mcp and /skills list in Gemini.'

def live(home):
    """Real call to the model, with diagnosis and fix; 0 if Gemini answers."""
    return print_live(home)

def session_logs(home):
    return sorted((home/'.gemini/tmp').glob('*/chats/*.json')) if (home/'.gemini/tmp').is_dir() else []

def history(home, state):
    """Usage events read from the Gemini session logs: prompts, activated skills, called agents, errors."""
    for path in session_logs(home):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        messages = data.get('messages', []) if isinstance(data, dict) else []
        session = 'gemini:'+str(path)
        for m in messages:
            if not isinstance(m, dict) or not str(m.get('timestamp',''))[:19]:
                continue
            ts = _ts(m.get('timestamp'))
            if m.get('type') == 'user':
                shown = str(m.get('displayContent') or m.get('content') or '')
                stripped = shown.strip()
                if stripped.startswith("[{'text': '"):
                    stripped = stripped[len("[{'text': '"):]
                yield {'kind': 'prompt', 'session': session, 'ts': ts, 'text': stripped}
            elif m.get('type') == 'error':
                yield {'kind': 'error', 'session': session, 'ts': ts}
            elif m.get('type') == 'gemini':
                yield {'kind': 'activity', 'session': session, 'ts': ts}
                for call in m.get('toolCalls', []) or []:
                    name = call.get('name', '')
                    if name == 'activate_skill':
                        yield {'kind': 'skill', 'session': session, 'ts': ts, 'name': str((call.get('args') or {}).get('name',''))}
                    elif name.startswith('ai-kit-'):
                        yield {'kind': 'agent', 'session': session, 'ts': ts, 'name': name}
            else:
                yield {'kind': 'activity', 'session': session, 'ts': ts}
