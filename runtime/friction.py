#!/usr/bin/env python3
"""Logs a friction as one line in ~/.ai-kit/frictions.jsonl, locally. Installed by the kit, called by /friction.

Usage: python3 ~/.ai-kit/bin/friction.py --category <command|skill|guardrail|rule|docs|tool|auth|other> [--command <name>] [--cli gemini|agy|codex|claude] --text "<one sentence>"
       python3 ~/.ai-kit/bin/friction.py --list [N]     the last N frictions (10)
       python3 ~/.ai-kit/bin/friction.py --sync         send to the tracker what was not sent
The context (kit version, team, system) is added automatically. Nothing is sent, unless IT set a friction tracker
(managed.toml [frictions.tracker], recorded by the installation in state.json): then a friction whose
source is in its `sources` (agent by default: --source agent when the agent logs on its own) is created as an issue
through the person's own glab or gh, signed in by them; the kit holds no token. Any failure keeps the friction local.
`ai-kit friction` runs this very file (installer/cli.py imports it): one implementation, --home for a trial home.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

CATEGORIES = ('command', 'skill', 'guardrail', 'rule', 'docs', 'tool', 'auth', 'other')
SOURCES = ('person', 'agent')  # doctor --live records 'doctor' itself
# The person's CLI for each tracker: the documented long flags, issue create, --flag=value so that a sentence starting
# with - is a value. glab takes labels as one comma list, gh takes --label several times.
TRACKERS = {'gitlab': {'cli': 'glab', 'body': '--description', 'labels': 'comma'},
            'github': {'cli': 'gh', 'body': '--body', 'labels': 'repeat'}}
SEND_TIMEOUT = 30
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

# 2.1 (ADR 0023): what could identify a person or a machine is redacted too, before a friction is stored or sent.
PERSONAL = ((re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), '[email]'),
            (re.compile(r'(?:/Users|/home)/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+'), '~'),
            (re.compile(r'\b(?:[a-z0-9-]+\.)+(?:internal|corp|lan|local|intra)\b', re.I), '[host]'))
RETENTION_DAYS = 30

def redact(text):
    text = SECRET.sub('[redacted]', str(text))
    for pattern, replacement in PERSONAL:
        text = pattern.sub(replacement, text)
    return text

def fingerprint(entry):
    """The same friction told twice has the same fingerprint: category, command, component and the text without digits."""
    text = re.sub(r'[0-9]+', '', ' '.join(str(entry.get('text', '')).lower().split()))
    key = '|'.join(str(entry.get(k, '')) for k in ('category', 'command', 'component')) + '|' + text
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]

def kit_dir(home=None):
    return os.path.join(home or os.path.expanduser('~'), '.ai-kit')

def private(descriptor):
    """Readable by the person only, also when the file was left by an older version with another mode (0.51.1). POSIX only."""
    if hasattr(os, 'fchmod'):
        try:
            os.fchmod(descriptor, 0o600)
        except OSError:
            pass

def context(home=None):
    """Kit version and team read from the installation state, machine operating system."""
    info = {'os': {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), platform.system().lower())}
    try:
        with open(os.path.join(kit_dir(home), 'state.json'), encoding='utf-8') as handle:
            state = json.load(handle)
        info['kit'] = str(state.get('version', ''))
        if state.get('team'):
            info['team'] = str(state['team'])  # 2.2: the team, not a profile (ADR 0018)
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
    entry['fingerprint'] = fingerprint(entry)
    os.makedirs(kit_dir(home), exist_ok=True)
    path = os.path.join(kit_dir(home), 'frictions.jsonl')
    # Readable by the person only: the lines say what they worked on.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    private(descriptor)
    with os.fdopen(descriptor, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return path, entry

def tracker(home=None):
    """The tracker update recorded in state.json, or None (no tracker, or the person opted out)."""
    try:
        with open(os.path.join(kit_dir(home), 'state.json'), encoding='utf-8') as handle:
            config = json.load(handle).get('friction_tracker')
    except (OSError, ValueError):
        return None
    return config if isinstance(config, dict) and config.get('kind') in TRACKERS and config.get('project') else None

def sent_file(home=None):
    return os.path.join(kit_dir(home), 'frictions-sent.json')

def read_sent(home=None):
    try:
        with open(sent_file(home), encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def issue_command(config, entry, exe):
    """The command that creates the issue: arguments only, no shell."""
    kind = TRACKERS[config['kind']]
    repo = ((config.get('host') + '/') if config.get('host') and config['kind'] == 'github' else '') + config['project']
    if config.get('host') and config['kind'] == 'gitlab':
        repo = 'https://' + config['host'] + '/' + config['project']
    context = ', '.join(k + ' ' + str(entry[k]) for k in ('cli', 'os', 'kit', 'team', 'source', 'occurrences', 'fingerprint') if entry.get(k))
    body = (entry.get('text', '') + '\n\nContext: ' + context + '\nFriction id: ' + entry['id']
            + '. When fixed, cite it in the CHANGELOG line of the fix: (frictions: ' + entry['id'] + ').\n'
            + 'Logged by the AI Kit /friction command on the workstation: one sentence, nothing else is read or sent.')
    command = [exe, 'issue', 'create', '--repo=' + repo, '--title=[friction] ' + str(entry.get('category')) + ' on /' + str(entry.get('command', 'none')),
               kind['body'] + '=' + body]
    labels = [str(label) for label in config.get('labels') or ['friction']]
    if labels:
        command += ['--label=' + ','.join(labels)] if kind['labels'] == 'comma' else ['--label=' + label for label in labels]
    return command

def send(entry, home=None, config=None):
    """Creates the issue for one friction through the person's CLI. Returns (status, detail): sent (the URL), skipped
    (not a source the organization sends, or already sent), off (no tracker), failed (why; the friction stays local)."""
    config = config or tracker(home)
    if not config:
        return 'off', ''
    if entry.get('source') not in (config.get('sources') or ['agent']):
        return 'skipped', 'source ' + str(entry.get('source'))
    if entry['id'] in read_sent(home):
        return 'skipped', 'already sent'
    cli = TRACKERS[config['kind']]['cli']
    exe = shutil.which(cli)
    if not exe:
        return 'failed', cli + ' not on the PATH'
    try:
        proc = subprocess.run(issue_command(config, entry, exe), capture_output=True, text=True, encoding='utf-8', errors='replace',
                              stdin=subprocess.DEVNULL, timeout=SEND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return 'failed', cli + ' did not answer within ' + str(SEND_TIMEOUT) + ' s'
    except OSError as exc:
        return 'failed', str(exc)
    if proc.returncode != 0:
        reason = (proc.stderr or proc.stdout).strip().splitlines()
        return 'failed', redact(reason[-1] if reason else cli + ' failed (' + str(proc.returncode) + ')')
    urls = [word for word in proc.stdout.split() if word.startswith('http')]
    url = urls[-1] if urls else '(issue created, no URL printed)'
    sent = read_sent(home)
    sent[entry['id']] = {'url': url, 'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'fingerprint': entry.get('fingerprint') or fingerprint(entry)}
    descriptor = os.open(sent_file(home), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    private(descriptor)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(sent, handle, ensure_ascii=False, indent=1)
    return 'sent', url

def send_line(status, detail):
    """One line for the person after a send; nothing for off and skipped."""
    if status == 'sent':
        return 'Issue created: ' + detail
    if status == 'waiting':
        return 'Not sent yet: your organization asks for your approval. Run ai-kit friction --publish in a terminal to send it.'
    if status == 'failed':
        return 'Issue not created (' + detail + '): the friction is kept locally; ai-kit friction --publish sends it later.'
    return ''

def entries(home=None):
    path = os.path.join(kit_dir(home), 'frictions.jsonl')
    found = []
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entry['id'] = entry.get('id') or friction_id(entry.get('ts'), entry.get('text'))
                    found.append(entry)
    except OSError:
        pass
    return path, found

def unsent(home=None, config=None):
    """The frictions the tracker expects and that were not sent."""
    config = config or tracker(home)
    if not config:
        return []
    sent = read_sent(home)
    sent_prints = {v.get('fingerprint') for v in sent.values() if isinstance(v, dict)}
    pending, seen = [], {}
    for entry in entries(home)[1]:
        if entry.get('source') not in (config.get('sources') or ['agent']) or entry['id'] in sent:
            continue
        mark = entry.get('fingerprint') or fingerprint(entry)
        if mark in sent_prints:
            continue  # the same friction was already published once
        if mark in seen:
            seen[mark]['occurrences'] = seen[mark].get('occurrences', 1) + 1  # one issue, its count
            continue
        seen[mark] = dict(entry, fingerprint=mark)
        pending.append(seen[mark])
    return pending

def housekeep(home=None, retention_days=None, now=None):
    """Local upkeep (ADR 0023), run at session start and by engine commands: entries older than the retention are purged
    (a rewrite under a lock, atomic; skipped when another process holds the lock), and the frictions waiting for the
    person's approval are counted. Reads frictions.jsonl only; never the network. Returns {'purged': n, 'waiting': n}."""
    path, found = entries(home)
    days = retention_days or RETENTION_DAYS
    now = now or datetime.now(timezone.utc)
    def recent(entry):
        try:
            return (now - datetime.strptime(str(entry.get('ts')), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)).days < days
        except ValueError:
            return True
    kept = [e for e in found if recent(e)]
    purged = len(found) - len(kept)
    if purged:
        lock = path + '.lock'
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            purged = 0  # another process is rewriting it: next time
        else:
            os.close(descriptor)
            try:
                temp = path + '.tmp'
                handle_fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                private(handle_fd)
                with os.fdopen(handle_fd, 'w', encoding='utf-8') as handle:
                    handle.writelines(json.dumps(e, ensure_ascii=False) + '\n' for e in kept)
                os.replace(temp, path)
            finally:
                os.unlink(lock)
    config = tracker(home)
    waiting = len(unsent(home, config)) if config and config.get('publication', 'auto') == 'approval' else 0
    return {'purged': purged, 'waiting': waiting}

