#!/usr/bin/env python3
"""Agrège plusieurs relevés `installer usage --json` (un par poste) en un bilan Markdown pour la revue d'usage.

Usage : python3 scripts/usage-aggregate.py releve-a.json releve-b.json ... [--catalog skills/catalog.json]
Sans dépendance. Rien n'est envoyé : les fichiers sont ceux que les personnes ont choisi de partager.
"""
import argparse
import json
import os
import sys
from collections import Counter

def load(path):
    with open(path, encoding='utf-8-sig') as handle:
        return json.load(handle)

def table(title, counter, unit='×'):
    lines = ['### ' + title, '', '| Nom | Total |', '| --- | --- |']
    lines += ['| `' + k + '` | ' + str(v) + ' |' for k, v in counter.most_common()]
    return '\n'.join(lines) if counter else '### ' + title + '\n\nAucun.'

def main(argv=None):
    parser = argparse.ArgumentParser(description='Agréger des relevés d’usage.')
    parser.add_argument('files', nargs='+')
    parser.add_argument('--catalog', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills', 'catalog.json'))
    args = parser.parse_args(argv)
    reports = []
    for path in args.files:
        try:
            reports.append(load(path))
        except (OSError, ValueError) as exc:
            print('Relevé ignoré : ' + path + ' (' + str(exc) + ')', file=sys.stderr)
    if not reports:
        print('Aucun relevé lisible.', file=sys.stderr)
        return 2
    totals = Counter()
    commands, skills, agents, categories = Counter(), Counter(), Counter(), Counter()
    frictions = []
    unused_everywhere = None
    for r in reports:
        for key in ('sessions', 'prompts', 'errors'):
            totals[key] += int(r.get(key, 0) or 0)
        commands.update(r.get('commands', {}))
        skills.update(r.get('skills', {}))
        agents.update(r.get('agents', {}))
        frictions += r.get('frictions', [])
        categories.update(r.get('frictions_by_category', {}))
        unused = set(r.get('unused_skills', []))
        unused_everywhere = unused if unused_everywhere is None else unused_everywhere & unused
    try:
        catalog = load(args.catalog)
    except (OSError, ValueError):
        catalog = {}
    candidates = sorted(s for s in (unused_everywhere or set()) if catalog.get(s, {}).get('tier') == 'core' and catalog.get(s, {}).get('category') in ('workflow', 'tool'))
    out = ['# Bilan d’usage agrégé', '', str(len(reports)) + ' postes | ' + str(totals['sessions']) + ' sessions | ' + str(totals['prompts']) + ' prompts | ' + str(totals['errors']) + ' erreurs', '',
           table('Commandes tapées', commands), '', table('Skills activés', skills), '', table('Agents appelés', agents), '',
           '### Candidats du noyau jamais activés sur aucun poste', '', (', '.join('`' + c + '`' for c in candidates) if candidates else 'Aucun.'), '',
           '### Frictions (' + str(len(frictions)) + ')', '']
    groups = Counter((str(f.get('category')), str(f.get('command'))) for f in frictions)
    candidates_groups = [(k, n) for k, n in groups.most_common() if n >= 2]
    out += ['Groupes de deux frictions ou plus (même catégorie, même commande) : un ticket chacun.', '']
    out += (['| Catégorie | Commande | Nombre |', '| --- | --- | --- |'] + ['| ' + c + ' | /' + m + ' | ' + str(n) + ' |' for (c, m), n in candidates_groups] + ['']) if candidates_groups else ['Aucun groupe.', '']
    unknown = Counter()
    repeated = 0
    for r in reports:
        unknown.update(r.get('unknown_commands', {}))
        repeated += int(r.get('repeated_prompts', 0) or 0)
    out += ['Signaux mesurés : commandes inconnues tapées ' + (', '.join('/' + k + ' ×' + str(v) for k, v in unknown.most_common()) or 'aucune') + ' ; demandes répétées dans une même session : ' + str(repeated) + '.', '']
    if frictions:
        out += ['| Catégorie | Commande | Friction | Contexte |', '| --- | --- | --- | --- |']
        for f in sorted(frictions, key=lambda f: (str(f.get('category')), str(f.get('command')))):
            ctx = ' '.join(str(f.get(k)) for k in ('cli', 'os', 'kit', 'profile') if f.get(k)) + (' (auto)' if f.get('source') == 'doctor' else '')
            out.append('| ' + str(f.get('category')) + ' | /' + str(f.get('command')) + ' | ' + str(f.get('text', '')).replace('|', '/') + ' | ' + ctx + ' |')
        out += ['', 'Par catégorie : ' + ', '.join(k + ' ×' + str(v) for k, v in categories.most_common())]
    else:
        out.append('Aucune.')
    print('\n'.join(out))
    return 0

if __name__ == '__main__':
    sys.exit(main())
