#!/usr/bin/env python3
"""Kit hook (session start): tells the agent, once, what is new in the configuration installed.

Input: the CLI's SessionStart JSON (`source`: startup, resume, clear, compact, fork; absent means startup). Output: {}
or {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}} (Claude Code, Codex, Gemini CLI);
for Antigravity CLI, recognised by its `conversationId`, {"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]},
its own SessionStart contract (a message persisted in the conversation, read by the model). Exit 0 always: a session is
never blocked or slowed by this script. What it announces, each once (marker ~/.ai-kit/news.json):
  - the CHANGELOG section of the version installed (state.json `version`, ~/.ai-kit/news/CHANGELOG.md);
  - the entries of the active Core's NEWS.md (~/.ai-kit/news/NEWS.md) aimed at everyone or at the active team;
  - an offer of /me while the personal context (~/.ai-kit/context/USER.md) is still the one the installer created.
Both are copies the installation writes from the active content: no network, no remote text in the agent's context. A newer
Core is said by `ai-kit status` (from the last sync), never by this hook. Also runs the local friction upkeep (ADR 0023).
"""
import json
import os
import re
import sys
from datetime import date

MARKER = 'news.json'
CONTEXT_LIMIT = 8000
SOURCES = ('startup', 'resume')
HEADING = re.compile(r'^## (\d{4}-\d{2}-\d{2}) ([a-z0-9-]{3,32}) : (.+?)\s*$')
META = re.compile(r'^(teams|until):\s*(.*?)\s*$')
ROLE_PLACEHOLDER = '<!-- One line: my role and what I work on these weeks. -->'  # installer/cli.py, same text
OFFER_ME = ('The personal context is still the default one: in one line, offer the person /me ($me in Codex) to fill it '
            'in, about two minutes; do not start it yourself, and handle their request.')
INSTRUCTION = ('[ai-kit] New since the last session. In your first reply, say it in one line per item below, in the '
               "person's language; give details only if asked.")


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
    """The lines under "## <version> (<date>)" of a CHANGELOG, up to the next '## ' heading."""
    lines, keep = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            if keep:
                break
            keep = (line[3:].split() or [''])[0] == version  # '## 4.1.0 (2026-11-10)'
            continue
        if keep:
            lines.append(line)
    return '\n'.join(lines).strip()


def parse_news(text):
    """NEWS.md -> entries: {'date', 'id', 'title', 'teams', 'until', 'text'}; a section without a valid
    heading is skipped (`check_news.py` refuses it in CI). Metadata: `key: value` lines right after the heading."""
    entries, current, in_meta = [], None, False
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = {'date': heading.group(1), 'id': heading.group(2), 'title': heading.group(3), 'teams': [], 'until': '', 'lines': []}
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
        in_meta = False
        current['lines'].append(line)
    for entry in entries:
        entry['text'] = '\n'.join(entry.pop('lines')).strip()
    return entries


def aimed_at(entry, team, today):
    if entry['until'] and entry['until'] < today:
        return False
    if entry['teams'] and team not in entry['teams']:
        return False
    return True


def whats_new(state, marker, news_dir, today, user_text=''):
    """Lines to announce, and the marker updated. Pure: reads the copies in news_dir only; user_text is USER.md's text."""
    items, team = [], str(state.get('team') or '')
    version = str(state.get('version') or '').strip()
    announced_versions = [v for v in marker.get('announced_versions', []) if isinstance(v, str)]
    announced_news = [n for n in marker.get('announced_news', []) if isinstance(n, str)]
    if version and version not in announced_versions:
        section = changelog_section(file_text(os.path.join(news_dir, 'CHANGELOG.md')), version)
        items.append('Kit version '+version+' installed.'+(' What changed:\n'+indent(section) if section else ''))
        announced_versions.append(version)
    for entry in parse_news(file_text(os.path.join(news_dir, 'NEWS.md'))):
        if entry['id'] in announced_news or not aimed_at(entry, team, today):
            continue
        items.append('News ('+entry['date']+') '+entry['title']+(':\n'+indent(entry['text']) if entry['text'] else '.'))
        announced_news.append(entry['id'])
    marker['announced_versions'], marker['announced_news'] = announced_versions, announced_news
    if ROLE_PLACEHOLDER in user_text and not marker.get('offered_me'):
        items.append(OFFER_ME)
        marker['offered_me'] = True
    return items, marker


