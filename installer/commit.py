"""Writing a plan to disk: backup, atomic writes, rollback on any error, and backup retention."""
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

from .core import (json_bytes)
from .adapters import ADAPTERS


BACKUPS_KEPT = 20


def prune_backups(kit, keep=BACKUPS_KEPT):
    """Only the most recent backups stay: they hold copies of settings files, which may carry the person's own secrets."""
    folder = kit/'backups'
    if not folder.is_dir():
        return
    dated = sorted((p for p in folder.iterdir() if p.is_dir() and re.match(r'\d{8}T\d{6}-', p.name)), key=lambda p: p.name)
    for old in dated[:-keep] if keep else dated:
        shutil.rmtree(old, ignore_errors=True)


def commit_changes(home, kit, writes, deletes, progress=None):
    """Backs up every file about to change, then writes and removes them; on any error or interruption, puts everything
    back. Returns (changed paths, backup folder)."""
    changed = list(writes)+deletes
    backup = kit/'backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    originals = {}
    for path in changed:
        originals[path] = path.read_bytes() if path.exists() else None
    step = progress or (lambda *_: None)
    if not changed:
        return changed, backup
    backup.mkdir(parents=True,exist_ok=True)
    try:
        if os.name != 'nt':
            backup.chmod(0o700)
        existing = sum(1 for data in originals.values() if data is not None)
        done = 0
        for path, data in originals.items():
            if data is not None:
                done += 1
                step('backup', done, existing)
                dest = backup/path.relative_to(home)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(data)
                if os.name != 'nt':
                    dest.chmod(0o600)
        (backup/'manifest.json').write_bytes(json_bytes({'created':[p.relative_to(home).as_posix() for p,b in originals.items() if b is None],'restore':'Copy the backed-up files to the home folder; remove the created files only if unchanged.'}))
        if os.name != 'nt':
            (backup/'manifest.json').chmod(0o600)
        for done, (path, data) in enumerate(writes.items(), 1):
            step('write', done, len(writes))
            atomic_write(path,data)
        for done, path in enumerate(deletes, 1):
            step('remove', done, len(deletes))
            path.unlink()
            prune_empty_dirs(path.parent, next((home/d for d in managed_roots(home) if path.is_relative_to(home/d)), home/'.ai-kit'))
    except BaseException:
        # A write error, Ctrl+C or a closed terminal during the writes: everything goes back as it was.
        for path,data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path,data)
        raise
    prune_backups(kit)
    return changed, backup


KIT_MANAGED = ('.ai-kit/bin/', '.ai-kit/hooks/', '.ai-kit/context/', '.ai-kit/schemas/')


def managed_roots(home):
    """Root folders where the kit puts files: its own and each CLI's."""
    return ['.ai-kit'] + sorted({a.HOME_DIR for a in ADAPTERS})


def prune_empty_dirs(directory, stop):
    """Remove empty folders left by a deletion, never a root folder or its structural folders."""
    roots = {stop} | {stop/name for name in ('skills', 'agents', 'commands', 'hooks', 'bin', 'config', 'config/plugins')}
    while directory not in roots and directory.is_relative_to(stop) and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix='.ai-kit-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
