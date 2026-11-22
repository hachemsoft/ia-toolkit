"""Writing a plan to disk: backup, atomic writes, rollback on any error, and backup retention."""
import contextlib
import json
import os
import re
import shutil
import signal
import stat
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone

from .core import inside, json_bytes
from .adapters import ADAPTERS


BACKUPS_KEPT = 20
BACKUP_STAMP = '%Y%m%dT%H%M%S%f'  # to the microsecond: the folders sort by name in the order they were made
DATED_BACKUP = re.compile(r'\d{8}T\d{6,}-')


class Stopped(KeyboardInterrupt):
    """SIGTERM or SIGHUP received during the writes: handled like Ctrl+C, every file is put back."""


def trap_stops():
    """While the files are written, SIGTERM (a killed process) and SIGHUP (a closed terminal) raise Stopped, so the writes are
    undone like on Ctrl+C. SIGKILL and a power cut cannot be caught: the pending manifest is resumed at the next start
    (resume_pending). Returns the previous handlers, for release_stops."""
    if threading.current_thread() is not threading.main_thread():
        return {}
    def stop(signum, frame):
        raise Stopped('signal '+str(signum))
    previous = {}
    for name in ('SIGTERM', 'SIGHUP'):
        number = getattr(signal, name, None)
        if number is not None:
            try:
                previous[number] = signal.signal(number, stop)
            except (OSError, ValueError):
                pass
    return previous


def release_stops(previous):
    for number, handler in previous.items():
        if handler is not None:  # None: a handler not installed from Python, which signal.signal() cannot put back
            signal.signal(number, handler)


@contextlib.contextmanager
def ignored_stops():
    """While the files are put back, Ctrl+C, SIGTERM and SIGHUP are ignored: a restoration stopped half-way would leave a
    mix of old and new files. SIGKILL and a power cut remain: the manifest stays pending and the next start resumes it."""
    previous = {}
    if threading.current_thread() is threading.main_thread():
        for name in ('SIGINT', 'SIGTERM', 'SIGHUP', 'SIGBREAK'):
            number = getattr(signal, name, None)
            if number is not None:
                try:
                    previous[number] = signal.signal(number, signal.SIG_IGN)
                except (OSError, ValueError):
                    pass
    try:
        yield
    finally:
        release_stops(previous)


def file_mode(path):
    """The POSIX permission bits of an existing file, else None (Windows, or no file)."""
    if os.name == 'nt':
        return None
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return None


def backup_folder(kit):
    """A new backup folder name, after every existing one: two runs within the clock's resolution, or a clock set back,
    still sort in the order they were made (resume_pending reads the last one)."""
    folder = kit/'backups'
    stamp = datetime.now(timezone.utc).strftime(BACKUP_STAMP)
    latest = max((p.name.split('-')[0] for p in folder.iterdir() if p.is_dir() and DATED_BACKUP.match(p.name)), default='') if folder.is_dir() else ''
    if stamp <= latest and len(latest) == len(stamp):
        stamp = (datetime.strptime(latest, BACKUP_STAMP)+timedelta(microseconds=1)).strftime(BACKUP_STAMP)
    return folder/(stamp+'-'+uuid.uuid4().hex[:8])


def prune_backups(kit, keep=BACKUPS_KEPT):
    """Only the most recent backups stay: they hold copies of settings files, which may carry the person's own secrets."""
    folder = kit/'backups'
    if not folder.is_dir():
        return
    dated = sorted((p for p in folder.iterdir() if p.is_dir() and DATED_BACKUP.match(p.name)), key=lambda p: p.name)
    for old in dated[:-keep] if keep else dated:
        shutil.rmtree(old, ignore_errors=True)


