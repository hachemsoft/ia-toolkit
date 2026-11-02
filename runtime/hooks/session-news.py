#!/usr/bin/env python3
"""Kit hook (session start): tells the agent, once, what is new, and whether a newer kit version is available.

Input: the CLI's SessionStart JSON (`source`: startup, resume, clear, compact, fork; absent means startup). Output: {}
or {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}} (Claude Code, Codex, Gemini CLI);
for Antigravity CLI, recognised by its `conversationId`, {"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]},
its own SessionStart contract (a message persisted in the conversation, read by the model). Exit 0 always: a session is
never blocked or slowed by this script. What it announces, each once (marker ~/.ai-kit/news.json):
  - the CHANGELOG section of the version just installed (state.json `version`, CHANGELOG.md of the kit folder);
  - the entries of NEWS.md (the kit folder, and origin/main after the daily read) aimed at this profile and team;
  - a newer version on origin/main, unless the person declined it (`ai-kit news --later`).
The remote read: at most once a day, only when the kit folder (state.json `kit_dir`) is a git clone with an origin and
`news.check_remote` is not false: `git fetch origin main` (5 s, no credential prompt), then `git show` of VERSION and
NEWS.md on origin/main; the working tree is never touched, nothing is sent, every failure is silent (doctor shows it).
The update itself is never run here: the agent proposes, the person runs `ai-kit update`. (ADR 0012)
"""
import json
import os
import re
import subprocess
import sys
from datetime import date

MARKER = 'news.json'
FETCH_TIMEOUT = 5
CONTEXT_LIMIT = 8000
SOURCES = ('startup', 'resume')
HEADING = re.compile(r'^## (\d{4}-\d{2}-\d{2}) ([a-z0-9-]{3,32}) : (.+?)\s*$')
META = re.compile(r'^(profiles|teams|until):\s*(.*?)\s*$')
INSTRUCTION = ('[ai-kit] New since the last session. In your first reply, say it in one line per item below, in the '
               "person's language; give details only if asked. Never run `ai-kit update` yourself.")
UPDATE_INSTRUCTION = ('Propose the update. If the person says yes, tell them to run `ai-kit update` in a terminal and say '
                      'what will change; if no, run `ai-kit news --later` and do not mention it again.')


def use_utf8():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass


