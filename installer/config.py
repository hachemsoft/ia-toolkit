"""managed.toml: the settings IT imposes on AI Kit (ADR 0015). Read from an administered path, never from an environment variable;
a closed schema; every key present wins, whatever its value (false, 0 and [] included); a key absent locks nothing. Values resolve
by precedence; restrictions (hooks.locked, mcp.denied) add to the other layers' restrictions and no other layer lifts them.
Applies to AI Kit only: it does not lock the workstation, the CLIs' own files or another program."""
import os
from pathlib import Path
import sys

from .core import KitError, digest
from .toml_files import read_toml

MANAGED_SCHEMAS = {1}
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
        raise ManagedConfigError(str(path)+': '+reason+'. Nothing was changed; ask IT to fix the file (docs/v2/config.md).')
    problem = ownership_problem(path)
    if problem:
        refuse('refused because '+problem+'; an administered file must be changeable by IT only')
    try:
        data = read_toml(path)
    except KitError as exc:
        refuse('unreadable ('+str(exc)+')')
    if data.get('managed_schema') not in MANAGED_SCHEMAS or isinstance(data.get('managed_schema'), bool):
        refuse('managed_schema must be one of '+', '.join(str(s) for s in sorted(MANAGED_SCHEMAS))+' (this AI Kit understands those)')
    allowed = {'managed_schema', 'hooks', 'mcp', 'frictions'}
    unknown = sorted(set(data) - allowed)
    if unknown:
        refuse('unknown key '+', '.join(unknown)+' (this version applies: '+', '.join(sorted(allowed))+')')
    for table in ('hooks', 'mcp', 'frictions'):
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
    unknown = sorted(set(mcp) - {'allow_stdio', 'denied'})
    if unknown:
        refuse('unknown key mcp.'+', mcp.'.join(unknown))
    if 'allow_stdio' in mcp and not isinstance(mcp['allow_stdio'], bool):
        refuse('mcp.allow_stdio must be true or false')
    if 'denied' in mcp and (not isinstance(mcp['denied'], list) or not all(isinstance(n, str) and n for n in mcp['denied'])):
        refuse('mcp.denied must be a list of server names')
    unknown = sorted(set(frictions) - {'capture', 'publication'})
    if unknown:
        refuse('unknown key frictions.'+', frictions.'.join(unknown))
    if 'capture' in frictions and frictions['capture'] not in FRICTION_CAPTURE:
        refuse('frictions.capture must be '+', '.join(FRICTION_CAPTURE))
    if 'publication' in frictions and frictions['publication'] not in FRICTION_PUBLICATION:
        refuse('frictions.publication must be '+', '.join(FRICTION_PUBLICATION))
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
    """Guardrails IT keeps on (a restriction: added to organization.toml locked_hooks)."""
    return list((managed or {}).get('hooks', {}).get('locked', []))


def filter_mcp(enabled_mcp, managed):
    """The MCP servers to install without those IT refuses (mcp.denied by name, every stdio server when mcp.allow_stdio = false);
    one notice per server removed. Names in enabled_mcp carry the ai-kit- prefix."""
    if not managed:
        return enabled_mcp, []
    mcp = managed.get('mcp', {})
    denied, stdio = set(mcp.get('denied', [])), mcp.get('allow_stdio', True)
    kept, notices = {}, []
    for name, server in enabled_mcp.items():
        short = name[len('ai-kit-'):] if name.startswith('ai-kit-') else name
        if short in denied:
            notices.append('[Info] MCP server '+short+' not installed: refused by IT (managed.toml mcp.denied).')
        elif not stdio and 'command' in server:
            notices.append('[Info] MCP server '+short+' not installed: local (stdio) servers are refused by IT (managed.toml mcp.allow_stdio = false).')
        else:
            kept[name] = server
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
        return 'IT added managed.toml since the last update: run ai-kit update to apply it'
    if current is None:
        return 'IT removed managed.toml since the last update: run ai-kit update'
    return 'IT changed managed.toml since the last update: run ai-kit update to apply it'


def provenance(org_defaults, team_layer, personal, managed=None):
    """Where each effective setting comes from: {key: 'organization' | 'team' | 'you' | 'IT'}, the highest layer that sets it.
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
    for label, layer in (('organization', flat(org_defaults)), ('team', flat(team_layer)), ('you', flat(personal)), ('IT', it)):
        origin.update({key: label for key in layer})
    return dict(sorted(origin.items()))


def summary(managed, path=None):
    """One line for doctor: where the managed file is and which keys it sets."""
    if managed is None:
        return None
    keys = sorted(k for k in managed if k != 'managed_schema')
    return 'Managed by IT: '+str(path or managed_path())+' (sets '+(', '.join(keys) if keys else 'nothing')+').'
