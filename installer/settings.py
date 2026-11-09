"""Settings: the organization, team and personal layers, the Core default selection, and what they resolve to (skills, commands, MCP servers)."""
import getpass
import os
import re
import shutil
import subprocess

from .core import (content_root, KIT_CONTEXT, EMAIL, SECRET, KitError, safe_id)
from .toml_files import read_toml
from .adapters import ADAPTERS


def context_folder(root=None):
    """The content's context layers."""
    return (root or content_root())/'context'


def practice_file(practice_id):
    """Source file of a practice and name of the context file it produces."""
    safe_id(practice_id)
    matches = sorted(context_folder().glob('[0-9][0-9]-'+practice_id+'.md'))
    if len(matches) != 1:
        raise KitError('Practice not found or ambiguous: ' + practice_id)
    source = matches[0]
    return source, source.stem[:2]+'_'+practice_id.upper().replace('-','_')+'.md'


CORE_SELECTION = 'core'  # 2.2: no profiles; state.json records this instead of a profile name


def core_selection():
    """The Core default selection (ADR 0018), in the shape the plan reads: every skill, agent and command marked default in its
    metadata; the context layers company and team. A Team then turns on more ([defaults]), the person adds or removes."""
    from .core import load_commands
    from .resolve import agent_catalog, skill_catalog
    return {'id': CORE_SELECTION, 'label': 'Core default', 'practices': ['company', 'team'], 'mcp': [],
            'skills': [n for n, e in skill_catalog(content_root()).items() if e.get('default')],
            'agents': [n for n, e in agent_catalog(content_root()).items() if e.get('default')],
            'commands': [c['name'] for c in load_commands() if c.get('default', True)]}


def managed_context_names(profile):
    names = [KIT_CONTEXT] + [practice_file(p)[1] for p in profile['practices']]
    if len(set(names)) != len(names):
        raise KitError('Duplicate practice prefixes in the profile.')
    return names


def validate_server(server):
    if not isinstance(server, dict):
        raise KitError('MCP configuration: object expected.')
    transports = [key for key in ('command','httpUrl','url') if server.get(key)]
    if len(transports) != 1:
        raise KitError('MCP: choose a single transport: command, httpUrl or url.')
    key = transports[0]
    if not isinstance(server[key], str):
        raise KitError('MCP: transport must be a string.')
    if key != 'command' and not server[key].startswith('https://'):
        raise KitError('Remote MCP: HTTPS URL expected.')
    if 'args' in server and (not isinstance(server['args'],list) or not all(isinstance(x,str) for x in server['args'])):
        raise KitError('MCP: args must be a list of strings.')
    if 'required' in server and not isinstance(server['required'], bool):
        raise KitError('MCP: required must be true or false.')
    # Never preselect automatic trust, whatever its form: "true" as a string went through to Gemini and agy before 0.51.1.
    if 'trust' in server:
        raise KitError('MCP: trust is not supported by this kit (the CLI asks before running a server\'s tools).')
    # A secret written as a value would be copied in clear into the CLIs' settings, the state and the backups: ${VARIABLE} only.
    for field in ('env', 'headers'):
        values = server.get(field) or {}
        if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
            raise KitError('MCP: '+field+' must be a table of texts.')
        for key, value in values.items():
            if re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', value.strip()):
                continue
            if SECRET_NAME.search(key) or SECRET.search(key+'='+value):
                raise KitError('MCP: '+field+' '+key+' holds a value that looks secret: write ${'+re.sub(r'[^A-Za-z0-9_]', '_', key).upper()
                               + '} instead and define that variable in your environment (docs/mcp.md).')
    return server


SECRET_NAME = re.compile(r'(?i)(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization|auth)')


