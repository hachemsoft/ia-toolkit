"""managed.toml: the settings IT imposes on AI Kit (ADR 0015). Read from an administered path, never from an environment variable;
a closed schema; every key present wins, whatever its value (false, 0 and [] included); a key absent locks nothing. Values resolve
by precedence; restrictions (hooks.locked, mcp.denied) add to the other layers' restrictions and no other layer lifts them.
Applies to AI Kit only: it does not lock the workstation, the CLIs' own files or another program."""
import hashlib
import json
import os
import re
from pathlib import Path
import sys

from .core import KitError, digest
from .toml_files import read_toml

MANAGED_SCHEMAS = {1}
MANAGED_GIT = ('allowed_hosts', 'allowed_groups', 'allowed_schemes', 'allow_prerelease', 'revoked', 'signers')
FRICTION_CAPTURE = ('propose', 'auto', 'off')
FRICTION_PUBLICATION = ('approval', 'auto', 'disabled')


class ManagedConfigError(KitError):
    """managed.toml is present but cannot be applied: nothing is changed (exit code 3)."""


def managed_path():
    """The administered location. Fixed per OS so that an environment variable cannot move it away."""
    if os.name == 'nt':
        return Path(r'C:\ProgramData\ai-kit\managed.toml')
    if sys.platform == 'darwin':
        return Path('/Library/Application Support/ai-kit/managed.toml')
    return Path('/etc/ai-kit/managed.toml')


def ownership_problem(path):
    """Why the current user could change this file, or None. POSIX: owned by root, neither the file nor its folder writable by the
    user. Windows: the user cannot open it for writing (the read-only attribute alone is not enough)."""
    if os.name == 'nt':
        try:
            with open(path, 'r+b'):
                pass
        except OSError:
            return None
        return 'the current user can write it'
    if os.stat(path).st_uid != 0:
        return 'it is not owned by root'
    if os.access(path, os.W_OK) or os.access(path.parent, os.W_OK):
        return 'the current user can write it or its folder'
    return None


