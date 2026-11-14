#!/usr/bin/env python3
"""Kit hook (after a tool call; whats-new calls it at session start): reports a change to what the kit installed, the same
way on every system, whatever made it (ADR 0030).

Compared with state.json: the files the kit owns (`files`; size, times and inode first, a digest when one of them moved;
always a digest at session start), the kit's part of the five files it shares with a CLI (`blocks`; judged by the adapter's
own check when the file moved), and the settings of the kit folder's .git/config that decide where the next update comes
from or what git runs (`kit_git`). A change is reported once per set of changes, to the agent (additionalContext) and to the
person (systemMessage), with the command that restores it; never a decision, which would replace the tool's result. It
writes only its marker, ~/.ai-kit/integrity.json, when something moved, and sends nothing.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

MARKER = 'integrity.json'
RESTORE = 'ai-kit sync --offline'
SAFE_NAME = re.compile(r'[A-Za-z0-9._/@-]{1,160}')  # a name shown in a message: nothing else reaches the agent or the person
MAX_BYTES = 32 * 1024 * 1024  # a file the kit installed is far smaller: a bigger one counts as changed, unread
SHOWN = 10
# The files the kit shares with a CLI whose part an adapter judges (changed_blocks); others are not looked at.
SHARED = ('.claude/CLAUDE.md', '.claude/settings.json', '.codex/AGENTS.md', '.codex/config.toml', '.gemini/settings.json')
# The settings of a clone's .git/config that decide where a fetch goes or what git runs (the kit runs git without hooks and
# without global configuration): a branch's tracking or a pushed tag changes nothing here.
GIT_KEYS = re.compile(r'(remote\.[^=]*\.(url|pushurl)|url\.[^=]*\.(insteadof|pushinsteadof)|core\.(fsmonitor|hookspath|sshcommand|askpass|gitproxy)'
                      r'|include\.path|includeif\.[^=]*\.path|credential(\.[^=]*)?\.helper)')


def read_state(path):
    """(state, problem): the parsed state.json, or a problem when it exists and cannot be read as the kit writes it."""
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding='utf-8') as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None, 'unreadable'
    if not isinstance(state, dict) or not isinstance(state.get('files', {}), dict) or not isinstance(state.get('blocks', {}), dict):
        return None, 'unreadable'
    return state, None


def read_marker(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def safe_rel(rel):
    """True for a relative name under the home folder the kit could have written: no absolute path, no .., no odd characters."""
    return isinstance(rel, str) and bool(SAFE_NAME.fullmatch(rel)) and not rel.startswith('/') and '..' not in rel.split('/')


def stamp(path):
    """[size, mtime, ctime, inode] of a regular file, 'missing' when there is none, 'not a file' for anything else."""
    try:
        info = os.stat(path)
    except (OSError, ValueError):
        return 'missing'
    if not stat.S_ISREG(info.st_mode):
        return 'not a file'
    return [info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino]


def file_digest(path):
    """sha256 of a regular file, read by blocks; 'too large' over MAX_BYTES; None when it cannot be read."""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return 'too large'
        sha = hashlib.sha256()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                sha.update(chunk)
        return sha.hexdigest()
    except OSError:
        return None


def git_dir(folder):
    """The folder that holds a clone's config: .git, or, for a worktree, the common folder its .git file leads to."""
    try:
        dot_git = os.path.join(folder, '.git')
        if os.path.isdir(dot_git):
            return dot_git
        with open(dot_git, encoding='utf-8') as handle:
            line = handle.read(4096).strip()
        if not line.startswith('gitdir:'):
            return None
        worktree = os.path.normpath(os.path.join(folder, line[len('gitdir:'):].strip()))
        try:
            with open(os.path.join(worktree, 'commondir'), encoding='utf-8') as handle:
                return os.path.normpath(os.path.join(worktree, handle.read(4096).strip()))
        except OSError:
            return worktree
    except (OSError, ValueError, TypeError):
        return None


def kit_git_digests(folder):
    """{setting: digest of its value} for the settings of a kit clone's .git/config that GIT_KEYS names; {} when the folder is
    not a clone (None). Values are kept as digests: a remote URL can hold a token."""
    root = git_dir(folder) if folder else None
    if not root:
        return None
    found = {}
    try:
        with open(os.path.join(root, 'config'), encoding='utf-8', errors='replace') as handle:
            lines = handle.read(1024 * 1024).splitlines()
    except (OSError, TypeError):
        return found
    section = ''
    for raw in lines:
        line = raw.strip()
        header = re.fullmatch(r'\[\s*([A-Za-z0-9.-]+)(?:\s+"(.*)")?\s*\]', line)
        if header:
            section = header.group(1).lower() + ('.' + header.group(2) if header.group(2) is not None else '')
            continue
        if not line or line.startswith(('#', ';')) or not section:
            continue
        key, _, value = line.partition('=')
        name = section + '.' + key.strip().lower()
        if GIT_KEYS.fullmatch(name):
            digest = hashlib.sha256(value.strip().encode('utf-8')).hexdigest()
            found[name] = found[name] + '+' + digest if name in found else digest
    return found


def owned_changes(home, state, stamps, full):
    """(changes as (name, current digest), fresh stamps) for the files the kit owns; full ignores the stamps (session start)."""
    changes, fresh = [], {}
    for rel, expected in sorted((state.get('files') or {}).items()):
        if not safe_rel(rel):
            continue
        path = os.path.join(home, rel)
        now = stamp(path)
        if not isinstance(now, list):
            changes.append((rel, now))
            continue
        known = stamps.get(rel)
        reuse = not full and isinstance(known, list) and len(known) == 5 and known[:4] == now
        current = known[4] if reuse else file_digest(path)
        fresh[rel] = now + [current]
        if current != expected:
            changes.append((rel, current))
    return changes, fresh


