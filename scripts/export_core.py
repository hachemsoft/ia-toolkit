"""The kit's content as a Core repository in its V2 layout (V2 slice 8, docs/v2/resources.md): skills/<name>/ and agents/<name>.md
flattened from their category folders, the commands, practices, profiles, templates and organization.toml, and the manifest
aikit.toml with kind = "core". The engine reads both layouts; this one is what a Core repository holds.

Usage: python3 scripts/export_core.py <empty folder> [--git]
  --git  also makes it a Git repository with one commit and the tag v<VERSION>, ready to be pushed where the organization
         decides (nothing is pushed, no remote is created). `ai-kit validate --path <folder>` checks the result.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.resolve import agent_catalog, skill_catalog  # noqa: E402

COPIED = ('commands', 'practices', 'profiles', 'templates', 'organization.toml')


def export(dest):
    dest = pathlib.Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(str(dest)+' is not empty: give a new folder, nothing is overwritten.')
    dest.mkdir(parents=True, exist_ok=True)
    for name in COPIED:
        source = ROOT/name
        (shutil.copytree if source.is_dir() else shutil.copy2)(source, dest/name)
    for skill, entry in skill_catalog(ROOT).items():
        if 'path' in entry:
            shutil.copytree(ROOT/entry['path'], dest/'skills'/skill)
    shutil.copy2(ROOT/'skills/LICENSE-UPSTREAM-MIT', dest/'skills/LICENSE-UPSTREAM-MIT')
    shutil.copy2(ROOT/'skills/upstream.lock.json', dest/'skills/upstream.lock.json')
    (dest/'agents').mkdir()
    shutil.copy2(ROOT/'agents/defaults.json', dest/'agents/defaults.json')
    for agent, entry in agent_catalog(ROOT).items():
        shutil.copy2(ROOT/entry['path'], dest/'agents'/(agent+'.md'))
    version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
    (dest/'aikit.toml').write_text('#:schema https://github.com/hachemsoft/ia-toolkit/blob/main/schemas/source.schema.json\n'
                                   'schema = 1\nname = "core"\nkind = "core"\nmin_engine = "2.1.0"\n', encoding='utf-8')
    (dest/'README.md').write_text('# AI Kit Core\n\nThe content AI Kit installs: skills, agents, commands, practices. Exported from the kit '
                                  + version+' by scripts/export_core.py. Check a change with `ai-kit validate --path .` before tagging '
                                  'a release vX.Y.Z; workstations install the highest stable tag with `ai-kit sync`.\n', encoding='utf-8')
    return version


def main(argv):
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        return 2
    version = export(argv[0])
    if '--git' in argv:
        env = {'GIT_CONFIG_NOSYSTEM': '1', 'PATH': __import__('os').environ.get('PATH', '')}
        for args in (['init', '-q', '-b', 'main'], ['add', '-A'], ['-c', 'user.name=AI Kit export', '-c', 'user.email=export@localhost', 'commit', '-q', '-m', 'Core '+version],
                     ['-c', 'user.name=AI Kit export', '-c', 'user.email=export@localhost', 'tag', '-a', 'v'+version, '-m', 'Core '+version]):
            subprocess.run(['git', *args], cwd=argv[0], check=True, env=env)
    print('Core exported to '+argv[0]+(' (Git repository, tag v'+version+')' if '--git' in argv else '')+'.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