def read_json(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def file_text(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read()
    except (OSError, ValueError):
        return ''


def version_tuple(text):
    """'0.47.0' -> (0, 47, 0); a part that is not a number counts as 0; '' -> ()."""
    parts = []
    for part in str(text or '').strip().split('.'):
        digits = re.match(r'\d+', part)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts) if str(text or '').strip() else ()


def changelog_section(text, version):
    """The lines under '## <version>' of a CHANGELOG, up to the next '## ' heading."""
    lines, keep = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            if keep:
                break
            keep = line[3:].strip() == version
            continue
        if keep:
            lines.append(line)
    return '\n'.join(lines).strip()


def parse_news(text):
    """NEWS.md -> entries: {'date', 'id', 'title', 'profiles', 'teams', 'until', 'text'}; a section without a valid
    heading is skipped (`check_news.py` refuses it in CI). Metadata: `key: value` lines right after the heading."""
    entries, current, in_meta = [], None, False
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = {'date': heading.group(1), 'id': heading.group(2), 'title': heading.group(3), 'profiles': [], 'teams': [], 'until': '', 'lines': []}
            entries.append(current)
            in_meta = True
            continue
        if line.startswith('## ') or line.startswith('# '):
            current, in_meta = None, False
            continue
        if current is None:
            continue
        meta = META.match(line) if in_meta else None
        if meta:
            key, value = meta.groups()
            if key == 'until':
                current['until'] = value
            else:
                current[key] = [v.strip() for v in value.split(',') if v.strip()]
            continue
        if line.strip():
            in_meta = False
        current['lines'].append(line)
    for entry in entries:
        entry['text'] = '\n'.join(entry.pop('lines')).strip()
    return entries


def aimed_at(entry, profile, team, today):
    if entry['until'] and entry['until'] < today:
        return False
    if entry['profiles'] and profile not in entry['profiles']:
        return False
    if entry['teams'] and team not in entry['teams']:
        return False
    return True


def git(kit_dir, *args, timeout=FETCH_TIMEOUT):
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': 'echo', 'SSH_ASKPASS': 'echo', 'GCM_INTERACTIVE': 'never'}
    return subprocess.run(['git', '-C', kit_dir, *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          stdin=subprocess.DEVNULL, timeout=timeout, env=env)


def remote_read(kit_dir):
    """(result, detail, remote VERSION, remote NEWS.md). A read only: fetch, then show on origin/main."""
    if not os.path.isdir(os.path.join(kit_dir, '.git')):
        return 'skipped', 'not a git clone', '', ''
    try:
        if git(kit_dir, 'remote', 'get-url', 'origin', timeout=FETCH_TIMEOUT).returncode != 0:
            return 'skipped', 'no origin remote', '', ''
        fetched = git(kit_dir, 'fetch', '--quiet', 'origin', 'main')
        if fetched.returncode != 0:
            reason = (fetched.stderr or fetched.stdout).strip().splitlines()
            return 'failed', (reason[-1] if reason else 'git fetch failed'), '', ''
        version = git(kit_dir, 'show', 'origin/main:VERSION')
        news = git(kit_dir, 'show', 'origin/main:NEWS.md')
    except (OSError, subprocess.SubprocessError) as exc:
        return 'failed', str(exc).splitlines()[0] if str(exc) else 'git failed', '', ''
    if version.returncode != 0:
        return 'failed', 'no VERSION on origin/main', '', ''
    return 'ok', '', version.stdout.strip(), news.stdout if news.returncode == 0 else ''


def whats_new(state, marker, kit_dir, today, check_remote=True):
    """Lines to announce, and the marker updated. Pure apart from the remote read (check_remote False skips it)."""
    items, profile, team = [], str(state.get('profile') or ''), str(state.get('team') or '')
    version = str(state.get('version') or '').strip()
    announced_versions = [v for v in marker.get('announced_versions', []) if isinstance(v, str)]
    announced_news = [n for n in marker.get('announced_news', []) if isinstance(n, str)]
    if version and version not in announced_versions:
        section = changelog_section(file_text(os.path.join(kit_dir, 'CHANGELOG.md')), version) if kit_dir else ''
        items.append('Kit updated to '+version+'.'+(' What changed:\n'+indent(section) if section else ' What changed: CHANGELOG.md of the kit.'))
        announced_versions.append(version)
    news_texts = [file_text(os.path.join(kit_dir, 'NEWS.md'))] if kit_dir else []
    remote_version = ''
    last = marker.get('last_check') if isinstance(marker.get('last_check'), dict) else {}
    if check_remote and kit_dir and os.path.isdir(kit_dir) and last.get('date') != today:
        result, detail, remote_version, remote_news = remote_read(kit_dir)
        if result != 'skipped':
            marker['last_check'] = {'date': today, 'result': result, **({'detail': detail} if detail else {}), **({'remote_version': remote_version} if remote_version else {})}
        news_texts.append(remote_news)
    for text in news_texts:
        for entry in parse_news(text):
            if entry['id'] in announced_news or not aimed_at(entry, profile, team, today):
                continue
            items.append('News ('+entry['date']+') '+entry['title']+(':\n'+indent(entry['text']) if entry['text'] else '.'))
            announced_news.append(entry['id'])
    if remote_version and version_tuple(remote_version) > version_tuple(version) and remote_version != marker.get('declined_version'):
        items.append('A newer kit version is available: '+remote_version+' (installed: '+(version or 'unknown')+'). '+UPDATE_INSTRUCTION)
    marker['announced_versions'], marker['announced_news'] = announced_versions, announced_news
    return items, marker


def indent(text):
    return '\n'.join('  '+line if line else '' for line in text.splitlines())


def context_text(items):
    text = INSTRUCTION+'\n'+'\n'.join('- '+item for item in items)
    if len(text) > CONTEXT_LIMIT:
        text = text[:CONTEXT_LIMIT-20].rstrip()+'\n  (truncated)'
    return text


def answer(payload, text):
    """The hook's answer in the form of the CLI that asked: agy (conversationId) injects a persisted system message; the
    others read hookSpecificOutput.additionalContext."""
    if payload.get('conversationId') is not None:
        return {'injectSteps': [{'systemMessage': {'systemMessage': text}}]}
    return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}}


def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = None
    output = {}
    try:
        if isinstance(payload, dict) and str(payload.get('source') or 'startup') in SOURCES:
            kit = os.path.join(os.path.expanduser('~'), '.ai-kit')
            state = read_json(os.path.join(kit, 'state.json'))
            if state:
                marker_path = os.path.join(kit, MARKER)
                before = file_text(marker_path)
                kit_dir = str(state.get('kit_dir') or '')
                check = (state.get('news') or {}).get('check_remote', True) is not False
                items, marker = whats_new(state, read_json(marker_path), kit_dir if os.path.isdir(kit_dir) else '', date.today().isoformat(), check)
                after = json.dumps(marker, ensure_ascii=False, indent=1)
                if after != before and (items or marker.get('last_check')):
                    with open(marker_path, 'w', encoding='utf-8') as handle:
                        handle.write(after)
                    try:
                        os.chmod(marker_path, 0o600)
                    except OSError:
                        pass
                if items:
                    output = answer(payload, context_text(items))
    except Exception:
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
