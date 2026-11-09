"""Settings: the organization, team and personal layers, the Core default selection, and what they resolve to (skills, commands, MCP servers)."""
import getpass
import os
import re
import shutil
import subprocess

from .core import (content_root, ROOT, KIT_CONTEXT, EMAIL, SECRET, KitError, read_json, safe_id)
from .toml_files import read_toml
from .adapters import ADAPTERS


def context_folder(root=None):
    """The content's context layers: context/ (2.2), or practices/ in a Core from before (read the same way)."""
    root = root or content_root()
    return root/'context' if (root/'context').is_dir() or not (root/'practices').is_dir() else root/'practices'


def practice_file(practice_id):
    """Source file of a practice and name of the context file it produces."""
    safe_id(practice_id)
    matches = sorted(context_folder().glob('[0-9][0-9]-'+practice_id+'.md'))
    if len(matches) != 1:
        raise KitError('Practice not found or ambiguous: ' + practice_id)
    source = matches[0]
    return source, source.stem[:2]+'_'+practice_id.upper().replace('-','_')+'.md'


def profile_menu():
    """2.2: no profiles (ADR 0018); kept empty for the callers of the V1 API."""
    return []


def profile_ids():
    return []


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


def carried_over(state, selection, overrides, catalog, agent_names, command_names):
    """ADR 0018: what a V1 (or 2.0/2.1) installation had and the Core default no longer gives, kept as plain personal lines:
    {extra_skills: [...], extra_agents: [...], extra_commands: [...]}; nothing when the state already uses the Core selection."""
    if not state.get('profile') or state.get('profile') == CORE_SELECTION:
        return {}
    installed = state.get('installed') or {}
    def kept(names, default, extra, disabled, known):
        return [n for n in names if n in known and n not in default and n not in overrides.get(extra, []) and n not in overrides.get(disabled, [])]
    found = {'extra_skills': kept(installed.get('skills', []), selection['skills'], 'extra_skills', 'disabled_skills',
                                  {n for n, e in catalog.items() if 'path' in e}),
             'extra_agents': kept([a[len('ai-kit-'):] if a.startswith('ai-kit-') else a for a in installed.get('agents', [])], selection['agents'],
                                  'extra_agents', 'disabled_agents', set(agent_names)),
             'extra_commands': kept(installed.get('commands', []), selection['commands'], 'extra_commands', 'disabled_commands', set(command_names))}
    return {k: v for k, v in found.items() if v}


def load_profile(profile_id):
    """2.2: no profiles; every id gives the Core default selection (kept for the callers of the V1 API)."""
    return core_selection()


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
    """What the organization decides. 2.2: the Core holds no organization.toml; its MCP servers are in mcp/servers.toml
    ([servers.<name>], read as the defaults' mcp). An organization.toml still present in a Core (an organization's own copy) is
    read the same way as before, and ai-kit validate says where its keys go (managed.toml, mcp/servers.toml, Team repos)."""
    org = read_toml(content_root()/'organization.toml', {})
    servers = read_toml(content_root()/'mcp'/'servers.toml', {}).get('servers', {})
    if servers:
        if not isinstance(servers, dict) or not all(isinstance(v, dict) for v in servers.values()):
            raise KitError('mcp/servers.toml: one table per server ([servers.<name>]).')
        defaults = dict(org.get('defaults') or {})
        defaults['mcp'] = {**{n: {k: v for k, v in {'server': {x: y for x, y in s.items() if x != 'enabled'}, 'enabled': s.get('enabled')}.items() if v is not None}
                              for n, s in servers.items()}, **(defaults.get('mcp') or {})}
        org = {**org, 'defaults': defaults}
    if not isinstance(org.get('defaults', {}), dict):
        raise KitError('organization.toml: defaults must be a table ([defaults]).')
    teams = org.get('teams', {})
    if not isinstance(teams, dict) or not all(isinstance(v, dict) for v in teams.values()):
        raise KitError('organization.toml: teams must be tables, one per team ([teams.<team>]).')
    for name in teams:
        safe_id(name)
    return org


TRACKER_KINDS = ('gitlab', 'github')
TRACKER_SOURCES = ('agent', 'person', 'doctor')


