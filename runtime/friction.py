#!/usr/bin/env python3
"""Logs a friction as one line in ~/.ai-kit/frictions.jsonl, locally. Installed by the kit, called by /friction.

Usage: python3 ~/.ai-kit/bin/friction.py --category <command|skill|guardrail|rule|docs|tool|auth|other> [--command <name>] [--cli gemini|agy|codex|claude] --text "<one sentence>"
The context (kit version, profile, system) is added automatically. Nothing is sent; the usage report
counts these lines and `usage --json` exports them for the usage review.
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
# in a friction or shown in a diagnosis. Same list in installer/core.py (a test checks it).
SECRET = re.compile(r'AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}'
                    r'|glpat-[A-Za-z0-9_-]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|ya29\.[0-9A-Za-z_-]{20,}'
                    r'|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
                    r'|(?i:bearer)\s+[A-Za-z0-9._~+/-]{16,}=*'
                    r'|(?i:\b(?:password|passwd|pwd|secret|token|api[_-]?key)\b\s*[:=]\s*)(?!\$\{)[^\s"\',;]{6,}')

def redact(text):
    return SECRET.sub('[redacted]', str(text))

def kit_dir():
    return os.path.join(os.path.expanduser('~'), '.ai-kit')

def context():
    """Kit version and profile read from the installation state, machine operating system."""
    info = {'os': {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), platform.system().lower())}
    try:
        with open(os.path.join(kit_dir(), 'state.json'), encoding='utf-8') as handle:
            state = json.load(handle)
        info['kit'] = str(state.get('version', ''))
        info['profile'] = str(state.get('profile', ''))
    except (OSError, ValueError):
        pass
    return info

def friction_id(ts, text):
    """Short stable id (6 hex characters) from the date and the sentence; cited in tickets and in the CHANGELOG."""
    return hashlib.sha256((str(ts) + '|' + str(text)).encode('utf-8')).hexdigest()[:6]

def record(category, text, command='none', cli='unknown', source='person'):
    text = redact(' '.join(str(text).split()))[:300]
    entry = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'category': category,
             'command': (command or 'none').lstrip('/') or 'none', 'text': text, 'cli': cli, 'source': source}
    entry.update(context())
    entry['id'] = friction_id(entry['ts'], entry['text'])
    os.makedirs(kit_dir(), exist_ok=True)
    path = os.path.join(kit_dir(), 'frictions.jsonl')
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return path, entry

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')  # console that cannot encode a character: replace it rather than crash
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description='Log a friction, locally.')
    parser.add_argument('--category', required=True, choices=CATEGORIES)
    parser.add_argument('--command', default='none', help='current kit command, or none')
    parser.add_argument('--cli', default='unknown', choices=('gemini', 'agy', 'codex', 'claude', 'unknown'))
    parser.add_argument('--text', help='one sentence, no secret and no prompt text; read from standard input when absent (safer: no shell expansion)')
    args = parser.parse_args(argv)
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
    path, entry = record(args.category, text, args.command, args.cli)
    print('Friction ' + entry['id'] + ' logged (' + entry['category'] + ', /' + entry['command'] + ') in ' + path + '; nothing is sent.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
