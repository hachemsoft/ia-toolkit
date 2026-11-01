#!/usr/bin/env python3
"""What the session-news hook has announced, and the refusal of a proposed update. Installed in ~/.ai-kit/bin by the kit.

Usage: python3 ~/.ai-kit/bin/news.py --later     a newer version was proposed and refused: do not propose it again
       python3 ~/.ai-kit/bin/news.py --list      installed version, last remote read, announced news, declined version
       python3 ~/.ai-kit/bin/news.py --check     read the kit's remote now (VERSION and NEWS.md on origin/main) and say
The agent runs --later when the person says no to an update (the kit context says so); the person runs the others.
`ai-kit news` runs this very file (installer/cli.py imports it): one implementation, --home for a trial home.
Writes only ~/.ai-kit/news.json; nothing is sent; the update itself is never run here (ADR 0012).
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import date

MARKER = 'news.json'


def read_json(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_marker(path, marker):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(marker, ensure_ascii=False, indent=1))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def hook_module():
    """runtime/hooks/session-news.py as a module: next to this file in the kit (runtime/hooks/), or ~/.ai-kit/hooks/ once installed."""
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, 'hooks', 'session-news.py'), os.path.join(os.path.dirname(here), 'hooks', 'session-news.py')):
        if os.path.isfile(candidate):
            spec = importlib.util.spec_from_file_location('ai_kit_session_news', candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


def later(state, marker):
    installed = str(state.get('version') or '')
    remote = str((marker.get('last_check') or {}).get('remote_version') or '')
    hook = hook_module()
    newer = bool(remote) and (hook.version_tuple(remote) > hook.version_tuple(installed) if hook else remote != installed)
    if not newer:
        return 'No newer version known: nothing to decline.', False
    marker['declined_version'] = remote
    return 'Version '+remote+' will not be proposed again. Run ai-kit update when you want it.', True


def listing(state, marker):
    last = marker.get('last_check') or {}
    lines = ['Installed: '+str(state.get('version') or 'unknown')+' (kit folder: '+str(state.get('kit_dir') or 'unknown')+')',
             'Remote read: '+(last.get('date', '')+' '+last.get('result', '')+(' '+last['detail'] if last.get('detail') else '')
                              + (' remote version '+last['remote_version'] if last.get('remote_version') else '') if last else 'never'),
             'Remote check: '+('off (news.check_remote = false)' if (state.get('news') or {}).get('check_remote') is False else 'on, once a day'),
             'Announced versions: '+(', '.join(marker.get('announced_versions') or []) or 'none'),
             'Announced news: '+(', '.join(marker.get('announced_news') or []) or 'none'),
             'Declined version: '+str(marker.get('declined_version') or 'none')]
    return '\n'.join(lines)


def check(state, marker):
    hook = hook_module()
    kit_dir = str(state.get('kit_dir') or '')
    if hook is None:
        return 'The session-news hook is not installed (hooks.session-news = false?): nothing read.', False
    if not kit_dir or not os.path.isdir(kit_dir):
        return 'Kit folder unknown or missing ('+(kit_dir or 'none')+'): run the installer from the kit folder, then update.', False
    result, detail, remote_version, _ = hook.remote_read(kit_dir)
    if result == 'skipped':
        return 'Not read: '+detail+'.', False
    marker['last_check'] = {'date': date.today().isoformat(), 'result': result, **({'detail': detail} if detail else {}), **({'remote_version': remote_version} if remote_version else {})}
    if result != 'ok':
        return 'Remote read failed: '+detail+'.', True
    installed = str(state.get('version') or '')
    if hook.version_tuple(remote_version) > hook.version_tuple(installed):
        return 'A newer kit version is available: '+remote_version+' (installed: '+installed+'). Run ai-kit update to install it.', True
    return 'Up to date: '+installed+' (remote: '+remote_version+').', True


def main(argv=None):
    parser = argparse.ArgumentParser(prog='news.py', description='What the kit announced at session start; refuse a proposed update.')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--later', action='store_true', help='do not propose the newer version again')
    action.add_argument('--list', action='store_true', help='installed version, last remote read, announced news')
    action.add_argument('--check', action='store_true', help='read the kit remote now and say whether a newer version exists')
    parser.add_argument('--home', help='home folder of the kit installation (default: yours)')
    args = parser.parse_args(argv)
    kit = os.path.join(os.path.abspath(os.path.expanduser(args.home)) if args.home else os.path.expanduser('~'), '.ai-kit')
    state = read_json(os.path.join(kit, 'state.json'))
    if not state:
        print('Kit not installed: run setup.')
        return 1
    marker_path = os.path.join(kit, MARKER)
    marker = read_json(marker_path)
    if args.list:
        print(listing(state, marker))
        return 0
    text, changed = (later if args.later else check)(state, marker)
    if changed:
        write_marker(marker_path, marker)
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