def git_identity(home):
    """Global git identity read from the given home folder."""
    if not shutil.which('git'):
        return {}
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home), 'XDG_CONFIG_HOME': str(home/'.config'), 'GIT_CONFIG_NOSYSTEM': '1'}
    result = {}
    for key in ('email','name'):
        try:
            proc = subprocess.run(['git','config','--global','--get','user.'+key], capture_output=True, text=True, encoding='utf-8', env=env, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return {}
        value = proc.stdout.strip()
        if proc.returncode == 0 and value:
            result[key] = value
    if 'email' in result and not EMAIL.fullmatch(result['email']):
        result.pop('email')
    return result


def detect_identity(home):
    """Declarative identity: first available source. Never an authentication."""
    found = next(((a.NAME, a.active_account(home)) for a in ADAPTERS if a.active_account(home)), (None, None))
    git = git_identity(home)
    if found[1]:
        identity = {'email': found[1], 'source': found[0]}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    if git.get('email'):
        identity = {'email': git['email'], 'source': 'git'}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    try:
        login = getpass.getuser()
    except Exception:
        return {}
    return {'name': login, 'source': 'os'} if login else {}


def organization():
    """The Core's settings: its MCP servers (mcp/servers.toml, [servers.<name>]) as the defaults' mcp. IT's decisions are in
    managed.toml, a team's in its Team repository."""
    servers = read_toml(content_root()/'mcp'/'servers.toml', {}).get('servers', {})
    if not isinstance(servers, dict) or not all(isinstance(v, dict) for v in servers.values()):
        raise KitError('mcp/servers.toml: one table per server ([servers.<name>]).')
    mcp = {n: {k: v for k, v in {'server': {x: y for x, y in s.items() if x != 'enabled'}, 'enabled': s.get('enabled')}.items() if v is not None}
           for n, s in servers.items()}
    return {'defaults': {'mcp': mcp}} if mcp else {}


TRACKER_KINDS = ('gitlab', 'github')
TRACKER_SOURCES = ('agent', 'person', 'doctor')


def friction_tracker(personal, managed=None):
    """managed.toml [frictions.tracker], validated, with its defaults, or None: no tracker, or the person wrote
    share_frictions = false. What the /friction script reads from state.json (runtime/friction.py)."""
    from .config import ManagedConfigError  # an unusable managed.toml is exit code 3 (ADR 0015)
    config = ((managed or {}).get('frictions') or {}).get('tracker')
    if config is None:
        return None
    if not isinstance(config, dict):
        raise ManagedConfigError('managed.toml: frictions.tracker must be a table ([frictions.tracker]).')
    kind, project, host = config.get('kind'), config.get('project'), config.get('host', '')
    if kind not in TRACKER_KINDS:
        raise ManagedConfigError('managed.toml: frictions.tracker.kind must be gitlab or github.')
    if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+', project):
        raise ManagedConfigError('managed.toml: frictions.tracker.project must be the project path on the host (group/project), without URL.')
    if not isinstance(host, str) or (host and not re.fullmatch(r'[a-z0-9.-]+(:[0-9]+)?', host)):
        raise ManagedConfigError('managed.toml: frictions.tracker.host must be a host name (gitlab.example.org), without scheme or path.')
    labels = config.get('labels', ['friction'])
    if not isinstance(labels, list) or not all(isinstance(label, str) and re.fullmatch(r'[^,\s][^,]{0,49}', label) for label in labels):
        raise ManagedConfigError('managed.toml: frictions.tracker.labels must be a list of label names.')
    sources = config.get('sources', ['agent'])
    if not isinstance(sources, list) or not sources or any(source not in TRACKER_SOURCES for source in sources):
        raise ManagedConfigError('managed.toml: frictions.tracker.sources must list agent, person or doctor.')
    share = personal.get('share_frictions', True)
    if not isinstance(share, bool):
        raise KitError('aikit.toml: frictions.publication must be approval or disabled.')
    if not share:
        return None
    return {'kind': kind, 'project': project, 'host': host, 'labels': labels, 'sources': sources}


def team_settings(team):
    """The active Team's [defaults] (teams/<team>.toml in the content the Team is overlaid on), between the Core and the person."""
    return read_toml(content_root()/'teams'/(safe_id(team)+'.toml'), {}) if team else {}


def resolve_mcp(org_mcp, profile_mcp, personal_mcp, team_mcp=None):
    """MCP servers to install, by name, and the names chosen without a definition.
    The Core's mcp/servers.toml says how to reach each server (active for everyone with enabled = true); the Team then the
    person turn a defined server on or off."""
    team_mcp = team_mcp or {}
    for label, entries in (('mcp/servers.toml', org_mcp), ('Team', team_mcp), ('aikit.toml', personal_mcp)):
        if not isinstance(entries, dict):
            raise KitError(label+': mcp must be an object.')
    if not isinstance(profile_mcp, list) or not all(isinstance(n, str) for n in profile_mcp):
        raise KitError('Profile: mcp must be a list of server names.')
    defined, active = {}, set(profile_mcp)
    for source, entries in (('mcp/servers.toml', org_mcp), ('Team', team_mcp), ('aikit.toml', personal_mcp)):
        for name, entry in entries.items():
            safe_id(name)
            if isinstance(entry, bool):
                if source == 'mcp/servers.toml':
                    raise KitError('mcp/servers.toml: '+name+' must describe the server ([servers.'+name+']).')
                if entry:
                    active.add(name)
                else:
                    active.discard(name)
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get('enabled', True), bool):
                raise KitError(source+': mcp.'+name+' must be true, false or a server ([mcp.'+name+'.server]).')
            if entry.get('server') is not None:
                defined[name] = validate_server(entry['server'])
            # A Core server is active when enabled = true (everyone) or turned on by the Team or the person.
            if entry.get('enabled', source != 'mcp/servers.toml'):
                active.add(name)
            elif 'enabled' in entry:
                active.discard(name)
    return {name: defined[name] for name in sorted(active) if name in defined}, sorted(active - set(defined))


