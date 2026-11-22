"""Where the content comes from when the installed package holds only the engine (2.2: the content left the package, the
release ZIP ships the Core as a git bundle). For one command run:

1. the engine's own folder has the content (a clone of the kit, python3 -m installer): it is used, as before;
2. a Core is locked (lock.toml): its version, extracted from the local cache, no network; when the launcher's folder
   ships a Core bundle (a release ZIP), it is handed over too, so that the installer of a newer ZIP moves the locked Core;
3. the folder the launcher runs from holds core/ai-kit-core.bundle (the release ZIP): a first installation activates that
   Core offline, recorded under the Core URL (IT's enterprise.core, the person's [core] repo, else this kit's repository);
4. that folder holds the content itself (a copy of a clone): it is used, as before;
5. otherwise nothing can be installed, and the message says what to run.

The commands that never read the content (needs_content) skip all of this: they run without a Core, or with one that can
no longer be read (cache removed, commit revoked), which is when they are needed."""
import contextlib
import os
from pathlib import Path

from .core import ROOT, KitError, content_from
from .toml_files import read_toml

DEFAULT_CORE_URL = 'https://github.com/hachemsoft/ia-toolkit.git'  # this repository is the Core (its tags are its versions)
BUNDLE = 'core/ai-kit-core.bundle'


def has_content(folder):
    folder = Path(folder)
    return (folder/'skills').is_dir() and (folder/'commands').is_dir()


def source_dir():
    folder = os.environ.get('AI_KIT_SOURCE_DIR')
    return Path(folder) if folder else None


def shipped_bundle():
    folder = source_dir()
    return folder/BUNDLE if folder and (folder/BUNDLE).is_file() else None


def needs_content(args):
    """False for the commands that read no content of their own run: the engine's version; uninstall (the state and the
    files on disk); rollback and sync --from-bundle (the activation extracts the content it applies); validate --path and
    news --add (the repository they are given). They must run when the locked Core cannot be read: they are the way out."""
    if args.version or args.action in ('uninstall', 'rollback', 'news'):
        return False
    if args.action == 'sync' and args.from_bundle:
        return False
    return not (args.action == 'validate' and args.path)


@contextlib.contextmanager
def run_content(home, managed_file=None, installing=False):
    """The content for this run; yields the Core bundle the launcher's folder ships, for the installation to activate when
    it is the first one or when the locked Core is older (the caller decides), else None. installing: the run is an
    installation (init), which may go on with the shipped Core when the locked one cannot be read."""
    if has_content(ROOT):
        yield None
        return
    kit = Path(home)/'.ai-kit'
    bundle = shipped_bundle()
    if read_toml(kit/'lock.toml', {}).get('sources'):
        from .sources import SourceError
        from .sync import activation
        with contextlib.ExitStack() as locked:
            try:
                locked.enter_context(activation(Path(home), 'update', dry_run=True, managed_file=managed_file))
            except SourceError as exc:
                # The locked Core cannot be read (cache removed, digest changed, commit revoked). The installer of a release
                # ZIP goes on with the Core it ships: a newer one is activated, the same one fills the cache again; the
                # installation itself still checks the locked Core (a revoked commit stays refused). Any other command
                # stops here with the reason: status and doctor never describe a Core that is not the locked one.
                if not (installing and bundle) or exc.kind not in ('not-found', 'invalid', 'revoked'):
                    raise
            else:
                yield bundle
                return
    if bundle:
        from .sync import shipped_core
        with shipped_core(Path(home), bundle) as folder, content_from(folder):
            yield bundle
        return
    folder = source_dir()
    if folder and has_content(folder):
        with content_from(folder):
            yield None
        return
    raise KitError('This AI Kit holds no content and no Core is installed: run the installer of the kit folder (Installer.cmd, '
                   'or sh scripts/bootstrap.sh).')