def sync(home=None):
    """Sends what was not sent, one issue each; stops at the first failure (the same cause would repeat)."""
    config = tracker(home)
    if not config:
        return ['No friction tracker set by your organization: frictions stay local.']
    pending = unsent(home, config)
    if not pending:
        return ['Nothing to send: every friction the tracker expects was sent.']
    lines = []
    for entry in pending:
        status, detail = send(entry, home, config)
        lines.append(entry['id'] + ': ' + send_line(status, detail))
        if status == 'failed':
            lines.append(str(len(pending) - len(lines) + 1) + ' friction(s) still to send: fix the cause, then --sync again.')
            break
    return lines

def analyze(home=None):
    """The local frictions grouped by fingerprint, the most frequent first: what keeps getting in the way (ADR 0023). Local only."""
    groups = {}
    for entry in entries(home)[1]:
        mark = entry.get('fingerprint') or fingerprint(entry)
        group = groups.setdefault(mark, {'count': 0, 'first': entry.get('ts', ''), 'last': '', 'entry': entry})
        group['count'] += 1
        group['last'] = max(group['last'], entry.get('ts', ''))
        group['first'] = min(group['first'], entry.get('ts', '')) or entry.get('ts', '')
    if not groups:
        return ['No friction logged here.']
    lines = [str(len(groups))+' distinct friction(s), the most frequent first:']
    for group in sorted(groups.values(), key=lambda g: (-g['count'], g['last'])):
        e = group['entry']
        lines.append('  '+str(group['count'])+'x ['+str(e.get('category'))+'] /'+str(e.get('command', 'none'))+': '+str(e.get('text', ''))
                     + ' ('+group['first'][:10]+(' to '+group['last'][:10] if group['last'][:10] != group['first'][:10] else '')+')')
    return lines