def load_managed(path=None, guardrail_names=()):
    """The validated content of managed.toml, or None when the file does not exist (not administered). Any other problem raises
    ManagedConfigError: unreadable, writable by the user, unknown key, wrong type, contradiction."""
    path = Path(path) if path is not None else managed_path()
    if not path.exists():
        return None
    def refuse(reason):
        raise ManagedConfigError(str(path)+': '+reason+'. Nothing was changed; ask IT to fix the file (docs/configuration.md).')
    problem = ownership_problem(path)
    if problem:
        refuse('refused because '+problem+'; an administered file must be changeable by IT only')
    try:
        data = read_toml(path)
    except KitError as exc:
        refuse('unreadable ('+str(exc)+')')
    if data.get('managed_schema') not in MANAGED_SCHEMAS or isinstance(data.get('managed_schema'), bool):
        refuse('managed_schema must be one of '+', '.join(str(s) for s in sorted(MANAGED_SCHEMAS))+' (this AI Kit understands those)')
    allowed = {'managed_schema', 'hooks', 'mcp', 'frictions', 'enterprise', 'git', 'teams'}
    unknown = sorted(set(data) - allowed)
    if unknown:
        refuse('unknown key '+', '.join(unknown)+' (this version applies: '+', '.join(sorted(allowed))+')')
    for table in ('hooks', 'mcp', 'frictions', 'enterprise', 'git', 'teams'):
        if table in data and not isinstance(data[table], dict):
            refuse('['+table+'] must be a table')
    hooks, mcp, frictions = data.get('hooks', {}), data.get('mcp', {}), data.get('frictions', {})
    for name, value in hooks.items():
        if name == 'locked':
            if not isinstance(value, list) or not all(isinstance(n, str) and n in guardrail_names for n in value):
                refuse('hooks.locked must list guardrails of the kit ('+', '.join(sorted(guardrail_names))+')')
        elif name not in guardrail_names:
            refuse('unknown guardrail hooks.'+name+' (guardrails: '+', '.join(sorted(guardrail_names))+')')
        elif not isinstance(value, bool):
            refuse('hooks.'+name+' must be true or false')
    contradiction = [n for n in hooks.get('locked', []) if hooks.get(n) is False]
    if contradiction:
        refuse('hooks.locked contains '+', '.join(contradiction)+' while hooks.'+contradiction[0]+' = false')
    unknown = sorted(set(mcp) - {'allow_stdio', 'denied', 'allowed_stdio', 'allowed_http'})
    if unknown:
        refuse('unknown key mcp.'+', mcp.'.join(unknown))
    if 'allow_stdio' in mcp and not isinstance(mcp['allow_stdio'], bool):
        refuse('mcp.allow_stdio must be true or false')
    for key in ('denied', 'allowed_stdio', 'allowed_http'):
        if key in mcp and (not isinstance(mcp[key], list) or not all(isinstance(n, str) and n for n in mcp[key])):
            refuse('mcp.'+key+' must be a list of texts')
    for key in ('allowed_stdio', 'allowed_http'):
        if any(not re.fullmatch(r'sha256:[0-9a-f]{64}', v) for v in mcp.get(key, [])):
            refuse('mcp.'+key+' lists server identities (sha256:<64 hex>, shown by ai-kit status --verbose)')
    unknown = sorted(set(frictions) - {'capture', 'publication', 'retention_days', 'tracker'})
    if unknown:
        refuse('unknown key frictions.'+', frictions.'.join(unknown))
    if 'capture' in frictions and frictions['capture'] not in FRICTION_CAPTURE:
        refuse('frictions.capture must be '+', '.join(FRICTION_CAPTURE))
    if 'publication' in frictions and frictions['publication'] not in FRICTION_PUBLICATION:
        refuse('frictions.publication must be '+', '.join(FRICTION_PUBLICATION))
    if 'tracker' in frictions and not isinstance(frictions['tracker'], dict):
        refuse('frictions.tracker must be a table: kind, project, host, labels, sources (kind, project, host, labels, sources)')
    if 'retention_days' in frictions and (not isinstance(frictions['retention_days'], int) or isinstance(frictions['retention_days'], bool) or frictions['retention_days'] < 1):
        refuse('frictions.retention_days must be a whole number of days, 1 or more')
    # Git sources (2.0, slice 2): the Core IT imposes, and the origins allowed.
    enterprise, git = data.get('enterprise', {}), data.get('git', {})
    unknown = sorted(set(enterprise) - {'core'}) + sorted('git.'+k for k in set(git) - set(MANAGED_GIT))
    if unknown:
        refuse('unknown key '+', '.join(k if k.startswith('git.') else 'enterprise.'+k for k in unknown))
    if 'core' in enterprise and (not isinstance(enterprise['core'], str) or not enterprise['core']):
        refuse('enterprise.core must be the URL of the Core repository')
    for key in ('allowed_hosts', 'allowed_groups', 'allowed_schemes', 'revoked', 'signers'):
        if key in git and (not isinstance(git[key], list) or not all(isinstance(v, str) and v for v in git[key])):
            refuse('git.'+key+' must be a list of texts')
    if not set(git.get('allowed_schemes', [])) <= {'https', 'ssh'}:
        refuse('git.allowed_schemes accepts https and ssh only')
    if any(not re.fullmatch(r'[0-9a-f]{40}', v) for v in git.get('revoked', [])):
        refuse('git.revoked must list full commit SHAs (40 hexadecimal characters)')
    if 'allow_prerelease' in git and not isinstance(git['allow_prerelease'], bool):
        refuse('git.allow_prerelease must be true or false')
    teams = data.get('teams', {})
    unknown = sorted(set(teams) - {'allowed', 'allow_unknown'})
    if unknown:
        refuse('unknown key teams.'+', teams.'.join(unknown))
    if 'allowed' in teams and (not isinstance(teams['allowed'], list) or not all(isinstance(v, str) and v for v in teams['allowed'])):
        refuse('teams.allowed must be a list of Team repository URLs or URL prefixes')
    if 'allow_unknown' in teams and not isinstance(teams['allow_unknown'], bool):
        refuse('teams.allow_unknown must be true or false')
    return data