def friction_tracker(org, personal, managed=None):
    """[friction_tracker] of organization.toml, validated, with its defaults, or None: no tracker, or the person wrote
    share_frictions = false. What the /friction script reads from state.json (runtime/friction.py)."""
    # 2.2: IT sets the tracker in managed.toml [frictions.tracker]; organization.toml [friction_tracker] is read as before.
    config = ((managed or {}).get('frictions') or {}).get('tracker', org.get('friction_tracker'))
    if config is None:
        return None
    if not isinstance(config, dict):
        raise KitError('organization.toml: friction_tracker must be a table ([friction_tracker]).')
    kind, project, host = config.get('kind'), config.get('project'), config.get('host', '')
    if kind not in TRACKER_KINDS:
        raise KitError('organization.toml: friction_tracker.kind must be gitlab or github.')
    if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+', project):
        raise KitError('organization.toml: friction_tracker.project must be the project path on the host (group/project), without URL.')
    if not isinstance(host, str) or (host and not re.fullmatch(r'[a-z0-9.-]+(:[0-9]+)?', host)):
        raise KitError('organization.toml: friction_tracker.host must be a host name (gitlab.example.org), without scheme or path.')
    labels = config.get('labels', ['friction'])
    if not isinstance(labels, list) or not all(isinstance(label, str) and re.fullmatch(r'[^,\s][^,]{0,49}', label) for label in labels):
        raise KitError('organization.toml: friction_tracker.labels must be a list of label names.')
    sources = config.get('sources', ['agent'])
    if not isinstance(sources, list) or not sources or any(source not in TRACKER_SOURCES for source in sources):
        raise KitError('organization.toml: friction_tracker.sources must list agent, person or doctor.')
    share = personal.get('share_frictions', True)
    if not isinstance(share, bool):
        raise KitError('overrides.toml: share_frictions must be true or false.')
    if not share:
        return None
    return {'kind': kind, 'project': project, 'host': host, 'labels': labels, 'sources': sources}


def team_settings(team):
    """The team's settings in organization.toml (same keys as overrides.toml), between the organization and the person; a V2
    Team's [defaults] (teams/<team>.toml in the active content) on top."""
    if not team:
        return {}
    layer = dict(organization().get('teams', {}).get(team, {}))
    layer.update(read_toml(content_root()/'teams'/(safe_id(team)+'.toml'), {}))
    return layer


def resolve_mcp(org_mcp, profile_mcp, personal_mcp, team_mcp=None):
    """MCP servers to install, by name, and the names chosen without a definition.
    organization.toml says how to reach each server, the profile which ones are active; the team (organization.toml teams)
    then the person (overrides.toml) adjust: true / false for a defined server, or a server of their own ([mcp.<name>.server])."""
    team_mcp = team_mcp or {}
    for label, entries in (('organization.toml', org_mcp), ('organization.toml teams', team_mcp), ('overrides.toml', personal_mcp)):
        if not isinstance(entries, dict):
            raise KitError(label+': mcp must be an object.')
    if not isinstance(profile_mcp, list) or not all(isinstance(n, str) for n in profile_mcp):
        raise KitError('Profile: mcp must be a list of server names.')
    defined, active = {}, set(profile_mcp)
    for source, entries in (('organization.toml', org_mcp), ('team', team_mcp), ('overrides.toml', personal_mcp)):
        for name, entry in entries.items():
            safe_id(name)
            if isinstance(entry, bool):
                if source == 'organization.toml':
                    raise KitError('organization.toml: mcp.'+name+' must describe the server ([mcp.'+name+'.server]).')
                if entry:
                    active.add(name)
                else:
                    active.discard(name)
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get('enabled', True), bool):
                raise KitError(source+': mcp.'+name+' must be true, false or a server ([mcp.'+name+'.server]).')
            if entry.get('server') is not None:
                defined[name] = validate_server(entry['server'])
            # An organization server is active only for the profiles that choose it, unless "enabled": true (everyone).
            # A person's entry is active unless "enabled": false (older format: "enabled": true with or without server).
            if entry.get('enabled', source != 'organization.toml'):
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
    """Keys of an overrides.toml (or organization defaults) the kit does not know: usually a typo. The schema is the list."""
    known = set(read_json(ROOT/'schemas'/'overrides.schema.json').get('properties', {}))
    return sorted(k for k in settings if not str(k).startswith(('_', '$')) and k not in known and k not in RETIRED_KEYS)


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


