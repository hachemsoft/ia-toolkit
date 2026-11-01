"""Versions of the skills and agents: checks them, or records them in versions.lock.json.

Usage: python3 scripts/versions.py            checks: every component has a version, none changed under the same version
       python3 scripts/versions.py --update   records the current versions and digests (refused while a check fails)
A test runs the check, so a skill or an agent changed without a new version fails the build.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.core import KitError  # noqa: E402
from installer import versions  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--update' in argv:
        try:
            versions.write_lock()
        except KitError as exc:
            print(exc, file=sys.stderr)
            return 1
        print('versions.lock.json written.')
        return 0
    found = versions.problems() + ['not recorded yet: ' + s + ' (python3 scripts/versions.py --update)' for s in versions.stale()]
    for line in found:
        print(line)
    print('Versions: ' + ('to fix.' if found else 'all recorded.'))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
