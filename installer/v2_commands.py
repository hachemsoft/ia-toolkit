"""AI Kit 2 commands and helpers kept out of cli.py (size): migrate_config (update --migrate-config), user_edit (user edit),
the source of each installed resource, whether a Core is synced or configured."""
import os
import shlex
import subprocess
import sys

from .config import load_managed
from .core import USER_CONTEXT, KitError, read_json
from .toml_files import parse_toml, read_toml


def core_synced(kit, extra_writes):
    """True when the content's base is a synced Core (the lock being written, or the one on disk), not the package's."""
    data = (extra_writes or {}).get(kit/'lock.toml')
    lock = parse_toml(data.decode('utf-8')) if data is not None else read_toml(kit/'lock.toml', {})
    return bool(lock.get('sources', {}).get('core'))


def resource_sources(selected, catalog, agents, agent_catalog, synced=False):
    """Where each installed skill and agent comes from (V2 slice 6): team:<name>, core (a synced Core) or package. doctor and
    status read it; a Team resource is the Team's to fix, a Core one the Core's."""
    base = 'core' if synced else 'package'
    def origin(path):
        parts = path.split('/')
        return 'team:'+parts[1][len('team-'):] if len(parts) > 1 and parts[1].startswith('team-') else base
    sources = {skill: origin(catalog[skill]['path']) for skill in selected if 'path' in catalog.get(skill, {})}
    sources.update({'ai-kit-'+agent: origin(agent_catalog[agent]['path']) for agent, _ in agents if agent in agent_catalog})
    return dict(sorted(sources.items()))


def user_edit(home, at_terminal):
    """ai-kit user edit (V2 slice 7): the person's context file in their own editor ($VISUAL, $EDITOR, else the system's text
    editor); off a terminal, only its path. The kit writes nothing: the editor does."""
    state = read_json(home/'.ai-kit/state.json')
    if not state:
        raise KitError('Kit not installed: run ai-kit init.')
    path = home/state.get('context_dir', '.ai-kit/context')/USER_CONTEXT
    if not path.is_file():
        raise KitError(str(path)+' does not exist yet: run /me in your CLI, or ai-kit init to create it.')
    if not at_terminal:
        print(str(path))
        return 0
    editor = os.environ.get('VISUAL') or os.environ.get('EDITOR')
    command = (shlex.split(editor) if editor else ['notepad'] if os.name == 'nt' else ['open', '-t'] if sys.platform == 'darwin' else ['xdg-open'])
    print('Opening '+str(path)+' with '+command[0]+'. Start a new CLI session afterwards to load it.')
    return subprocess.run(command+[str(path)]).returncode


def sync_configured(home):
    """init runs a first sync when a Core source is set (managed.toml enterprise.core or aikit.toml [core] repo)."""
    from .sync import git_settings
    return bool(git_settings(home, load_managed(None))[1])