def listing(home=None, count=10):
    """The last frictions, oldest first, one line each: id, date, category, command, sentence."""
    path, found = entries(home)
    if not found:
        return ['No friction logged in ' + path + '.']
    sent = read_sent(home)
    lines = []
    for entry in found[-count:] if count else found:
        lines.append(entry['id'] + '  ' + str(entry.get('ts', ''))[:10] + '  ' + str(entry.get('category', '?')) + '  /' + str(entry.get('command', 'none'))
                     + '  ' + str(entry.get('text', '')) + ('  -> ' + sent[entry['id']]['url'] if entry['id'] in sent else ''))
    pending = len(unsent(home))
    lines.append(str(len(found)) + ' friction' + ('s' if len(found) != 1 else '') + ' in ' + path
                 + ('; ' + str(pending) + ' not sent to the tracker yet (ai-kit friction --publish).' if pending else '; nothing is sent.' if not tracker(home) else '.'))
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
    parser.add_argument('--analyze', action='store_true', help='group the local frictions by kind, the most frequent first (nothing is sent)')
    parser.add_argument('--sync', action='store_true', help='send to the tracker the frictions not sent yet, instead of logging one')
    parser.add_argument('--source', default='person', choices=SOURCES, help='agent when the agent logs on its own (auto mode); person otherwise')
    parser.add_argument('--home', help='home folder of the kit installation (default: yours)')
    parser.add_argument('--command', default='none', help='current kit command, or none')
    parser.add_argument('--cli', default='unknown', choices=('gemini', 'agy', 'codex', 'claude', 'unknown'))
    parser.add_argument('--text', help='one sentence, no secret and no prompt text; read from standard input when absent (safer: no shell expansion)')
    args = parser.parse_args(argv)
    if args.list is not None:
        print('\n'.join(listing(args.home, args.list)))
        return 0
    if args.analyze:
        print('\n'.join(analyze(args.home)))
        return 0
    if args.sync:
        lines = sync(args.home)
        print('\n'.join(lines))
        return 1 if any('still to send' in line for line in lines) else 0
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
    path, entry = record(args.category, text, args.command, args.cli, source=args.source, home=args.home)
    config = tracker(args.home)
    # approval (the default since 2.0.0): nothing leaves on its own; the person sends from a terminal (--sync).
    status, detail = ('waiting', '') if config and config.get('publication', 'auto') == 'approval' else send(entry, args.home, config)
    print('Friction ' + entry['id'] + ' logged (' + entry['category'] + ', /' + entry['command'] + ') in ' + path + ('.' if status != 'off' else '; nothing is sent.'))
    line = send_line(status, detail)
    if line:
        print(line)
    return 0

if __name__ == '__main__':
    sys.exit(main())
