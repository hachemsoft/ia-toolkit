"""Settings: the organization, team and personal layers, profiles, and what they resolve to (skills, commands, MCP servers)."""
import getpass
import os
import re
import shutil
import subprocess

from .core import (ROOT, KIT_CONTEXT, EMAIL, SECRET, KitError, read_json, safe_id)
from .toml_files import read_toml
from .adapters import ADAPTERS


def practice_file(practice_id):
    """Source file of a practice and name of the context file it produces."""
    safe_id(practice_id)
    matches = sorted((ROOT/'practices').glob('[0-9][0-9]-'+practice_id+'.md'))
    if len(matches) != 1:
        raise KitError('Practice not found or ambiguous: ' + practice_id)
    source = matches[0]
    return source, source.stem[:2]+'_'+practice_id.upper().replace('-','_')+'.md'


def profile_menu():
    """(id, label) of every profile in profiles/, sorted by its "order": adding a profile is adding one file."""
    profiles = [read_toml(p) for p in sorted((ROOT/'profiles').glob('*.toml'))]
    return [(p['id'], p.get('label') or p['id']) for p in sorted(profiles, key=lambda p: (p.get('order', 1000), p['id']))]


def profile_ids():
    return sorted(p.stem for p in (ROOT/'profiles').glob('*.toml'))


def load_profile(profile_id):
    """profiles/<id>.toml: the skills, commands, agents and MCP servers of a job."""
    path = ROOT/'profiles'/(safe_id(profile_id)+'.toml')
    if not path.exists():
        raise KitError('Unknown profile: '+profile_id+'. Profiles: '+', '.join(profile_ids()))
    return read_toml(path)


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
    # Never preselect automatic trust.
    if server.get('trust') is True:
        raise KitError('MCP: trust=true is not supported by this kit.')
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
    """organization.toml at the root of the kit: what the organization decides (expected email domains, defaults, teams)."""
    org = read_toml(ROOT/'organization.toml', {})
    if not isinstance(org.get('defaults', {}), dict):
        raise KitError('organization.toml: defaults must be a table ([defaults]).')
    teams = org.get('teams', {})
    if not isinstance(teams, dict) or not all(isinstance(v, dict) for v in teams.values()):
        raise KitError('organization.toml: teams must be tables, one per team ([teams.<team>]).')
    for name in teams:
        safe_id(name)
    return org


def team_settings(team):
    """The team's settings in organization.toml (same keys as overrides.toml), between the organization and the person."""
    return organization().get('teams', {}).get(team, {}) if team else {}


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
    """Teams: those with their own practices (practices/20-<team>.md, besides the shared 20-team.md) or their own settings
    (teams in organization.toml): context, tools, or both."""
    files = {p.stem[3:] for p in (ROOT/'practices').glob('20-*.md') if p.stem != '20-team'}
    return sorted(files | set(organization().get('teams', {})))


def profile_practices(profile, team):
    """The profile's practices, with the shared team practice replaced by the person's team when it has its own file."""
    if team and team not in team_ids():
        raise KitError('Unknown team: '+team+'. Teams: '+(', '.join(team_ids()) or 'none (practices/20-<team>.md or teams in organization.toml)'))
    own = team and (ROOT/'practices'/('20-'+team+'.md')).is_file()
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
    """The person's settings: ~/.ai-kit/overrides.toml, or the overrides.json of a version before 0.37 not converted yet."""
    if (kit/PERSONAL_FILE).exists() or not (kit/LEGACY_PERSONAL_FILE).exists():
        return read_toml(kit/PERSONAL_FILE, {})
    return read_json(kit/LEGACY_PERSONAL_FILE, {})


CHOICE_KEYS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
SCALAR_CHOICES = ('frictions',)  # a plain value the installer may write too (ai-kit friction --mode)