def commit_changes(home, kit, writes, deletes, progress=None):
    """Backs up every file about to change, then writes and removes them; on any error or interruption, puts everything
    back. Returns (changed paths, backup folder)."""
    changed = list(writes)+deletes
    backup = backup_folder(kit)
    originals, modes = {}, {}
    for path in changed:
        originals[path] = path.read_bytes() if path.exists() else None
        modes[path] = file_mode(path)
    step = progress or (lambda *_: None)
    if not changed:
        return changed, backup
    backup.mkdir(parents=True,exist_ok=True)
    previous = trap_stops()
    manifest_path, manifest = backup/'manifest.json', None
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
        # modes: the backup copies are private (0600); the permission bits to give back are recorded here.
        pending = {'status':'pending','created':[p.relative_to(home).as_posix() for p,b in originals.items() if b is None],
                   'modes':{p.relative_to(home).as_posix(): mode for p, mode in modes.items() if mode is not None},
                   'restore':'Copy the backed-up files to the home folder; remove the created files only if unchanged.'}
        atomic_write(manifest_path, json_bytes(pending), 0o600)
        manifest = pending
        for done, (path, data) in enumerate(writes.items(), 1):
            step('write', done, len(writes))
            atomic_write(path,data)
        for done, path in enumerate(deletes, 1):
            step('remove', done, len(deletes))
            path.unlink()
            prune_empty_dirs(path.parent, next((home/d for d in managed_roots(home) if path.is_relative_to(home/d)), home/'.ai-kit'))
    except BaseException:
        # A write error, Ctrl+C or a closed terminal during the writes: everything goes back as it was, without being
        # stopped half-way. Then the manifest says so: left pending, the next start would put these copies back again, over
        # what the person changed since. An error during the restoration itself leaves it pending, for that next start.
        with ignored_stops():
            for path,data in originals.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, data, modes[path])
            if manifest is not None:
                atomic_write(manifest_path, json_bytes({**manifest, 'status': 'restored'}), 0o600)
        raise
    finally:
        release_stops(previous)
    # Done once every write landed; a pending manifest at the next start means a machine stop during the writes.
    atomic_write(manifest_path, json_bytes({**manifest, 'status': 'done'}), 0o600)
    prune_backups(kit)
    return changed, backup


def resume_pending(home, kit):
    """An activation stopped by a power cut or a killed process left its backup manifest pending: put back the files it had
    backed up and remove those it had created, so that the previous configuration (and lock.toml) is whole again."""
    folder = kit/'backups'
    if not folder.is_dir():
        return None
    # Only the folders the kit names (backup_folder), never a link: another folder in backups/ is not a backup of the kit.
    dated = (p for p in folder.iterdir() if p.is_dir() and not p.is_symlink() and DATED_BACKUP.match(p.name))
    for backup in sorted(dated, key=lambda p: p.name, reverse=True)[:1]:
        manifest_path = backup/'manifest.json'
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if not isinstance(manifest, dict) or manifest.get('status') != 'pending':
            return None
        modes = manifest.get('modes') if isinstance(manifest.get('modes'), dict) else {}
        created = manifest.get('created') if isinstance(manifest.get('created'), list) else []
        # Every path is checked before the first write: inside the home folder, through no link (a manifest is a file a
        # process could have written; what it names is never followed outside).
        from .plan import refuse_links
        saved_files = [saved for saved in sorted(backup.rglob('*')) if saved.is_file() and not saved.is_symlink() and saved != manifest_path]
        restore = [(saved, inside(home, saved.relative_to(backup))) for saved in saved_files]
        remove = [inside(home, str(rel)) for rel in created]
        refuse_links(home, [target for _, target in restore] + remove)
        for saved, target in restore:
            mode = modes.get(saved.relative_to(backup).as_posix())
            atomic_write(target, saved.read_bytes(), mode if isinstance(mode, int) else None)
        for target in remove:
            target.unlink(missing_ok=True)
        atomic_write(manifest_path, json_bytes({**manifest, 'status': 'restored'}), 0o600)
        return backup
    return None


KIT_MANAGED = ('.ai-kit/bin/', '.ai-kit/hooks/', '.ai-kit/context/', '.ai-kit/schemas/', '.ai-kit/news/', '.ai-kit/me/')


def managed_roots(home):
    """Root folders where the kit puts files: its own and each CLI's."""
    return ['.ai-kit'] + sorted({a.HOME_DIR for a in ADAPTERS})


def prune_empty_dirs(directory, stop):
    """Remove empty folders left by a deletion, never a root folder or its structural folders."""
    roots = {stop} | {stop/name for name in ('skills', 'agents', 'commands', 'hooks', 'bin', 'config', 'config/plugins')}
    while directory not in roots and directory.is_relative_to(stop) and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def atomic_write(path, data, mode=None):
    """Writes through a temporary file of the same folder. POSIX: the file keeps the permission bits it had (the execute
    bit of the ai-kit command, the mode of a shell startup file), or takes `mode`; a new file is private (0600)."""
    path.parent.mkdir(parents=True,exist_ok=True)
    if mode is None:
        mode = file_mode(path)
    fd,tmp = tempfile.mkstemp(prefix='.ai-kit-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data)
        if mode is not None and os.name != 'nt':
            os.chmod(tmp, mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
