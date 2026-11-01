"""The `ai-kit` command in the person's terminal: a small script in ~/.ai-kit/bin that runs the launcher of the kit
folder with the same arguments (so `ai-kit update` is the launcher's update: fetch, reinstall, apply), and that folder
on the person's own PATH: the user `Path` of the registry on Windows, a marked block in the login shell's startup file
on Mac and Linux. Chosen at setup (yes by default), kept by update, removed by uninstall. Only the launcher knows the
kit folder: run otherwise, the kit writes no command and keeps an existing one as it is."""
import os
import sys
from pathlib import Path

SHIM_NAME = 'ai-kit.cmd' if os.name == 'nt' else 'ai-kit'
BLOCK_START = '# >>> AI Kit command (managed by the kit: removed by uninstall) >>>'
BLOCK_END = '# <<< AI Kit command <<<'
REGISTRY_ENTRY = r'%USERPROFILE%\.ai-kit\bin'


def shim_bytes(folder):
    """The script that runs the launcher of the kit folder. Windows: the menu opened by `ai-kit` alone must not pause."""
    folder = str(folder)
    if os.name == 'nt':
        text = ('@echo off\r\n'
                'rem AI Kit command, installed by the kit: runs the launcher of the kit folder. Removed by uninstall.\r\n'
                'set "AI_KIT_NO_PAUSE=1"\r\n'
                'call "'+folder+'\\Installer.cmd" %*\r\n'
                'exit /b %ERRORLEVEL%\r\n')
    else:
        quoted = "'"+folder.replace("'", "'\\''")+"/scripts/bootstrap.sh'"
        text = ('#!/bin/sh\n'
                '# AI Kit command, installed by the kit: runs the launcher of the kit folder. Removed by uninstall.\n'
                'exec sh '+quoted+' "$@"\n')
    return text.encode('utf-8')


def shim_folder(data):
    """The kit folder a shim points to, or None."""
    text = data.decode('utf-8', 'replace')
    for line in text.splitlines():
        if line.startswith('call "') and line.endswith('\\Installer.cmd" %*'):
            return line[len('call "'):-len('\\Installer.cmd" %*')]
        if line.startswith("exec sh '") and line.endswith("/scripts/bootstrap.sh' \"$@\""):
            return line[len("exec sh '"):-len("/scripts/bootstrap.sh' \"$@\"")].replace("'\\''", "'")
    return None


def startup_file(shell=None):
    """The login shell's startup file (relative to the home folder), or None for a shell the kit does not know."""
    name = os.path.basename(shell if shell is not None else os.environ.get('SHELL', ''))
    if name == 'zsh':
        return '.zshrc'
    if name == 'bash':
        return '.bash_profile' if sys.platform == 'darwin' else '.bashrc'
    if name in ('sh', 'dash', 'ksh'):
        return '.profile'
    return None


def path_line(home):
    quoted = "'"+str(home/'.ai-kit'/'bin').replace("'", "'\\''")+"'"
    return 'export PATH='+quoted+':"$PATH"'


def with_block(text, line):
    """The startup file with the kit's block, once: an existing block is rewritten in place."""
    block = BLOCK_START+'\n'+line+'\n'+BLOCK_END+'\n'
    if BLOCK_START in text and BLOCK_END in text:
        return _replace_block(text, block)
    if not text:
        return block
    return text.rstrip('\n')+'\n\n'+block


def _replace_block(text, block):
    start, end = text.index(BLOCK_START), text.index(BLOCK_END)+len(BLOCK_END)
    tail = text[end:]
    return text[:start]+block+tail.lstrip('\n')


def without_block(text):
    """The startup file without the kit's block, the rest untouched."""
    if BLOCK_START not in text or BLOCK_END not in text:
        return text
    start, end = text.index(BLOCK_START), text.index(BLOCK_END)+len(BLOCK_END)
    head = text[:start].rstrip('\n')
    tail = text[end:].lstrip('\n')
    if not head:
        return tail
    return head+'\n'+('\n'+tail if tail else '')


def registry_entry(add, reg=None):
    """Adds or removes the kit's folder in the user PATH (HKCU\\Environment\\Path, never the machine PATH), keeping the
    other entries and the expandable kind. Returns True when the value changed. reg: winreg, or a stand-in for tests."""
    if reg is None:
        import winreg as reg  # Windows only
    with reg.OpenKey(reg.HKEY_CURRENT_USER, 'Environment', 0, reg.KEY_READ | reg.KEY_SET_VALUE) as key:
        try:
            value, kind = reg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            value, kind = '', reg.REG_EXPAND_SZ
        parts = [part for part in str(value).split(';') if part]
        def ours(part):
            return part.strip().strip('"').rstrip('\\').lower() == REGISTRY_ENTRY.lower()
        present = any(ours(part) for part in parts)
        if add == present:
            return False
        parts = parts+[REGISTRY_ENTRY] if add else [part for part in parts if not ours(part)]
        reg.SetValueEx(key, 'Path', 0, reg.REG_EXPAND_SZ if add or kind == reg.REG_EXPAND_SZ else kind, ';'.join(parts))
    return True


def announce_environment_change():
    """Tells the Windows shell the environment changed, so a new console sees the PATH (best effort)."""
    try:
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 5000, None)
    except Exception:  # noqa: BLE001 — a missing user32 or a timeout changes nothing for the files written
        pass


def real_home(home):
    """True when the kit runs in the person's own home folder: a --home trial never touches the registry."""
    try:
        return Path(home).resolve() == Path.home().resolve()
    except OSError:
        return False
