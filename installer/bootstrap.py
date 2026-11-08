"""Where the content comes from when the installed package holds only the engine (2.2: the content left the package, the
release ZIP ships the Core as a git bundle). For one command run:

1. the engine's own folder has the content (a clone of the kit, python3 -m installer): it is used, as before;
2. a Core is locked (lock.toml): its version, extracted from the local cache, no network;
3. the folder the launcher runs from holds core/ai-kit-core.bundle (the release ZIP): a first installation activates that
   Core offline, recorded under the Core URL (IT's enterprise.core, the person's [core] repo, else this kit's repository);
4. that folder holds the content itself (a copy of a clone): it is used, as before;
5. otherwise nothing can be installed, and the message says what to run."""
import contextlib
import os
from pathlib import Path

from .core import ROOT, KitError, content_from
from .toml_files import read_toml

DEFAULT_CORE_URL = 'https://github.com/hachemsoft/ia-toolkit.git'  # this repository is the Core (its tags are its versions)
BUNDLE = 'core/ai-kit-core.bundle'


def has_content(folder):
    folder = Path(folder)
    return (folder/'skills').is_dir() and (folder/'commands').is_dir() and (folder/'profiles').is_dir()


def source_dir():
    folder = os.environ.get('AI_KIT_SOURCE_DIR')
    return Path(folder) if folder else None


def shipped_bundle():
    folder = source_dir()
    return folder/BUNDLE if folder and (folder/BUNDLE).is_file() else None


@contextlib.contextmanager
def run_content(home, managed_file=None):
    """The content for this run; yields the shipped bundle when a first installation must activate it, else None."""
    if has_content(ROOT):
        yield None
        return
    kit = Path(home)/'.ai-kit'
    if read_toml(kit/'lock.toml', {}).get('sources'):
        from .sync import activation
        with activation(Path(home), 'update', dry_run=True, managed_file=managed_file):
            yield None
        return
    bundle = shipped_bundle()
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
                   'or sh scripts/bootstrap.sh), or ai-kit sync --from-bundle <core bundle>.')
