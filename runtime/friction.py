#!/usr/bin/env python3
"""Logs a friction as one line in ~/.ai-kit/frictions.jsonl, locally. Installed by the kit, called by /friction.

Usage: python3 ~/.ai-kit/bin/friction.py --category <command|skill|guardrail|rule|docs|tool|auth|other> [--command <name>] [--cli gemini|agy|codex|claude] --text "<one sentence>"
       python3 ~/.ai-kit/bin/friction.py --list [N]     the last N frictions (10)
The context (kit version, profile, system) is added automatically. Nothing is sent; the usage report
counts these lines and `usage --json` exports them for the usage review. `ai-kit friction` runs this very
file (installer/cli.py imports it): one implementation, --home for a trial home folder.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone

CATEGORIES = ('command', 'skill', 'guardrail', 'rule', 'docs', 'tool', 'auth', 'other')
# What looks like a secret (API keys and tokens of common services, bearer tokens, password=..., private keys): never kept
# in a friction or shown in a diagnosis. installer/core.py imports it from here (one list).
SECRET = re.compile(r'AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9_-]{20,}|sk_(?:live|test)_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{30,}'
                    r'|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}'
                    r'|ya29\.[0-9A-Za-z_-]{20,}|hf_[A-Za-z0-9]{30,}|npm_[A-Za-z0-9]{30,}|dapi[0-9a-f]{32}|GOCSPX-[A-Za-z0-9_-]{20,}'
                    r'|https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}'
                    r'|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
                    r'|(?i:bearer|basic)\s+[A-Za-z0-9._~+/-]{16,}=*'
                    r'|\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s:/@]{3,}@'
                    r'|(?i:\b(?:[a-z0-9]+_)*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)(?:_[a-z0-9_]*)?\b["\']?\s*[:=]\s*["\']?)'
                    r'(?!\$\{)(?=[^\s"\',;]*[A-Za-z])[^\s"\',;]{6,}')

def redact(text):
    return SECRET.sub('[redacted]', str(text))

def kit_dir(home=None):
    return os.path.join(home or os.path.expanduser('~'), '.ai-kit')

def context(home=None):
    """Kit version and profile read from the installation state, machine operating system."""
    info = {'os': {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), platform.system().lower())}
    try:
        with open(os.path.join(kit_dir(home), 'state.json'), encoding='utf-8') as handle:
            state = json.load(handle)
        info['kit'] = str(state.get('version', ''))
        info['profile'] = str(state.get('profile', ''))
    except (OSError, ValueError):
        pass
    return info

def friction_id(ts, text):
    """Short stable id (6 hex characters) from the date and the sentence; cited in tickets and in the CHANGELOG."""
    return hashlib.sha256((str(ts) + '|' + str(text)).encode('utf-8')).hexdigest()[:6]

def component_version(name, home=None):
    """Version of the kit skill or agent named like the command, from the installation state (0.40), or None."""
    try:
        with open(os.path.join(kit_dir(home), 'state.json'), encoding='utf-8') as handle:
            recorded = (json.load(handle).get('installed') or {}).get('versions') or {}
    except (OSError, ValueError):
        return None
    for kind in ('skills', 'agents'):
        version = (recorded.get(kind) or {}).get(name) or (recorded.get(kind) or {}).get(name.replace('ai-kit-', '', 1))
        if version:
            return kind[:-1] + ' ' + name + ' ' + str(version)
    return None

def record(category, text, command='none', cli='unknown', source='person', home=None):
    text = redact(' '.join(str(text).split()))[:300]
    command = (command or 'none').lstrip('/') or 'none'
    if not re.fullmatch(r'[a-z0-9:_-]{1,40}', command.lower()):
        command = 'none'  # a kit command name, nothing else: the field is never free text
    entry = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'category': category,
             'command': command, 'text': text, 'cli': cli, 'source': source}
    entry.update(context(home))
    version = component_version(entry['command'], home)
    if version:
        entry['component'] = version
    entry['id'] = friction_id(entry['ts'], entry['text'])
    os.makedirs(kit_dir(home), exist_ok=True)
    path = os.path.join(kit_dir(home), 'frictions.jsonl')
    # Readable by the person only: the lines say what they worked on.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return path, entry

def listing(home=None, count=10):
    """The last frictions, oldest first, one line each: id, date, category, command, sentence."""
    path = os.path.join(kit_dir(home), 'frictions.jsonl')
    entries = []
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except OSError:
        pass
    if not entries:
        return ['No friction logged in ' + path + '.']
    lines = []
    for entry in entries[-count:] if count else entries:
        fid = entry.get('id') or friction_id(entry.get('ts'), entry.get('text'))
        lines.append(fid + '  ' + str(entry.get('ts', ''))[:10] + '  ' + str(entry.get('category', '?')) + '  /' + str(entry.get('command', 'none'))
                     + '  ' + str(entry.get('text', '')))
    lines.append(str(len(entries)) + ' friction' + ('s' if len(entries) != 1 else '') + ' in ' + path + '; nothing is sent.')
    return lines

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')  # console that cannot encode a character: replace it rather than crash
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description='Log a friction, locally.')
    parser.add_argument('--category', choices=CATEGORIES, help='required to log a friction')
    parser.add_argument('--list', nargs='?', const=10, type=int, metavar='N', help='show the last N frictions (10) instead of logging one')
    parser.add_argument('--home', help='home folder of the kit installation (default: yours)')
    parser.add_argument('--command', default='none', help='current kit command, or none')
    parser.add_argument('--cli', default='unknown', choices=('gemini', 'agy', 'codex', 'claude', 'unknown'))
    parser.add_argument('--text', help='one sentence, no secret and no prompt text; read from standard input when absent (safer: no shell expansion)')
    args = parser.parse_args(argv)
    if args.list is not None:
        print('\n'.join(listing(args.home, args.list)))
        return 0
    if not args.category:
        parser.error('--category is required (or --list)')
    if args.text is None:
        try:
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')  # PowerShell 7 and shells send UTF-8
        except (AttributeError, ValueError):
            pass
    raw = args.text if args.text is not None else sys.stdin.read()
    text = ' '.join(raw.split())
    if not text or len(text) > 300:
        print('The text must be between 1 and 300 characters.', file=sys.stderr)
        return 2
    path, entry = record(args.category, text, args.command, args.cli, home=args.home)
    print('Friction ' + entry['id'] + ' logged (' + entry['category'] + ', /' + entry['command'] + ') in ' + path + '; nothing is sent.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
