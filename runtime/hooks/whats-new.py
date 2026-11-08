#!/usr/bin/env python3
"""Kit hook (session start): tells the agent, once, what is new, and whether a newer kit version is available.

Input: the CLI's SessionStart JSON (`source`: startup, resume, clear, compact, fork; absent means startup). Output: {}
or {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}} (Claude Code, Codex, Gemini CLI);
for Antigravity CLI, recognised by its `conversationId`, {"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]},
its own SessionStart contract (a message persisted in the conversation, read by the model). Exit 0 always: a session is
never blocked or slowed by this script. What it announces, each once (marker ~/.ai-kit/news.json):
  - the CHANGELOG section of the version just installed (state.json `version`, CHANGELOG.md of the kit folder);
  - the entries of NEWS.md of the installed kit (never the remote's: 2.1, no remote text in the agent's context) aimed at this
    profile and team;
  - a newer version on origin/main, unless the person declined it (`ai-kit news --later`).
The remote read: at most once a day, only when the kit folder (state.json `kit_dir`) is a git clone with an origin and
`news.check_remote` is not false: `git fetch origin main` (5 s, no credential prompt), then `git show` of VERSION and
NEWS.md on origin/main; the working tree is never touched, nothing is sent, every failure is silent (doctor shows it).
The update itself is never run here: the agent proposes, the person runs `ai-kit update`. (ADR 0012)
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
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


class Run:
    def __init__(self, returncode, stdout, stderr):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def git(kit_dir, *args, timeout=FETCH_TIMEOUT):
    """git without any prompt, cut at the timeout whatever its children do: output goes to files, not pipes (a child such as
    ssh or git-remote-https holding a pipe would keep a pipe-based wait going past the timeout), the process group is
    killed on POSIX, the process tree on Windows."""
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': 'echo', 'SSH_ASKPASS': 'echo', 'GCM_INTERACTIVE': 'never'}
    env.setdefault('GIT_SSH_COMMAND', 'ssh -oBatchMode=yes')
    # The clone's own config is not trusted (0.51.1): core.fsmonitor and core.hooksPath would run a program at every session start.
    command = ['git', '-c', 'credential.interactive=false', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath='+os.devnull, '-C', kit_dir, *args]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env,
                                   **({'start_new_session': True} if os.name != 'nt' else {}))
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            raise
        out.seek(0)
        err.seek(0)
        return Run(process.returncode, out.read().decode('utf-8', 'replace'), err.read().decode('utf-8', 'replace'))


def kill_tree(process):
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        process.wait(timeout=2)
    except subprocess.SubprocessError:
        pass


def failure_category(text):
    """What a git failure was, never its text: the message may carry the remote URL, a user name or a token."""
    lower = text.lower()
    if any(word in lower for word in ('authentication', 'permission denied', 'publickey', 'could not read username', 'credential', 'access denied', 'host key')):
        return 'auth'
    if any(word in lower for word in ('could not resolve', 'unable to access', 'connection', 'network', 'timed out', 'proxy', 'unreachable')):
        return 'network'
    if any(word in lower for word in ("couldn't find remote ref", 'remote ref', 'not found', 'does not exist', 'invalid refspec')):
        return 'no ref'
    return 'git failed'


def remote_branch(kit_dir):
    """The branch read on origin: origin's default branch (origin/HEAD), else the branch this clone tracks, else main."""
    head = git(kit_dir, 'symbolic-ref', '-q', '--short', 'refs/remotes/origin/HEAD')
    if head.returncode == 0 and head.stdout.strip().startswith('origin/'):
        return head.stdout.strip()[len('origin/'):]
    upstream = git(kit_dir, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    if upstream.returncode == 0 and upstream.stdout.strip().startswith('origin/'):
        return upstream.stdout.strip()[len('origin/'):]
    return 'main'


def remote_read(kit_dir):
    """(result, detail, remote VERSION, remote NEWS.md). A read only: fetch, then show on origin's branch; the working tree
    is never touched (the fetch writes only .git/FETCH_HEAD and the remote-tracking ref). detail is a category, never git's text."""
    if not os.path.isdir(os.path.join(kit_dir, '.git')):
        return 'skipped', 'not a git clone', '', ''
    try:
        if git(kit_dir, 'remote', 'get-url', 'origin').returncode != 0:
            return 'skipped', 'no origin remote', '', ''
        branch = remote_branch(kit_dir)
        fetched = git(kit_dir, 'fetch', '--quiet', 'origin', branch)
        if fetched.returncode != 0:
            return 'failed', failure_category(fetched.stderr+fetched.stdout), '', ''
        version = git(kit_dir, 'show', 'origin/'+branch+':VERSION')
        news = git(kit_dir, 'show', 'origin/'+branch+':NEWS.md')
    except subprocess.TimeoutExpired:
        return 'failed', 'timeout', '', ''
    except (OSError, subprocess.SubprocessError):
        return 'failed', 'git failed', '', ''
    if version.returncode != 0:
        return 'failed', 'no ref', '', ''
    if not re.fullmatch(r'\d+\.\d+\.\d+', version.stdout.strip()):
        # The remote VERSION goes into the agent's context: anything but X.Y.Z is refused, with the news of that remote (0.51.1).
        return 'failed', 'invalid version', '', ''
    return 'ok', '', version.stdout.strip(), news.stdout if news.returncode == 0 else ''


def whats_new(state, marker, kit_dir, today, check_remote=True):
    """Lines to announce, and the marker updated. Pure apart from the remote read (check_remote False skips it)."""
    items, profile, team = [], str(state.get('profile') or ''), str(state.get('team') or '')
    version = str(state.get('version') or '').strip()
    announced_versions = [v for v in marker.get('announced_versions', []) if isinstance(v, str)]
    announced_news = [n for n in marker.get('announced_news', []) if isinstance(n, str)]
    if version and version not in announced_versions:
        section = changelog_section(file_text(os.path.join(kit_dir, 'CHANGELOG.md')), version) if kit_dir else ''
        items.append('Kit version '+version+' installed.'+(' What changed:\n'+indent(section) if section else ' What changed: CHANGELOG.md of the kit.'))
        announced_versions.append(version)
    news_texts = [file_text(os.path.join(kit_dir, 'NEWS.md'))] if kit_dir else []
    remote_version = ''
    last = marker.get('last_check') if isinstance(marker.get('last_check'), dict) else {}
    if check_remote and kit_dir and os.path.isdir(kit_dir) and last.get('date') != today:
        result, detail, remote_version, remote_news = remote_read(kit_dir)
        if result != 'skipped':
            marker['last_check'] = {'date': today, 'result': result, **({'detail': detail} if detail else {}), **({'remote_version': remote_version} if remote_version else {})}
        # V2 slice 6: no remote text reaches the agent's context; only the remote VERSION (checked X.Y.Z) is announced.
        del remote_news
    for text in news_texts:
        for entry in parse_news(text):
            if entry['id'] in announced_news or not aimed_at(entry, profile, team, today):
                continue
            items.append('News ('+entry['date']+') '+entry['title']+(':\n'+indent(entry['text']) if entry['text'] else '.'))
            announced_news.append(entry['id'])
    if remote_version and version_tuple(remote_version) > version_tuple(version) and remote_version != marker.get('declined_version'):
        # First: the context is cut by the end, and this item must survive a long CHANGELOG section.
        items.insert(0, 'A newer kit version is available: '+remote_version+' (installed: '+(version or 'unknown')+'). '+UPDATE_INSTRUCTION)
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
                    write_marker(marker_path, after)
                if items:
                    output = answer(payload, context_text(items))
    except Exception:
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