def indent(text):
    return '\n'.join('  '+line if line else '' for line in text.splitlines())


def context_text(items):
    text = INSTRUCTION+'\n'+'\n'.join('- '+item for item in items)
    if len(text) > CONTEXT_LIMIT:
        text = text[:CONTEXT_LIMIT-20].rstrip()+'\n  (truncated)'
    return text


def answer(payload, text, person=None):
    """The hook's answer in the form of the CLI that asked: agy (conversationId) injects a persisted system message; the
    others read hookSpecificOutput.additionalContext, and show systemMessage to the person."""
    if payload.get('conversationId') is not None:
        return {'injectSteps': [{'systemMessage': {'systemMessage': text}}]}
    output = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}}
    return {'systemMessage': person, **output} if person else output


CHECK_MISSING = ('AI Kit integrity: the kit\'s integrity check (~/.ai-kit/hooks/integrity.py) is missing or was changed, so changes to '
                 'what the kit installed are no longer reported. Say it to the person in the first line of your reply; they restore it '
                 'with: ai-kit sync --offline --restore')


def integrity(home, state):
    """(agent text, person text) of the integrity check next to this script, run in full at session start. When the kit
    installed it and it is missing or changed, that is said instead: it cannot report on itself. (None, None) otherwise; a
    session always starts."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'integrity.py')
    expected = (state.get('files') or {}).get('.ai-kit/hooks/integrity.py') if isinstance(state.get('files'), dict) else None
    try:
        if expected:
            import hashlib
            with open(script, 'rb') as handle:
                if hashlib.sha256(handle.read()).hexdigest() != expected:
                    raise ValueError('changed')
        import importlib.util
        spec = importlib.util.spec_from_file_location('ai_kit_integrity', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.checked(home, full=True)
    except Exception:
        if expected:
            return CHECK_MISSING, 'AI Kit: the integrity check ~/.ai-kit/hooks/integrity.py is missing or changed. To restore: ai-kit sync --offline --restore'
        return None, None


def write_marker(path, text):
    """Atomic: a session reading the marker never sees a half-written file (two sessions can start the same minute)."""
    temp = path+'.'+str(os.getpid())+'.tmp'
    with open(temp, 'w', encoding='utf-8') as handle:
        handle.write(text)
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)


def friction_upkeep(kit, state):
    """ADR 0023: the local friction upkeep (purge after the retention, waiting count) at session start, from the friction script
    the kit installed; any failure is silent and never delays the session beyond the script's own work."""
    script = os.path.join(kit, 'bin', 'friction.py')
    if not os.path.isfile(script):
        return 0
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('ai_kit_friction_upkeep', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.housekeep(os.path.dirname(kit), state.get('frictions_retention'))['waiting']
    except Exception:
        return 0


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
                items, marker = whats_new(state, read_json(marker_path), os.path.join(kit, 'news'), date.today().isoformat(),
                                          file_text(os.path.join(kit, 'context', 'USER.md')))
                after = json.dumps(marker, ensure_ascii=False, indent=1)
                if after != before and items:
                    write_marker(marker_path, after)
                waiting = friction_upkeep(kit, state)
                if waiting:
                    items.append(str(waiting)+' friction(s) logged here wait for the person\'s approval before they reach the team\'s tracker: '
                                 'they send them from a terminal with ai-kit friction --publish. Never run it yourself.')
                agent, person = integrity(os.path.expanduser('~'), state)
                text = context_text(items) if items else ''
                if agent:  # the integrity check comes first: it is about what watches the agent
                    text = agent + ('\n\n' + text if text else '')
                if text:
                    output = answer(payload, text, person)
    except Exception:
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