def merge_settings(base, extra):
    """Organization defaults, then the person's overrides on top: lists add up, objects combine, a single value is replaced.
    Keys starting with _ are documentation, $schema is for editors."""
    merged = {k: v for k, v in base.items() if not str(k).startswith(('_', '$'))}
    for key, value in extra.items():
        if str(key).startswith(('_', '$')):
            continue
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_settings(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            merged[key] = current + [v for v in value if v not in current]
        else:
            merged[key] = value
    return merged


def unknown_keys(settings):
    """Keys of a settings layer (the person's aikit.toml translated, a Team's [defaults]) the engine does not know."""
    known = set(CHOICE_KEYS) | {'hooks', 'mcp', 'skill_prefix', 'frictions', 'share_frictions'}
    return sorted(k for k in settings if not str(k).startswith(('_', '$')) and k not in known)


def setting_differences(base, effective, prefix=''):
    """Single values the person's overrides change compared with the organization defaults (for doctor)."""
    changed = []
    for key, value in base.items():
        if str(key).startswith(('_', '$')) or key not in effective:
            continue
        if isinstance(value, dict) and isinstance(effective[key], dict):
            changed += setting_differences(value, effective[key], prefix+key+'.')
        elif not isinstance(value, list) and effective[key] != value:
            changed.append(prefix+key)
    return changed


def resolve_skills(profile, overrides, catalog, log=print):
    """Final selection: the Core default + extra, dependencies added, disabled skills respected."""
    disabled = set(overrides.get('disabled_skills', []))
    selected = []
    def add(name, via=None):
        safe_id(name)
        if name not in catalog:
            raise KitError('Unknown skill: '+name)
        entry = catalog[name]
        if name in disabled:
            if via:
                raise KitError('Skill '+name+' is disabled in your aikit.toml but required by '+via+'.')
            return
        if name in selected:
            return
        selected.append(name)
        for dependency in entry.get('requires', []):
            add(dependency, name)
    for name in list(profile['skills']) + list(overrides.get('extra_skills', [])):
        add(name)
    return selected


def skill_note(skill, selected, catalog):
    """What the installed SKILL.md says about the optional skills it cites that this installation does not have."""
    missing = {name: alternative for name, alternative in catalog[skill].get('optional', {}).items() if name not in selected}
    if not missing:
        return ''
    return ('## Not installed here\nThis text cites skills this installation does not have; do not look for them. Instead:\n'
            + ''.join('- `'+name+'`: '+alternative+'.\n' for name, alternative in sorted(missing.items())))


# Authentication and model belong to each CLI and to the IT procedure: the kit stopped writing them in 0.36.
def unknown_names(overrides, catalog, agent_catalog, notices):
    """disabled_skills and disabled_agents naming nothing the kit knows: a typo, reported, never silently ignored."""
    for key, known in (('disabled_skills', catalog), ('disabled_agents', agent_catalog)):
        unknown = [name for name in overrides.get(key, []) if name not in known]
        if unknown:
            notices.append('[Check] aikit.toml '+key+': unknown name '+', '.join(unknown)+' (a typo?); it has no effect.')


def allowed_commands(profile_commands, overrides, command_names):
    """Allowed commands: the profile list (or all), plus extra_commands, minus disabled_commands; None when nothing restricts."""
    extra, disabled = overrides.get('extra_commands', []), set(overrides.get('disabled_commands', []))
    if profile_commands is None and not disabled:
        return None
    base = list(profile_commands) if profile_commands is not None else list(command_names)
    return [c for c in base + [e for e in extra if e not in base] if c not in disabled]


def selected_commands(selected, manifest, allowed=None):
    """Commands whose skills are all installed, in manifest order; restricted to the profile list if there is one."""
    return [c for c in manifest if all(s in selected for s in c['skills']) and (allowed is None or c['name'] in allowed)]


def version_changes(before, now):
    """The skills and agents whose version changed since the previous installation: "skill tdd 1.0.0 → 1.1.0". Nothing
    on a first installation, or from a state written before 0.40 (no versions recorded)."""
    if not before:
        return []
    return [kind[:-1]+' '+name+' '+str(before[kind][name])+' → '+str(version)
            for kind in ('skills', 'agents') for name, version in sorted((now.get(kind) or {}).items())
            if name in (before.get(kind) or {}) and before[kind][name] != version]




def recorded_targets(state):
    """The CLIs the person chose at the last installation."""
    return state.get('targets') or (state.get('installed') or {}).get('clis') or None


PERSONAL_FILE = 'aikit.toml'  # 3.0: the person's only settings file


def personal_settings(kit):
    """The person's settings: ~/.ai-kit/aikit.toml, in the engine's vocabulary (to_overrides); none when it does not exist."""
    from .config import load_aikit, to_overrides
    return to_overrides(load_aikit(kit/PERSONAL_FILE)[0]) if (kit/PERSONAL_FILE).exists() else {}


CHOICE_KEYS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
SCALAR_CHOICES = ('frictions',)  # a plain value the installer may write too (ai-kit friction --mode)