def apply_values(overrides, managed):
    """The merged settings with managed values on top (guardrail switches, frictions capture), and one notice per personal value
    that a managed one replaces."""
    if not managed:
        return overrides, []
    result, notices = dict(overrides), []
    hooks = {k: v for k, v in managed.get('hooks', {}).items() if k != 'locked'}
    if hooks:
        mine = dict(result.get('hooks', {}))
        for name, value in hooks.items():
            if name in mine and mine[name] != value:
                notices.append('[Info] Guardrail '+name+' = '+str(mine[name]).lower()+' in your settings is ignored: IT sets it to '+str(value).lower()+' (managed.toml).')
            mine[name] = value
        result['hooks'] = mine
    capture = managed.get('frictions', {}).get('capture')
    if capture is not None:
        if result.get('frictions', 'propose') != capture and 'frictions' in result:
            notices.append('[Info] frictions = '+result['frictions']+' in your settings is ignored: IT sets '+capture+' (managed.toml).')
        result['frictions'] = capture
    return result, notices


def locked_guardrails(managed):
    """Guardrails IT keeps on, whatever a Team or a person writes."""
    return list((managed or {}).get('hooks', {}).get('locked', []))


MCP_KEYS = ('command', 'args', 'env', 'cwd', 'httpUrl', 'url', 'headers', 'required')
SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'cmd', 'cmd.exe', 'powershell', 'powershell.exe', 'pwsh', 'pwsh.exe')


def server_warnings(short, server):
    """What AI Kit reports but still installs (ADR 0022): a key outside the closed schema, a shell as the command or a -c script (anything can then run, unseen by the CLI's approval)."""
    found = ['[Check] MCP server '+short+': unknown key '+k+' (AI Kit knows '+', '.join(MCP_KEYS)+'); AI Kit does not check it.'
             for k in sorted(set(server) - set(MCP_KEYS))]
    command = str(server.get('command') or '')
    if command and (Path(command.replace('\\', '/')).name.lower() in SHELLS or re.search(r'[;&|`$<>]', command)
                    or any(a in ('-c', '/c', '-Command', '-EncodedCommand') for a in server.get('args') or [])):
        found.append('[Check] MCP server '+short+': runs a shell or a shell script ('+command+'); name the program itself.')
    return found


FETCH_AND_RUN = ('npx', 'uvx', 'bunx', 'pnpx', 'pipx')


def unpinned_launcher(server):
    """A fetch-and-run launcher (npx, uvx...) whose package has no exact version: what runs changes without anyone seeing it."""
    command = Path(str(server.get('command') or '').replace('\\', '/')).name.lower()
    if command not in FETCH_AND_RUN:
        return False
    packages = [a for a in server.get('args') or [] if not a.startswith('-') and a not in ('run', 'dlx', 'exec')]
    return not packages or not any(('==' in a) or re.search(r'@\d', a) for a in packages[:1])


def team_mcp_gate(enabled_mcp, team_servers, managed, approved, approve=None):
    """ADR 0022 for the servers a Team brings: a local (stdio) one is kept only when its exact identity is listed by IT
    (mcp.allowed_stdio) or approved on this workstation (state.json mcp_approvals, asked in a terminal through approve);
    an unpinned fetch-and-run launcher is refused. Returns (kept, notices, approvals)."""
    allowed = set(((managed or {}).get('mcp') or {}).get('allowed_stdio') or [])
    kept, notices, approvals = {}, [], set(approved or [])
    for name, server in enabled_mcp.items():
        short = name[len('ai-kit-'):]
        if short not in team_servers or not server.get('command'):
            kept[name] = server
            continue
        identity = server_identity(server)
        why = None
        if unpinned_launcher(server):
            why = 'its launcher fetches a package without an exact version'
        elif identity not in allowed and identity not in approvals:
            if approve and approve('The Team adds a local MCP server '+short+' that runs: '+' '.join([server['command']]+list(server.get('args') or []))
                                   + ' (identity '+identity[:19]+'...). Allow it on this workstation?'):
                approvals.add(identity)
            else:
                why = 'a local server from a Team needs your approval in a terminal (or IT lists its identity in mcp.allowed_stdio)'
        if why and team_servers[short].get('required'):
            raise KitError('MCP server '+short+' is required by the Team but '+why+': nothing was changed.')
        if why:
            notices.append('[Info] MCP server '+short+' not installed: '+why+'.')
        else:
            kept[name] = server
    return kept, notices, sorted(approvals)


