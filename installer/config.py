"""managed.toml: the settings IT imposes on AI Kit (ADR 0015). Read from an administered path, never from an environment variable;
a closed schema; every key present wins, whatever its value (false, 0 and [] included); a key absent locks nothing. Values resolve
by precedence; restrictions (hooks.locked, mcp.denied) add to the other layers' restrictions and no other layer lifts them.
Applies to AI Kit only: it does not lock the workstation, the CLIs' own files or another program."""
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import sys

from .core import KitError, digest
from .toml_files import read_toml

MANAGED_SCHEMAS = {1}
FRICTION_CAPTURE = ('propose', 'auto', 'off')
FRICTION_PUBLICATION = ('approval', 'auto', 'disabled')
TRACKER_KEYS = ('kind', 'project', 'host', 'labels', 'sources')  # [frictions.tracker] is closed, like every table here
# Windows: who may own managed.toml and its folder. SYSTEM, the Administrators group, TrustedInstaller.
WINDOWS_TRUSTED_OWNERS = ('S-1-5-18', 'S-1-5-32-544', 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')


def _is_bool(value):
    return isinstance(value, bool)


def _is_texts(value):
    """A list of non-empty texts."""
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def _all_match(pattern):
    return lambda values: all(re.fullmatch(pattern, v) for v in values)


_BOOL = (_is_bool, 'must be true or false')
_TEXTS = (_is_texts, 'must be a list of texts')
_IDENTITIES = (_all_match(r'sha256:[0-9a-f]{64}'), 'lists server identities (sha256:<64 hex>, shown by ai-kit status --verbose)')
# The closed tables of managed.toml: table -> key -> checks in order, each (predicate, text); a failed check refuses the file with
# '<table>.<key> <text>'. A key absent from the file is never checked. [hooks] is not here: its keys are the lockable hooks.
MANAGED_RULES = {
    'mcp': {'allow_stdio': [_BOOL], 'denied': [_TEXTS], 'allowed_stdio': [_TEXTS, _IDENTITIES], 'allowed_http': [_TEXTS, _IDENTITIES]},
    'frictions': {
        'capture': [(lambda v: v in FRICTION_CAPTURE, 'must be '+', '.join(FRICTION_CAPTURE))],
        'publication': [(lambda v: v in FRICTION_PUBLICATION, 'must be '+', '.join(FRICTION_PUBLICATION))],
        'retention_days': [(lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1, 'must be a whole number of days, 1 or more')],
        # Its shape only: settings.friction_tracker checks its content and gives its defaults.
        'tracker': [(lambda v: isinstance(v, dict), 'must be a table: kind, project, host, labels, sources (kind, project, host, labels, sources)')],
    },
    'enterprise': {'core': [(lambda v: isinstance(v, str) and bool(v), 'must be the URL of the Core repository')]},
    'git': {  # Git sources (2.0, slice 2): the Core IT imposes, and the origins allowed.
        'allowed_hosts': [_TEXTS], 'allowed_groups': [_TEXTS],
        'allowed_schemes': [_TEXTS, (lambda v: set(v) <= {'https', 'ssh'}, 'accepts https and ssh only')],
        'allow_prerelease': [_BOOL],
        'revoked': [_TEXTS, (_all_match(r'[0-9a-f]{40}'), 'must list full commit SHAs (40 hexadecimal characters)')],
        'signers': [_TEXTS],
    },
    'teams': {'allowed': [(_is_texts, 'must be a list of Team repository URLs or URL prefixes')], 'allow_unknown': [_BOOL]},
}
MANAGED_TABLES = ('hooks', *MANAGED_RULES)
MANAGED_GIT = tuple(MANAGED_RULES['git'])


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
    """Why someone other than IT could change this file, or None."""
    path = Path(path)
    if os.name == 'nt':
        try:
            with open(path, 'r+b'):
                writable = True
        except OSError:
            writable = False
        return windows_ownership_problem(windows_owner(path), windows_owner(path.parent), writable)
    return posix_ownership_problem(path)


def posix_ownership_problem(path):
    """POSIX: a regular file (not a link) owned by root in a folder owned by root, neither writable by a group or by other
    users, and that the current user cannot write (an ACL the mode bits do not show). Run by root, the last check does
    not apply: root writes everything, which is who IT is."""
    path = Path(path)
    file, folder = os.lstat(path), os.lstat(path.parent)
    if stat.S_ISLNK(file.st_mode):
        return 'it is a symbolic link'
    if not stat.S_ISREG(file.st_mode):
        return 'it is not a regular file'
    if file.st_uid != 0:
        return 'it is not owned by root'
    if file.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return 'its group or other users can write it'
    if stat.S_ISLNK(folder.st_mode):
        return 'its folder is a symbolic link'
    if folder.st_uid != 0:
        return 'its folder is not owned by root'
    if folder.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return 'its folder is writable by its group or by other users'
    if os.geteuid() != 0 and (os.access(path, os.W_OK) or os.access(path.parent, os.W_OK)):
        return 'the current user can write it or its folder'
    return None


def windows_ownership_problem(file_owner, folder_owner, writable):
    """Windows: the file and its folder are owned by SYSTEM, Administrators or TrustedInstaller (owner SIDs), and the
    current user cannot open the file for writing. The owner decides: a person can create the file under C:\\ProgramData
    and set it read-only, which makes it unwritable but still theirs. An owner that cannot be read is refused."""
    if file_owner is None or folder_owner is None:
        return 'its owner or the owner of its folder cannot be read'
    if file_owner not in WINDOWS_TRUSTED_OWNERS:
        return 'it is owned by '+file_owner+', not by Administrators or SYSTEM (icacls <file> /setowner Administrators)'
    if folder_owner not in WINDOWS_TRUSTED_OWNERS:
        return 'its folder is owned by '+folder_owner+', not by Administrators or SYSTEM'
    if writable:
        return 'the current user can write it'
    return None


def windows_owner(path):
    """The owner SID of a file or folder as text (S-1-5-...), or None when it cannot be read. Windows only (advapi32)."""
    try:
        import ctypes
        from ctypes import wintypes
        advapi32, kernel32 = ctypes.WinDLL('advapi32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
        get_info = advapi32.GetNamedSecurityInfoW
        get_info.argtypes = [wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        get_info.restype = wintypes.DWORD
        to_text = advapi32.ConvertSidToStringSidW
        to_text.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        to_text.restype = wintypes.BOOL
        free = kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        owner, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        # SE_FILE_OBJECT = 1, OWNER_SECURITY_INFORMATION = 1; the owner points inside the descriptor, freed once.
        if get_info(str(path), 1, 1, ctypes.byref(owner), None, None, None, ctypes.byref(descriptor)) != 0:
            return None
        try:
            text = wintypes.LPWSTR()
            if not to_text(owner, ctypes.byref(text)):
                return None
            try:
                return text.value
            finally:
                free(ctypes.cast(text, ctypes.c_void_p))
        finally:
            free(descriptor)
    except Exception:  # noqa: BLE001 — unreadable for any reason: the caller refuses the file
        return None


def lockable_hooks():
    """What IT may name in [hooks]: the lockable hooks of the engine's own manifest, the same for every caller."""
    from .core import ROOT, lockable_names, read_json
    return lockable_names(read_json(ROOT/'runtime'/'hooks'/'hooks.json').get('hooks', {}))


def load_managed(path=None):
    """The validated content of managed.toml, or None when the file does not exist (not administered). Any other problem raises
    ManagedConfigError: unreadable, writable by the user, unknown key, wrong type, contradiction."""
    path = Path(path) if path is not None else managed_path()
    if not path.exists():
        return None
    lockable = lockable_hooks()

    def refuse(reason):
        raise ManagedConfigError(str(path)+': '+reason+'. Nothing was changed; ask IT to fix the file (docs/configuration.md).')
    problem = ownership_problem(path)
    if problem:
        refuse('refused because '+problem+'; an administered file must be changeable by IT only')
    try:
        data = read_toml(path)
    except KitError as exc:
        refuse('unreadable ('+str(exc)+')')
    if type(data.get('managed_schema')) is not int or data['managed_schema'] not in MANAGED_SCHEMAS:  # not True, not 1.0
        refuse('managed_schema must be one of '+', '.join(str(s) for s in sorted(MANAGED_SCHEMAS))+' (this AI Kit understands those)')
    allowed = {'managed_schema', *MANAGED_TABLES}
    unknown = sorted(set(data) - allowed)
    if unknown:
        refuse('unknown key '+', '.join(unknown)+' (this version applies: '+', '.join(sorted(allowed))+')')
    for table in MANAGED_TABLES:
        if table in data and not isinstance(data[table], dict):
            refuse('['+table+'] must be a table')
    hooks = data.get('hooks', {})
    follower = 'hooks.whats-new follows integrity: lock or set integrity instead'
    for name, value in hooks.items():
        if name == 'locked':
            if isinstance(value, list) and 'whats-new' in value:
                refuse(follower)
            if not isinstance(value, list) or not all(isinstance(n, str) and n in lockable for n in value):
                refuse('hooks.locked must list lockable hooks of the kit ('+', '.join(sorted(lockable))+')')
        elif name == 'whats-new':
            refuse(follower)
        elif name not in lockable:
            refuse('unknown hook hooks.'+name+' (lockable hooks: '+', '.join(sorted(lockable))+')')
        elif not isinstance(value, bool):
            refuse('hooks.'+name+' must be true or false')
    contradiction = [n for n in hooks.get('locked', []) if hooks.get(n) is False]
    if contradiction:
        refuse('hooks.locked contains '+', '.join(contradiction)+' while hooks.'+contradiction[0]+' = false')
    # The closed tables: their unknown keys first, then each key present, in the order of MANAGED_RULES.
    for table, rules in MANAGED_RULES.items():
        values = data.get(table, {})
        unknown = sorted(set(values) - set(rules))
        if unknown:
            refuse('unknown key '+', '.join(table+'.'+k for k in unknown))
        for key, checks in rules.items():
            if key in values:
                for check, text in checks:
                    if not check(values[key]):
                        refuse(table+'.'+key+' '+text)
    unknown = sorted(set(data.get('frictions', {}).get('tracker', {})) - set(TRACKER_KEYS))
    if unknown:
        refuse('unknown key '+', '.join('frictions.tracker.'+k for k in unknown)+' (this version applies: '+', '.join(TRACKER_KEYS)+')')
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
                notices.append('[Info] '+('Hook ' if name in ('integrity', 'whats-new') else 'Guardrail ')+name+' = '+str(mine[name]).lower()+' in your settings is ignored: IT sets it to '+str(value).lower()+' (managed.toml).')
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


FETCH_AND_RUN = ('npx', 'uvx', 'bunx', 'pnpx', 'pipx')


def unpinned_launcher(server):
    """A fetch-and-run launcher (npx, uvx...) whose package has no exact version: what runs changes without anyone seeing it."""
    from .settings import program
    if program(server.get('command')) not in FETCH_AND_RUN:
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
    """mcp.denied matches a server by name, by URL prefix (https://host/path) or by executable (name or full path), without
    case. A URL entry stops at a boundary: https://mcp.example.org denies that host (any port, any path), not
    https://mcp.example.org.other.test; https://host/api denies /api and /api/…, not /api2. An executable entry matches the
    file name with or without the extension Windows adds (npx denies npx.cmd)."""
    from .settings import program
    address = (server.get('httpUrl') or server.get('url') or '').lower()
    command = str(server.get('command') or '').replace('\\', '/').lower()
    for entry in denied:
        if entry == short:
            return True
        lowered = str(entry).replace('\\', '/').lower()
        if address and '://' in lowered and address.startswith(lowered) and (
                len(address) == len(lowered) or lowered.endswith('/') or address[len(lowered)] in '/?#:'):
            return True
        if command and lowered in (command, command.rsplit('/', 1)[-1], program(command)):
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
    locked = (managed.get('hooks') or {}).get('locked') or []
    return 'Managed by IT: '+str(path or managed_path())+' (sets '+(', '.join(keys) if keys else 'nothing')+(('; locks '+', '.join(locked)) if locked else '')+').'


# --- ~/.ai-kit/aikit.toml: the person's V2 settings (docs/configuration.md) ---------------------------------

AIKIT_FILE = 'aikit.toml'
AIKIT_SCHEMAS = {1}
USER_LISTS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')
AIKIT_SECTIONS = {'user': USER_LISTS + ('skill_prefix', 'active_team'), 'hooks': None, 'mcp': ('denied', 'enabled'), 'frictions': ('capture', 'publication'),
                  'agents': ('parallel',), 'core': ('repo',), 'git': ('allow_prerelease',), 'teams': None}
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
            if (section, key) == ('agents', 'parallel') and not isinstance(value, bool):
                raise KitError(where+': agents.parallel must be true or false.')
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
    if 'parallel' in data.get('agents', {}):
        out['parallel_agents'] = data['agents']['parallel']
    return out


# --- The content's manifest: aikit.toml at the root of a content tree (a Core source later) ------------------------------

SOURCE_SCHEMAS = {1}
TEAM_DEFAULTS = ('extra_skills', 'extra_agents', 'extra_commands', 'disabled_skills', 'disabled_agents', 'disabled_commands')
TEAM_SWITCHES = ('parallel_agents',)  # true or false: the Team's default, the person's aikit.toml on top


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
    if not isinstance(defaults, dict) or set(defaults) - set(TEAM_DEFAULTS) - set(TEAM_SWITCHES) or not all(
            isinstance(v, bool) if k in TEAM_SWITCHES else isinstance(v, list) and all(isinstance(n, str) and n for n in v)
            for k, v in defaults.items()):
        raise KitError(where+': [defaults] accepts lists of names ('+', '.join(TEAM_DEFAULTS)+') and true or false for '+', '.join(TEAM_SWITCHES)+'.')
    try:
        needed = version_tuple(data.get('min_engine', '0.0.0'))
    except ValueError:
        raise KitError(where+': min_engine must be a version X.Y.Z.') from None
    if needed > version_tuple(engine_version):
        raise KitError('The content '+data['name']+' needs AI Kit '+data['min_engine']+' or newer; this one is '+engine_version
                       +'. Update AI Kit first; nothing was changed.')
    return data
