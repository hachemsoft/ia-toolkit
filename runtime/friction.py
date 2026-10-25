#!/usr/bin/env python3
"""Note une friction en une ligne dans ~/.ai-kit/frictions.jsonl, localement. Installé par le kit, appelé par /friction.

Usage : python3 ~/.ai-kit/bin/friction.py --category <command|skill|guardrail|docs|tool|auth|other> [--command <nom>] [--cli gemini|agy] --text "<une phrase>"
Le contexte (version du kit, profil, système) est ajouté automatiquement. Rien n'est envoyé ; le relevé d'usage
compte ces lignes et `usage --json` les exporte pour la revue d'usage.
"""
import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone

CATEGORIES = ('command', 'skill', 'guardrail', 'docs', 'tool', 'auth', 'other')

def kit_dir():
    return os.path.join(os.path.expanduser('~'), '.ai-kit')

def context():
    """Version du kit et profil lus dans l'état d'installation, système du poste."""
    info = {'os': {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), platform.system().lower())}
    try:
        with open(os.path.join(kit_dir(), 'state.json'), encoding='utf-8') as handle:
            state = json.load(handle)
        info['kit'] = str(state.get('version', ''))
        info['profile'] = str(state.get('profile', ''))
    except (OSError, ValueError):
        pass
    return info

def record(category, text, command='none', cli='unknown', source='person'):
    text = ' '.join(str(text).split())[:300]
    entry = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'category': category,
             'command': (command or 'none').lstrip('/') or 'none', 'text': text, 'cli': cli, 'source': source}
    entry.update(context())
    os.makedirs(kit_dir(), exist_ok=True)
    path = os.path.join(kit_dir(), 'frictions.jsonl')
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return path, entry

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')  # console qui ne connaît pas un caractère : le remplacer plutôt que planter
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description='Noter une friction, localement.')
    parser.add_argument('--category', required=True, choices=CATEGORIES)
    parser.add_argument('--command', default='none', help='commande du kit en cours, ou none')
    parser.add_argument('--cli', default='unknown', choices=('gemini', 'agy', 'unknown'))
    parser.add_argument('--text', required=True, help='une phrase, sans secret ni texte de prompt')
    args = parser.parse_args(argv)
    text = ' '.join(args.text.split())
    if not text or len(text) > 300:
        print('Le texte doit faire entre 1 et 300 caractères.', file=sys.stderr)
        return 2
    path, entry = record(args.category, text, args.command, args.cli)
    print('Friction notée (' + entry['category'] + ', /' + entry['command'] + ') dans ' + path + ' ; rien n’est envoyé.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