def server_identity(server):
    """The exact identity of an MCP server (ADR 0022): sha256 of its command, args, env templates and cwd (stdio), or of its URL
    and header templates (http). A name is not an identity: a rename does not change it, a changed argument does."""
    if server.get('command'):
        material = {'command': server['command'], 'args': list(server.get('args') or []), 'env': dict(sorted((server.get('env') or {}).items())),
                    'cwd': server.get('cwd') or ''}
    else:
        material = {'url': server.get('httpUrl') or server.get('url'), 'headers': dict(sorted((server.get('headers') or {}).items()))}
    return 'sha256:'+hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def denied_match(short, server, denied):
    """mcp.denied matches a server by name, by URL prefix (https://host/path) or by executable (name or full path)."""
    address = server.get('httpUrl') or server.get('url') or ''
    command = str(server.get('command') or '')
    for entry in denied:
        if entry == short or (address and '://' in entry and address.startswith(entry)) or (
                command and (entry == command or entry == Path(command.replace('\\', '/')).name)):
            return True
    return False


def filter_mcp(enabled_mcp, managed):
    """The MCP servers to install without those IT refuses (mcp.denied by name, URL prefix or executable; every stdio server when
    mcp.allow_stdio = false; when IT lists identities in mcp.allowed_stdio or mcp.allowed_http, any server of that transport
    whose exact identity is not listed), and the notices. A refused server marked required = true stops the installation;
    required itself is AI Kit's, never written into a CLI. Names carry the ai-kit- prefix."""
    mcp = (managed or {}).get('mcp', {})
    denied, stdio = mcp.get('denied', []), mcp.get('allow_stdio', True)
    allowed_stdio, allowed_http = mcp.get('allowed_stdio'), mcp.get('allowed_http')
    kept, notices = {}, []
    for name, server in enabled_mcp.items():
        short = name[len('ai-kit-'):] if name.startswith('ai-kit-') else name
        notices += server_warnings(short, server)
        local, identity = bool(server.get('command')), server_identity(server)
        why = ('refused by IT (managed.toml mcp.denied)' if denied_match(short, server, denied)
               else 'local (stdio) servers are refused by IT (managed.toml mcp.allow_stdio = false)' if not stdio and local
               else 'its identity '+identity+' is not in managed.toml mcp.allowed_stdio' if local and allowed_stdio is not None and identity not in allowed_stdio
               else 'its identity '+identity+' is not in managed.toml mcp.allowed_http' if not local and allowed_http is not None and identity not in allowed_http
               else None)
        if why and server.get('required') is True:
            raise KitError('MCP server '+short+' is required but '+why+': nothing was changed. Ask IT or the owner of the source.')
        if why:
            notices.append('[Info] MCP server '+short+' not installed: '+why+'.')
        else:
            kept[name] = {k: v for k, v in server.items() if k != 'required'}
    return kept, notices


def publication(managed):
    """How frictions reach the tracker: approval (default: the person sends them from a terminal), auto (as soon as logged) or
    disabled. A person who wrote share_frictions = false keeps them local in every case (a restriction of their own)."""
    return (managed or {}).get('frictions', {}).get('publication', 'approval')


def managed_digest(path=None):
    """The SHA-256 of the managed file as applied, recorded in state.json: doctor sees when IT changed it since the last update."""
    path = Path(path) if path is not None else managed_path()
    return digest(path.read_bytes()) if path.is_file() else None


