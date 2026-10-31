"""Builds the release ZIP, dist/ai-kit-<version>.zip: the launchers, the kit's wheel and the wheels of its dependencies.
Installing from it needs no package index and no download: the launcher runs pip with --no-index on its wheels/ folder.

Usage: python3 scripts/build_release.py [--worktree] [--out DIR]
  default     the committed files (git archive HEAD): what gets published
  --worktree  the files as they are now, tracked or new but not ignored: to test a change before committing it; never publish it

Steps: a staging copy, the kit's wheel (pip wheel: the build backend comes from the package index pip is configured for),
the dependency wheels pinned in packaging/runtime.txt (pure Python only, so one ZIP serves Mac, Windows and Linux, Python 3.9
to 3.14), a check that everything installs offline into a temporary environment, then the ZIP. No top folder inside:
extracting it gives a single folder with Installer.cmd at its root.
"""
import argparse
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
# What a person needs next to the wheels: the launchers, the version, the licence, how to start, and the documentation.
SHIPPED = ('Installer.cmd', 'scripts/bootstrap.sh', 'scripts/bootstrap.ps1', 'scripts/launcher.py', 'VERSION', 'README.md', 'CHANGELOG.md', 'LICENSE', 'docs')

INSTALL_TXT = """AI Kit {version}

Install or update
  Windows: double-click Installer.cmd (or, in a Command Prompt opened in this folder: Installer.cmd).
  Mac and Linux: in Terminal, from this folder: sh scripts/bootstrap.sh

What happens
  The installer needs Python 3.9 or newer with its standard venv and pip modules. It creates the kit's private Python
  environment in your home folder (.ai-kit/runtime), installs the kit from the wheels/ folder of this ZIP (no download,
  no administrator rights, no change to your Python, PATH or shell), then asks your choices and configures your CLI.
  Once installed, this folder can be deleted: nothing points back to it. A new version comes as a new ZIP: run its installer.

Other actions (same command, followed by)
  update      reapply the configuration (after editing your choices)
  doctor      local checks, no call to the model
  uninstall   remove what the kit installed (--dry-run first shows what would go)

Documentation: README.md and docs/.
"""


def run(cmd, **kwargs):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **kwargs)
    if proc.returncode != 0:
        raise SystemExit('Failed: '+' '.join(map(str, cmd))+'\n'+(proc.stderr or proc.stdout)[-3000:])
    return proc.stdout


def stage(dest, worktree):
    """The repository's files in dest: committed ones (HEAD), or the current ones with --worktree."""
    if worktree:
        names = run(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).split('\0')
        for name in filter(None, names):
            source = ROOT/name
            if source.is_file():
                (dest/name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest/name)
        return
    data = subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar', 'HEAD'], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(dest)


def environment_python(folder):
    return folder/('Scripts' if os.name == 'nt' else 'bin')/('python.exe' if os.name == 'nt' else 'python')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the release ZIP.')
    parser.add_argument('--worktree', action='store_true', help='build from the current files (test only, never publish)')
    parser.add_argument('--out', type=Path, default=ROOT/'dist')
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='ai-kit-release-') as tmp:
        tmp = Path(tmp)
        source, wheels, payload = tmp/'source', tmp/'payload'/'wheels', tmp/'payload'
        source.mkdir()
        wheels.mkdir(parents=True)
        stage(source, args.worktree)
        version = (source/'VERSION').read_text(encoding='utf-8').strip()
        print('Kit '+version+(' (current files, test build)' if args.worktree else ' (committed files)'))
        run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--quiet', '--wheel-dir', str(wheels), str(source)])
        run([sys.executable, '-m', 'pip', 'download', '--quiet', '--no-deps', '--only-binary=:all:', '--python-version', '3.9',
             '--dest', str(wheels), '--requirement', str(source/'packaging'/'runtime.txt')])
        names = sorted(p.name for p in wheels.glob('*.whl'))
        not_universal = [n for n in names if not n.endswith(('-py3-none-any.whl', '-py2.py3-none-any.whl'))]
        if not_universal:
            raise SystemExit('Wheels tied to a platform, the ZIP would not serve every system: '+', '.join(not_universal))
        # The check a workstation will do: everything installs from wheels/ alone, no index.
        check = tmp/'check'
        venv.EnvBuilder(with_pip=True).create(str(check))
        run([str(environment_python(check)), '-I', '-m', 'pip', 'install', '--quiet', '--no-index', '--find-links', str(wheels), 'ai-kit=='+version],
            env={**os.environ, 'PIP_USER': '0'})
        run([str(environment_python(check)), '-I', '-c', 'import ai_kit.cli, rich, questionary; from ai_kit.core import ROOT; assert (ROOT/"skills"/"catalog.json").is_file()'])
        for rel in SHIPPED:
            src = source/rel
            if src.is_dir():
                shutil.copytree(src, payload/rel)
            elif src.is_file():
                (payload/rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, payload/rel)
            else:
                raise SystemExit('Missing from the repository: '+rel)
        (payload/'INSTALL.txt').write_text(INSTALL_TXT.format(version=version), encoding='utf-8')
        args.out.mkdir(parents=True, exist_ok=True)
        out = args.out/('ai-kit-'+version+('-worktree' if args.worktree else '')+'.zip')
        out.unlink(missing_ok=True)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(payload.rglob('*')):
                if path.is_file():
                    info = zipfile.ZipInfo.from_file(path, path.relative_to(payload).as_posix())
                    if path.name in ('bootstrap.sh', 'launcher.py'):
                        info.external_attr = 0o755 << 16
                    archive.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
        print('Wheels: '+', '.join(names))
        print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