def allowed_domains():
    value = organization().get('allowed_domains', [])
    if not isinstance(value, list) or not all(isinstance(x,str) and x for x in value):
        raise KitError('organization.toml: allowed_domains must be a list of domains.')
    return [x.lower().lstrip('@') for x in value]


def domain_allowed(email, domains):
    return not domains or email.rsplit('@',1)[-1].lower() in domains


def team_ids():
    """Teams: those with their own practices (context/20-<team>.md, besides the shared 20-team.md) or their own settings
    (teams in organization.toml): context, tools, or both."""
    files = {p.stem[3:] for p in context_folder().glob('20-*.md') if p.stem != '20-team'}
    v2 = {p.stem for p in (content_root()/'teams').glob('*.toml')} if (content_root()/'teams').is_dir() else set()
    return sorted(files | set(organization().get('teams', {})) | v2)


def profile_practices(profile, team):
    """The profile's practices, with the shared team practice replaced by the person's team when it has its own file."""
    if team and team not in team_ids():
        raise KitError('Unknown team: '+team+'. Teams: '+(', '.join(team_ids()) or 'none (context/20-<team>.md or teams in organization.toml)'))
    own = team and (context_folder()/('20-'+team+'.md')).is_file()
    return [team if p == 'team' and own else p for p in profile['practices']]


# 0.26: skills renamed so that no skill shares a command's name (Gemini CLI turns every skill into a /command).
RENAMED_SKILLS = {'guide': 'routing', 'handoff': 'handover', 'research': 'investigation', 'retro': 'retrospective',
                  'triage': 'ticket-sorting', 'wizard': 'manual-steps'}


def resolve_skills(profile, overrides, catalog, log=print):
    """Final selection: profile + extra, replacements followed, dependencies added, disabled skills respected."""
    disabled = set(overrides.get('disabled_skills', []))
    selected = []
    def add(name, via=None):
        safe_id(name)
        if name not in catalog:
            raise KitError('Unknown skill: '+name)
        entry = catalog[name]
        if entry.get('replaced_by'):
            log('Skill replaced: '+name+' → '+', '.join(entry['replaced_by']))
            for replacement in entry['replaced_by']:
                add(replacement, via)
            return
        if name in disabled:
            if via:
                raise KitError('Skill '+name+' is disabled in overrides.toml but required by '+via+'.')
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
RETIRED_KEYS = ('vertex', 'code_assist', 'model', 'models')


def retired_key_notice(key):
    return ('[Info] overrides.toml: "'+key+'" is no longer handled by the kit (0.36): what it set before stays in your CLI\'s'
            ' configuration; change authentication or model in the CLI itself (docs/customization.md#authentication-and-model).')


def unknown_names(overrides, catalog, agent_catalog, notices):
    """disabled_skills and disabled_agents naming nothing the kit knows: a typo, reported, never silently ignored."""
    for key, known in (('disabled_skills', catalog), ('disabled_agents', agent_catalog)):
        unknown = [name for name in overrides.get(key, []) if name not in known]
        if unknown:
            notices.append('[Check] overrides.toml '+key+': unknown name '+', '.join(unknown)+' (a typo?); it has no effect.')


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


LEGACY_KIT_DIR = '.ai-toolkit'  # kit folder name before 0.19


def recorded_targets(state):
    """The CLIs the person chose at the last installation."""
    return state.get('targets') or (state.get('installed') or {}).get('clis') or None


PERSONAL_FILE = 'overrides.toml'


LEGACY_PERSONAL_FILE = 'overrides.json'  # before 0.37: becomes overrides.toml at the next setup or update


def personal_settings(kit):
    """The person's settings: ~/.ai-kit/aikit.toml (2.0) when it exists, translated to the engine's keys; otherwise
    ~/.ai-kit/overrides.toml, or the overrides.json of a version before 0.37 not converted yet."""
    from .config import AIKIT_FILE, load_aikit, to_overrides
    if (kit/AIKIT_FILE).exists():
        return to_overrides(load_aikit(kit/AIKIT_FILE)[0])
    if (kit/PERSONAL_FILE).exists() or not (kit/LEGACY_PERSONAL_FILE).exists():
        return read_toml(kit/PERSONAL_FILE, {})
    return read_json(kit/LEGACY_PERSONAL_FILE, {})


CHOICE_KEYS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
SCALAR_CHOICES = ('frictions',)  # a plain value the installer may write too (ai-kit friction --mode)