def drift(recorded, path=None):
    """Why the applied managed settings are out of date, or None: IT added, changed or removed the file since the last update."""
    current = managed_digest(path)
    if current == recorded:
        return None
    if recorded is None:
        return 'IT added managed.toml since the last update: run ai-kit sync --offline to apply it'
    if current is None:
        return 'IT removed managed.toml since the last update: run ai-kit sync --offline'
    return 'IT changed managed.toml since the last update: run ai-kit sync --offline to apply it'


def provenance(org_defaults, team_layer, personal, managed=None):
    """Where each effective setting comes from: {key: 'Core' | 'team' | 'you' | 'IT'}, the highest layer that sets it.
    Guardrail switches are listed one by one (hooks.<name>); IT's frictions.capture sets the person's frictions key."""
    def flat(layer):
        out = {}
        for key, value in (layer or {}).items():
            if key == 'hooks' and isinstance(value, dict):
                out.update({'hooks.'+n: v for n, v in value.items()})
            else:
                out[key] = value
        return out
    it = {'hooks.'+n: v for n, v in (managed or {}).get('hooks', {}).items() if n != 'locked'}
    if 'capture' in (managed or {}).get('frictions', {}):
        it['frictions'] = managed['frictions']['capture']
    origin = {}
    for label, layer in (('Core', flat(org_defaults)), ('team', flat(team_layer)), ('you', flat(personal)), ('IT', it)):
        origin.update({key: label for key in layer})
    return dict(sorted(origin.items()))


def summary(managed, path=None):
    """One line for doctor: where the managed file is and which keys it sets."""
    if managed is None:
        return None
    keys = sorted(k for k in managed if k != 'managed_schema')
    return 'Managed by IT: '+str(path or managed_path())+' (sets '+(', '.join(keys) if keys else 'nothing')+').'


# --- ~/.ai-kit/aikit.toml: the person's V2 settings (docs/configuration.md) ---------------------------------

AIKIT_FILE = 'aikit.toml'
AIKIT_SCHEMAS = {1}
USER_LISTS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
AIKIT_SECTIONS = {'user': USER_LISTS + ('skill_prefix', 'active_team'), 'hooks': None, 'mcp': ('denied', 'enabled'), 'frictions': ('capture', 'publication'),
                  'core': ('repo',), 'git': ('allow_prerelease',), 'teams': None}
PERSONAL_PUBLICATION = ('approval', 'disabled')  # the person can only restrict (auto is set by IT or the organization)


def load_aikit(path):
    """The validated person's aikit.toml and its warnings. A wrong type or schema stops the command (KitError); an unknown key
    is a warning, shown by doctor and update, so that a newer file still works with this engine."""
    path = Path(path)
    data = read_toml(path)
    where = '~/.ai-kit/'+AIKIT_FILE
    if data.get('schema') not in AIKIT_SCHEMAS or isinstance(data.get('schema'), bool):
        raise KitError(where+': schema must be one of '+', '.join(str(s) for s in sorted(AIKIT_SCHEMAS))+'.')
    warnings = ['[Check] '+where+': unknown key '+k+', ignored.' for k in sorted(set(data) - set(AIKIT_SECTIONS) - {'schema'})]
    for section, keys in AIKIT_SECTIONS.items():
        table = data.get(section, {})
        if not isinstance(table, dict):
            raise KitError(where+': ['+section+'] must be a table.')
        if keys is not None:
            warnings += ['[Check] '+where+': unknown key '+section+'.'+k+', ignored.' for k in sorted(set(table) - set(keys))]
        for key, value in table.items():
            name = section+'.'+key
            if section == 'teams':
                if not isinstance(value, dict) or set(value) - {'repo'} or not isinstance(value.get('repo'), str) or not value.get('repo'):
                    raise KitError(where+': [teams.'+key+'] must hold repo = "<URL of the Team repository>".')
                continue
            if key == 'active_team' and not isinstance(value, str):
                raise KitError(where+': user.active_team must be a Team name or "none".')
            if section == 'hooks' and not isinstance(value, bool):
                raise KitError(where+': '+name+' must be true or false.')
            if (key in USER_LISTS or section == 'mcp') and not (isinstance(value, list) and all(isinstance(v, str) and v for v in value)):
                raise KitError(where+': '+name+' must be a list of names.')
            if key == 'skill_prefix' and not isinstance(value, str):
                raise KitError(where+': '+name+' must be a text.')
            if key == 'capture' and value not in FRICTION_CAPTURE:
                raise KitError(where+': '+name+' must be '+', '.join(FRICTION_CAPTURE)+'.')
            if (section, key) == ('core', 'repo') and (not isinstance(value, str) or not value):
                raise KitError(where+': core.repo must be the URL of the Core repository.')
            if (section, key) == ('git', 'allow_prerelease') and not isinstance(value, bool):
                raise KitError(where+': git.allow_prerelease must be true or false.')
            if key == 'publication' and value not in PERSONAL_PUBLICATION:
                raise KitError(where+': '+name+' must be '+' or '.join(PERSONAL_PUBLICATION)+' (auto is set by IT or the organization).')
    return data, warnings


