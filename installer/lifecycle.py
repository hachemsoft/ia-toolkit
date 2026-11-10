"""The `ai-kit` command on the person's PATH (shim, shell startup block, Windows registry) and uninstall. Split from cli.py,
unchanged; cli.py re-exports these names."""
import os
from types import SimpleNamespace

from .core import USER_CONTEXT, KitError, read_json, digest, inside, check_state_schema
from .adapters import ADAPTERS
from . import command as kit_command
from .commit import commit_changes, KIT_MANAGED
from .doctor import source_folder


PERSONAL_KEPT = ('.ai-kit/aikit.toml', '.ai-kit/lock.toml', '.ai-kit/sources/', '.ai-kit/backups/', '.ai-kit/frictions.jsonl', '.ai-kit/learning/', '.ai-kit/runtime/')


def _nothing():
    pass


def _registry_add():
    if kit_command.registry_entry(True):
        kit_command.announce_environment_change()


def _registry_remove():
    kit_command.registry_entry(False)
    kit_command.announce_environment_change()


def plan_command(p, managed_write, choice):
    """The `ai-kit` command of installer/command.py in the plan: the shim as a managed file, the startup block as an
    untracked write. Returns (state entry, function to call once the files are written: registry, execute bit)."""
    kit, home, state = p.kit, p.home, p.state
    previous = state.get('command') or {}
    chosen = choice if choice is not None else previous.get('chosen', True)
    folder = source_folder()
    shim = kit/'bin'/kit_command.SHIM_NAME
    rel = shim.relative_to(home).as_posix()
    entry = {'chosen': chosen, 'folder': None, 'startup_file': None, 'registry': False}
    after = _nothing
    if not chosen:
        if previous.get('startup_file') and (home/previous['startup_file']).is_file():
            text = (home/previous['startup_file']).read_text(encoding='utf-8')
            if kit_command.BLOCK_START in text:
                p.writes[home/previous['startup_file']] = kit_command.without_block(text).encode('utf-8')
        if previous.get('registry') and os.name == 'nt' and kit_command.real_home(home):
            after = _registry_remove
        return entry, after
    if folder is None:
        # Run without the launcher (a developer's pip install .): nothing to point to; an existing command stays as it is.
        if rel in p.old_files and shim.is_file():
            managed_write(shim, shim.read_bytes(), 'Kit command')
            entry.update({'folder': previous.get('folder') or kit_command.shim_folder(shim.read_bytes()), 'startup_file': previous.get('startup_file'), 'registry': previous.get('registry', False)})
        else:
            p.notices.append('[Info] The `ai-kit` command is not installed: run the installer from the kit folder (Installer.cmd, or sh scripts/bootstrap.sh) to add it.')
        return entry, after
    data = kit_command.shim_bytes(folder)
    new = not shim.is_file() or shim.read_bytes() != data
    managed_write(shim, data, 'Kit command')
    entry['folder'] = str(folder)
    if os.name == 'nt':
        entry['registry'] = kit_command.real_home(home)
        if entry['registry']:
            after = _registry_add
        else:
            p.notices.append('[Info] `ai-kit` command written for this trial home folder only: the user PATH is not changed.')
    else:
        def after(shim=shim):
            if shim.is_file():
                shim.chmod(0o755)  # the execute bit, once the file is written
        name = kit_command.startup_file()
        line = kit_command.path_line(home)
        if name:
            path = home/name
            text = path.read_text(encoding='utf-8') if path.is_file() else ''
            wanted = kit_command.with_block(text, line)
            if wanted != text:
                p.writes[path] = wanted.encode('utf-8')
                new = True
            entry['startup_file'] = name
        else:
            p.notices.append('[Info] Shell not recognised: add this line to your shell startup file to use the `ai-kit` command: '+line)
    if new:
        p.notices.append('[Info] `ai-kit` command installed: open a new terminal to use it (ai-kit status, ai-kit doctor).')
    return entry, after


def remove_command(home, state, writes):
    """uninstall: the startup block goes (the shim is a managed file, removed with the others)."""
    previous = state.get('command') or {}
    if previous.get('startup_file') and (home/previous['startup_file']).is_file():
        text = (home/previous['startup_file']).read_text(encoding='utf-8')
        if kit_command.BLOCK_START in text:
            writes[home/previous['startup_file']] = kit_command.without_block(text).encode('utf-8')


def uninstall(home, dry_run=False, confirm=None, progress=None, report=None):
    """Removes what the kit installed and nothing else: the managed files it can recognise as unchanged, its blocks and
    entries in the CLIs' settings, and its state. Kept: the personal context (USER.md), aikit.toml, the backups,
    frictions, the CLIs' folders and the person's own settings; a managed file modified by hand is kept and named.
    No network, no model. confirm(report) -> bool is asked before any change (interactive); returns an exit code."""
    home = home.resolve()
    kit = home/'.ai-kit'
    state = read_json(kit/'state.json')
    if not state:
        raise KitError('The kit configuration is not installed in '+str(home)+': nothing to remove.')
    check_state_schema(state, kit/'state.json')
    old_files = state.get('files', {})
    writes, deletes, kept = {}, [], []
    for rel, expected in sorted(old_files.items()):
        if not (rel.startswith(KIT_MANAGED) or any(a.is_managed(rel) for a in ADAPTERS)):
            raise KitError('Invalid state: deletion outside the managed scope ('+rel+').')
        path = inside(home, rel)
        if not path.is_file():
            continue
        if digest(path.read_bytes()) != expected:
            kept.append(rel+': modified since the kit installed it, kept; remove it yourself if you no longer need it')
            continue
        deletes.append(path)
    cleanup = SimpleNamespace(home=home, state=state, old_files=old_files, writes=writes, deletes=deletes, blocks={}, notices=[], active=[])
    for adapter in ADAPTERS:
        try:
            adapter.finalize(cleanup, active=False)
        except KitError as exc:
            kept.append(adapter.LABEL+': '+str(exc))
    deletes.append(kit/'state.json')
    remove_command(home, state, writes)
    writes = {path: data for path, data in writes.items() if not path.exists() or path.read_bytes() != data}
    personal = [str(home/'.ai-kit/context'/USER_CONTEXT)] + [str(home/rel) for rel in PERSONAL_KEPT if (home/rel).exists()]
    def rel(path):
        return path.relative_to(home).as_posix()
    summary = {'removed': [rel(d) for d in deletes], 'rewritten': sorted(rel(w) for w in writes), 'kept_modified': kept,
               'personal': personal, 'home': str(home)}
    if report is not None:
        report.update(summary)
    print('Uninstall from '+str(home)+': '+str(len(deletes))+' kit files to remove, '+str(len(writes))+' settings files to clean.')
    for line in summary['rewritten']:
        print('  Clean the kit entries in: '+line)
    for line in kept:
        print('[Check] '+line)
    print('Kept: your personal context, aikit.toml, backups and frictions, the CLIs and their own settings.')
    if dry_run:
        print('Dry run: nothing changed.')
        return 0
    if confirm is not None and not confirm(summary):
        print('Uninstall cancelled: nothing changed.')
        return 1
    changed, backup = commit_changes(home, kit, writes, deletes, progress)
    if (state.get('command') or {}).get('registry') and os.name == 'nt' and kit_command.real_home(home):
        kit_command.registry_entry(False)
        kit_command.announce_environment_change()
    print('Kit configuration removed. Backup of every removed or cleaned file: '+str(backup))
    print('Your files kept: '+', '.join(personal))
    print('The kit\'s private Python environment ('+str(kit/'runtime')+') stays; the launcher removes it with uninstall --remove-runtime.')
    return 0