def git_changes(state):
    """Changes to the settings of the kit clone's .git/config that GIT_KEYS names, as (name, digest)."""
    recorded = state.get('kit_git')
    if not isinstance(recorded, dict):
        return []  # not recorded: the kit folder is not a clone
    folder = state.get('kit_dir')
    current = kit_git_digests(folder) if isinstance(folder, str) else None
    if current is None:
        return [('kit folder .git/config', 'not found')]
    names = sorted(set(recorded) | set(current))
    return [('kit folder .git/config ' + n, current.get(n, 'removed')) for n in names if recorded.get(n) != current.get(n)]


def adapters():
    """The kit's adapters: from the kit's package (the private Python the hooks run with), else from the kit folder this script
    sits in (a clone); never from a path read in state.json. [] when neither loads."""
    try:
        from ai_kit.adapters import claude, codex, gemini
        return [claude, codex, gemini]
    except Exception:
        pass
    root = Path(__file__).resolve().parents[2]
    if not (root/'installer'/'adapters').is_dir():
        return []
    try:
        sys.path.insert(0, str(root))
        from installer.adapters import claude, codex, gemini
        return [claude, codex, gemini]
    except Exception:
        return []
    finally:
        if sys.path and sys.path[0] == str(root):
            sys.path.pop(0)


def shared_changes(home, state, marker, full):
    """(changes as (name, current digest), stamps): the kit's part of the files it shares with a CLI, judged again when one
    of those files moved since the last check, and always at session start."""
    targets = state.get('targets') if isinstance(state.get('targets'), list) else []
    watched = [r for r in SHARED if r in (state.get('blocks') or {}) or (r == '.gemini/settings.json' and 'gemini' in targets)]
    now = {rel: stamp(os.path.join(home, rel)) for rel in watched}
    cached = marker.get('shared_changed')
    if not full and now == marker.get('shared_stamps') and isinstance(cached, list):
        return [tuple(c) for c in cached if isinstance(c, list) and len(c) == 2], now
    changed = set()
    for module in adapters():
        try:
            changed.update(r for r in module.changed_blocks(Path(home), state) if r in watched)
        except Exception:
            continue
    return [(rel, file_digest(os.path.join(home, rel))) for rel in sorted(changed)], now


def shown(names):
    """The names as a message may show them: simple characters only, at most SHOWN."""
    safe = ['~/' + n if not n.startswith('kit folder') else n for n in names if SAFE_NAME.fullmatch(n.replace(' ', '-'))]
    listed = ', '.join(safe[:SHOWN])
    hidden = len(names) - min(len(safe), SHOWN)
    return listed + (' and ' + str(hidden) + ' more' if hidden else '')


def check(home, state, marker, full=False):
    """(text for the agent, text for the person, marker updated): texts only for a set of changes not announced yet."""
    owned, fresh = owned_changes(home, state, marker.get('stamps') or {}, full)
    shared, shared_now = shared_changes(home, state, marker, full)
    changes = sorted(set(owned) | set(shared) | set(git_changes(state)))
    marker = {**marker, 'stamps': fresh, 'shared_stamps': shared_now, 'shared_changed': [list(c) for c in shared]}
    key = hashlib.sha256(json.dumps(changes).encode('utf-8')).hexdigest() if changes else ''
    announced, marker['announced'] = marker.get('announced'), key
    if not changes or key == announced:
        return None, None, marker
    listed = shown([name for name, _ in changes])
    return message(listed), person_message(listed), marker


def message(listed):
    return ('AI Kit integrity: what the kit installed was changed outside the kit: ' + listed + '. Say it to the person in the first '
            'line of your reply. Do not change it back yourself; the person restores it with: ' + RESTORE)


def person_message(listed):
    return 'AI Kit: changed outside the kit: ' + listed + '. To restore: ' + RESTORE


def write_marker(path, data):
    """Writes the marker through a temporary file of its own (never a fixed name another hook could race or a link could
    redirect), readable by its owner only."""
    folder = os.path.dirname(path)
    handle, temporary = tempfile.mkstemp(prefix='.integrity-', dir=folder)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as out:
            json.dump(data, out)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def checked(home, full=False):
    """(agent text, person text) of a new set of changes, the marker written when it moved; (None, None) otherwise."""
    kit = os.path.join(home, '.ai-kit')
    state, problem = read_state(os.path.join(kit, 'state.json'))
    path = os.path.join(kit, MARKER)
    before = read_marker(path)
    if problem:
        key = 'state:' + problem
        if before.get('announced') == key:
            return None, None
        write_marker(path, {**before, 'announced': key})
        return message('~/.ai-kit/state.json (' + problem + ')'), person_message('~/.ai-kit/state.json (' + problem + ')')
    if state is None:
        return None, None
    agent, person, after = check(home, state, before, full)
    if after != before:
        try:
            write_marker(path, after)
        except OSError:
            pass
    return agent, person


def answer(payload, agent, person):
    """The answer in the form of the CLI that asked, after a tool call."""
    if not agent:
        return {}
    event = str(payload.get('hook_event_name') or '')
    output = {'additionalContext': agent}
    if event in ('PostToolUse', ''):  # Claude Code and Codex name the event in their output; Gemini CLI (AfterTool) does not
        output = {'hookEventName': 'PostToolUse', **output}
    return {'systemMessage': person, 'hookSpecificOutput': output}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        agent, person = checked(os.path.expanduser('~'))
        output = answer(payload if isinstance(payload, dict) else {}, agent, person)
    except Exception:
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