def to_overrides(data):
    """aikit.toml in the engine's settings vocabulary (the keys of aikit.toml), so that one resolver serves both files."""
    user, mcp, frictions = data.get('user', {}), data.get('mcp', {}), data.get('frictions', {})
    out = {k: list(user[k]) for k in USER_LISTS if k in user}
    if 'skill_prefix' in user:
        out['skill_prefix'] = user['skill_prefix']
    if data.get('hooks'):
        out['hooks'] = dict(data['hooks'])
    servers = {**{n: True for n in mcp.get('enabled', [])}, **{n: False for n in mcp.get('denied', [])}}  # a refusal wins
    if servers:
        out['mcp'] = servers
    if 'capture' in frictions:
        out['frictions'] = frictions['capture']
    if frictions.get('publication') == 'disabled':
        out['share_frictions'] = False
    return out


# --- The content's manifest: aikit.toml at the root of a content tree (a Core source later) ------------------------------

SOURCE_SCHEMAS = {1}
TEAM_DEFAULTS = ('extra_skills', 'extra_agents', 'extra_commands', 'disabled_skills', 'disabled_agents', 'disabled_commands')


def version_tuple(text):
    parts = str(text).split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(text)
    return tuple(int(p) for p in parts)


def check_source(root, engine_version):
    """The content tree's manifest (name, min_engine), or None when it has none. Refuses a content that needs a
    newer engine: installing it with an older one would install resources it cannot apply."""
    path = Path(root)/AIKIT_FILE
    if not path.is_file():
        return None
    data = read_toml(path)
    where = str(path)
    if data.get('schema') not in SOURCE_SCHEMAS or isinstance(data.get('schema'), bool):
        raise KitError(where+': schema must be one of '+', '.join(str(s) for s in sorted(SOURCE_SCHEMAS))+'.')
    unknown = sorted(set(data) - {'schema', 'name', 'kind', 'min_engine', 'defaults'})
    if unknown:
        raise KitError(where+': unknown key '+', '.join(unknown)+'.')
    if not isinstance(data.get('name'), str) or not data['name']:
        raise KitError(where+': name must be a text.')
    if data.get('kind', 'core') not in ('core', 'team'):
        raise KitError(where+': kind must be core or team.')
    defaults = data.get('defaults', {})
    if 'defaults' in data and data.get('kind') != 'team':
        raise KitError(where+': [defaults] is for a Team repository (kind = "team").')
    if not isinstance(defaults, dict) or set(defaults) - set(TEAM_DEFAULTS) or not all(
            isinstance(v, list) and all(isinstance(n, str) and n for n in v) for v in defaults.values()):
        raise KitError(where+': [defaults] accepts lists of names: '+', '.join(TEAM_DEFAULTS)+'.')
    try:
        needed = version_tuple(data.get('min_engine', '0.0.0'))
    except ValueError:
        raise KitError(where+': min_engine must be a version X.Y.Z.') from None
    if needed > version_tuple(engine_version):
        raise KitError('The content '+data['name']+' needs AI Kit '+data['min_engine']+' or newer; this one is '+engine_version
                       +'. Update AI Kit first; nothing was changed.')
    return data
