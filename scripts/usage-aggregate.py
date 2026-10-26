#!/usr/bin/env python3
"""Aggregates several `installer usage --json` reports (one per machine) into a Markdown summary for the usage review.

Usage: python3 scripts/usage-aggregate.py report-a.json report-b.json ... [--catalog skills/catalog.json] [--draft-issues]
No dependencies. Nothing is sent: the files are the ones people chose to share. --draft-issues prints one ticket
draft per group of frictions, to paste into the team's tracker by hand; nothing is created automatically.
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
    lines = ['### ' + title, '', '| Name | Total |', '| --- | --- |']
    lines += ['| `' + k + '` | ' + str(v) + ' |' for k, v in counter.most_common()]
    return '\n'.join(lines) if counter else '### ' + title + '\n\nNone.'

# Where a fix usually goes, by friction category (support rule of docs/usage-review.md).
FIX_HINTS = {
    'command': 'fix the command prompt, and add an eval case that reproduces it',
    'skill': 'fix the skill or its description (when it fires), and add an eval case',
    'guardrail': 'adjust the guardrail or its message, or document the legitimate case',
    'rule': 'the written rule is not enough: turn it into a check (eval case, guardrail or doctor check)',
    'docs': 'fix the page, or add a Troubleshooting line',
    'tool': 'add a doctor check or a Troubleshooting line',
    'auth': 'add a doctor --live diagnosis or a Troubleshooting line',
    'other': 'decide the category first, then apply its fix',
}

def draft_issues(frictions):
    """One ticket draft per group of two or more frictions (same category, same command), in Markdown."""
    groups = {}
    for f in frictions:
        groups.setdefault((str(f.get('category')), str(f.get('command'))), []).append(f)
    drafts = []
    for (category, command), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 2:
            continue
        ids = [str(f.get('id')) for f in items if f.get('id')]
        lines = ['## [friction] ' + category + ' on /' + command + ' (' + str(len(items)) + ' reports)', '',
                 '**Reported**', '']
        for f in items:
            ctx = ', '.join(str(f.get(k)) for k in ('cli', 'os', 'kit', 'profile') if f.get(k))
            lines.append('- `' + str(f.get('id', '?')) + '` ' + str(f.get('text', '')) + (' (' + ctx + ')' if ctx else ''))
        lines += ['', '**Suggested fix**: ' + FIX_HINTS.get(category, FIX_HINTS['other']) + '.', '',
                  '**When fixed**: cite them in the CHANGELOG line of the fix: `(frictions: ' + ', '.join(ids) + ')`; each person then sees it in `usage`.', '']
        drafts.append('\n'.join(lines))
    return drafts

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')  # console that cannot encode a character: replace it rather than crash
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description='Aggregate usage reports.')
    parser.add_argument('files', nargs='+')
    parser.add_argument('--draft-issues', action='store_true', help='print one ticket draft per group of frictions (nothing is created)')
    parser.add_argument('--catalog', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills', 'catalog.json'))
    args = parser.parse_args(argv)
    reports = []
    for path in args.files:
        try:
            reports.append(load(path))
        except (OSError, ValueError) as exc:
            print('Report skipped: ' + path + ' (' + str(exc) + ')', file=sys.stderr)
    if not reports:
        print('No readable report.', file=sys.stderr)
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
    out = ['# Aggregated usage summary', '', str(len(reports)) + ' machines | ' + str(totals['sessions']) + ' sessions | ' + str(totals['prompts']) + ' prompts | ' + str(totals['errors']) + ' errors', '',
           table('Commands typed', commands), '', table('Skills activated', skills), '', table('Agents called', agents), '',
           '### Core candidates never activated on any machine', '', (', '.join('`' + c + '`' for c in candidates) if candidates else 'None.'), '',
           '### Frictions (' + str(len(frictions)) + ')', '']
    groups = Counter((str(f.get('category')), str(f.get('command'))) for f in frictions)
    candidates_groups = [(k, n) for k, n in groups.most_common() if n >= 2]
    out += ['Groups of two or more frictions (same category, same command): one ticket each.', '']
    out += (['| Category | Command | Count |', '| --- | --- | --- |'] + ['| ' + c + ' | /' + m + ' | ' + str(n) + ' |' for (c, m), n in candidates_groups] + ['']) if candidates_groups else ['No group.', '']
    unknown = Counter()
    repeated = 0
    for r in reports:
        unknown.update(r.get('unknown_commands', {}))
        repeated += int(r.get('repeated_prompts', 0) or 0)
    out += ['Measured signals: unknown commands typed ' + (', '.join('/' + k + ' ×' + str(v) for k, v in unknown.most_common()) or 'none') + '; requests repeated within one session: ' + str(repeated) + '.', '']
    if frictions:
        out += ['| Id | Category | Command | Friction | Context |', '| --- | --- | --- | --- | --- |']
        for f in sorted(frictions, key=lambda f: (str(f.get('category')), str(f.get('command')))):
            ctx = ' '.join(str(f.get(k)) for k in ('cli', 'os', 'kit', 'profile') if f.get(k)) + (' (auto)' if f.get('source') == 'doctor' else '')
            out.append('| `' + str(f.get('id', '')) + '` | ' + str(f.get('category')) + ' | /' + str(f.get('command')) + ' | ' + str(f.get('text', '')).replace('|', '/') + ' | ' + ctx + ' |')
        out += ['', 'By category: ' + ', '.join(k + ' ×' + str(v) for k, v in categories.most_common())]
    else:
        out.append('None.')
    if args.draft_issues:
        drafts = draft_issues(frictions)
        out += ['', '# Ticket drafts (' + str(len(drafts)) + ')', '', 'Paste each draft into the team\'s tracker by hand; nothing has been created.', ''] + (drafts or ['No group of two or more frictions.'])
    print('\n'.join(out))
    return 0

if __name__ == '__main__':
    sys.exit(main())
