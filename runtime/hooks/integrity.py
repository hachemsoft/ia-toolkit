#!/usr/bin/env python3
"""Kit hook (after a tool call; whats-new calls it at session start): reports a change to what the kit installed, the same
way on every system, whatever made it (ADR 0030).

Compared with state.json: the files the kit owns (`files`; size, times and inode first, a digest when one of them moved;
always a digest at session start), the kit's part of the six files it shares with a CLI (`blocks`; judged by the adapter's
own check when the file moved), and the settings of the kit folder's .git/config that decide where the next update comes
from or what git runs (`kit_git`). A change is reported once per set of changes, to the agent (additionalContext) and to the
person (systemMessage), with the command that restores it; never a decision, which would replace the tool's result. It
writes only its marker, ~/.ai-kit/integrity.json, when something moved, and sends nothing.

After a tool that only reads (READ_ONLY_TOOLS), it answers at once without looking at the disk: such a tool changed
nothing, and the full check still runs at session start and after any tool that writes, runs a command or is not known.
"""
import json
import os
import re
import stat
import sys
# hashlib, tempfile and pathlib are loaded where they are used: a call that finds nothing moved needs none of them, and they
# are most of what this script costs after the start of Python (they bring shutil, bz2, lzma and random with them).

MARKER = 'integrity.json'
SELF = '.ai-kit/hooks/integrity.py'  # the check itself, recorded by every installation
RESTORE = 'ai-kit sync --offline --restore'
GIT_CHECK = 'git -C <kit folder> remote -v'  # sync does not manage the kit folder's git configuration
SAFE_NAME = re.compile(r'[A-Za-z0-9._/@-]{1,160}')  # a name shown in a message: nothing else reaches the agent or the person
MAX_BYTES = 32 * 1024 * 1024  # a file the kit installed is far smaller: a bigger one counts as changed, unread
SHOWN = 10
# The files the kit shares with a CLI whose part an adapter judges (changed_blocks); others are not looked at.
SHARED = ('.claude/CLAUDE.md', '.claude/settings.json', '.claude.json', '.codex/AGENTS.md', '.codex/config.toml', '.gemini/settings.json')
# The settings of a clone's .git/config that decide where a fetch goes or what git runs (the kit runs git without hooks and
# without global configuration): a branch's tracking or a pushed tag changes nothing here.
# Tools that only read, by the names the CLIs give them (Claude Code; Gemini CLI; Antigravity CLI). Anything else, an MCP
# tool or a name not listed, gets the full check.
READ_ONLY_TOOLS = frozenset(('Read', 'Grep', 'Glob', 'read_file', 'grep_search', 'list_dir', 'find_by_name', 'view_file'))
GIT_KEYS = re.compile(r'(remote\.[^=]*\.(url|pushurl)|url\.[^=]*\.(insteadof|pushinsteadof)|core\.(fsmonitor|hookspath|sshcommand|askpass|gitproxy)'
                      r'|include\.path|includeif\.[^=]*\.path|credential(\.[^=]*)?\.helper)')


def use_utf8():
    """The CLIs send and read UTF-8, whatever the console's code page (Windows: cp1252)."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass


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


def stamp(path, follow=False):
    """[size, mtime, ctime, inode] of a regular file, 'missing' when there is none, 'not a file' for anything else. A file
    the kit owns is never a link: one put in its place is 'not a file', even to the same content today. follow: a file the
    person shares with the kit (their settings, the kit folder's git configuration) may be a link to their own."""
    try:
        info = os.stat(path) if follow else os.lstat(path)
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
        import hashlib
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
    import hashlib
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
    """(changes as (name, current digest), failures as (name, reason), fresh stamps) for the files the kit owns; full
    ignores the stamps (session start). A file that cannot be read is a check that failed, not a change."""
    changes, failed, fresh = [], [], {}
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
        if current is None:
            failed.append((rel, 'unreadable'))
            continue
        fresh[rel] = now + [current]
        if current != expected:
            changes.append((rel, current))
    return changes, failed, fresh


def git_changes(state, cache=None, full=False):
    """(changes, cache): the changes to the settings of the kit clone's .git/config that GIT_KEYS names, as (name, digest),
    and what the marker keeps to answer the next call without reading the file again: its path and stamp, what state.json
    records, the changes found. The file is read again when it moved, when the record changed, and at session start (full)."""
    recorded = state.get('kit_git')
    if not isinstance(recorded, dict):
        return [], None  # not recorded: the kit folder is not a clone
    folder = state.get('kit_dir')
    key = json.dumps([folder, recorded], sort_keys=True, default=str)  # recorded holds digests, never a value
    if (not full and isinstance(cache, dict) and cache.get('key') == key and isinstance(cache.get('path'), str)
            and isinstance(cache.get('stamp'), list) and isinstance(cache.get('changes'), list) and stamp(cache['path'], follow=True) == cache['stamp']):
        return pairs(cache['changes']), cache
    root = git_dir(folder) if isinstance(folder, str) else None
    path = os.path.join(root, 'config') if root else None
    before = stamp(path, follow=True) if path else None  # taken first: a change during the read shows at the next call
    current = kit_git_digests(folder) if isinstance(folder, str) else None
    if current is None:
        return [('kit folder .git/config', 'not found')], None
    names = sorted(set(recorded) | set(current))
    changes = [('kit folder .git/config ' + n, current.get(n, 'removed')) for n in names if recorded.get(n) != current.get(n)]
    return changes, {'key': key, 'path': path, 'stamp': before, 'changes': [list(c) for c in changes]}


def adapters():
    """The kit's adapters: from the kit's package (the private Python the hooks run with), else from the kit folder this script
    sits in (a clone); never from a path read in state.json. [] when neither loads."""
    try:
        from ai_kit.adapters import claude, codex, gemini
        return [claude, codex, gemini]
    except Exception:
        pass
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    if not os.path.isdir(os.path.join(root, 'installer', 'adapters')):
        return []
    try:
        sys.path.insert(0, root)
        from installer.adapters import claude, codex, gemini
        return [claude, codex, gemini]
    except Exception:
        return []
    finally:
        if sys.path and sys.path[0] == root:
            sys.path.pop(0)


def pairs(items):
    """(name, value) pairs kept in the marker as lists."""
    return [tuple(c) for c in items if isinstance(c, list) and len(c) == 2]


def shared_changes(home, state, marker, full):
    """(changes as (name, current digest), failures as (name, reason), stamps): the kit's part of the files it shares with
    a CLI, judged again when one of those files moved since the last check, and always at session start. When the adapters
    cannot load or their check fails, the files to judge are a check that failed, never taken for unchanged."""
    targets = state.get('targets') if isinstance(state.get('targets'), list) else []
    watched = [r for r in SHARED if r in (state.get('blocks') or {}) or (r == '.gemini/settings.json' and 'gemini' in targets)]
    now = {rel: stamp(os.path.join(home, rel), follow=True) for rel in watched}
    cached, cached_failed = marker.get('shared_changed'), marker.get('shared_failed', [])
    if not full and now == marker.get('shared_stamps') and isinstance(cached, list) and isinstance(cached_failed, list):
        return pairs(cached), pairs(cached_failed), now
    if not watched:
        return [], [], now
    modules = adapters()
    if not modules:
        return [], [(rel, 'kit adapters not loadable') for rel in watched], now
    from pathlib import Path
    changed, failed = set(), []
    for module in modules:
        try:
            changed.update(r for r in module.changed_blocks(Path(home), state) if r in watched)
        except Exception:
            failed = [(rel, 'check failed') for rel in watched]
    return [(rel, file_digest(os.path.join(home, rel))) for rel in sorted(changed)], failed, now


def shown(names):
    """The names as a message may show them: simple characters only, at most SHOWN."""
    safe = ['~/' + n if not n.startswith('kit folder') else n for n in names if SAFE_NAME.fullmatch(n.replace(' ', '-'))]
    listed = ', '.join(safe[:SHOWN])
    hidden = len(names) - min(len(safe), SHOWN)
    return listed + (' and ' + str(hidden) + ' more' if hidden else '')


def check(home, state, marker, full=False):
    """(text for the agent, text for the person, marker updated): texts only for a set of changes not announced yet."""
    owned, owned_failed, fresh = owned_changes(home, state, marker.get('stamps') or {}, full)
    shared, shared_failed, shared_now = shared_changes(home, state, marker, full)
    git, git_cache = git_changes(state, marker.get('git'), full)
    changes = sorted(set(owned) | set(shared) | set(git))
    failed = sorted(set(owned_failed) | set(shared_failed))
    marker = {**marker, 'stamps': fresh, 'shared_stamps': shared_now, 'shared_changed': [list(c) for c in shared],
              'shared_failed': [list(c) for c in shared_failed], 'git': git_cache}
    return announce(marker, changes, failed)


def announce(marker, changes, failed):
    """Healthy (nothing), drift (changes) or check failed (failures), said once per set: (agent, person, marker)."""
    key = ''
    if changes or failed:
        import hashlib
        key = hashlib.sha256(json.dumps([changes, failed]).encode('utf-8')).hexdigest()
    announced, marker['announced'] = marker.get('announced'), key
    if not key or key == announced:
        return None, None, marker
    agent, person = [], []
    files = [c for c in changes if not c[0].startswith('kit folder')]
    git = [c for c in changes if c[0].startswith('kit folder')]
    if files:
        listed = shown([name for name, _ in files])
        agent.append(message(listed))
        person.append(person_message(listed))
    if git:  # sync does not manage the kit folder's git configuration: the person checks where the next update comes from
        listed = shown([name for name, _ in git])
        agent.append('AI Kit integrity: the kit folder\'s git settings changed: ' + listed + '. Say it to the person; the next update could '
                     'come from elsewhere. They check the remotes with: ' + GIT_CHECK)
        person.append('AI Kit: the kit folder\'s git settings changed: ' + listed + '. Check its remotes: ' + GIT_CHECK)
    if failed:
        listed = shown([name for name, _ in failed])
        reasons = sorted({reason for _, reason in failed})
        agent.append('AI Kit integrity: could not check ' + listed + ' (' + ', '.join(reasons) + '). Say it to the person; they run '
                     'ai-kit doctor, then, if it reports a problem: ' + RESTORE)
        person.append('AI Kit: could not check ' + listed + ' (' + ', '.join(reasons) + '). Run ai-kit doctor; to restore: ' + RESTORE)
    return ' '.join(agent), ' '.join(person), marker


def message(listed):
    return ('AI Kit integrity: what the kit installed was changed outside the kit: ' + listed + '. Say it to the person in the first '
            'line of your reply. Do not change it back yourself; the person restores it with: ' + RESTORE)


def person_message(listed):
    return 'AI Kit: changed outside the kit: ' + listed + '. To restore: ' + RESTORE


def write_marker(path, data):
    """Writes the marker through a temporary file of its own (never a fixed name another hook could race or a link could
    redirect), readable by its owner only. A kit folder that is gone or cannot be written to keeps no marker: the change is
    then announced at each call, never hidden."""
    import tempfile
    temporary = None
    try:
        handle, temporary = tempfile.mkstemp(prefix='.integrity-', dir=os.path.dirname(path))
        with os.fdopen(handle, 'w', encoding='utf-8') as out:
            json.dump(data, out)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except OSError:
        try:
            if temporary:
                os.unlink(temporary)
        except OSError:
            pass


def checked(home, full=False):
    """(agent text, person text) of a new set of changes, the marker written when it moved; (None, None) otherwise."""
    kit = os.path.join(home, '.ai-kit')
    state, problem = read_state(os.path.join(kit, 'state.json'))
    path = os.path.join(kit, MARKER)
    before = read_marker(path)
    installed = os.path.dirname(os.path.realpath(__file__)) == os.path.realpath(os.path.join(kit, 'hooks'))
    if state is None and installed and not problem:
        problem = 'missing'  # this copy was installed by the kit: its state cannot be gone
    if state is not None and installed and SELF not in (state.get('files') or {}):
        # An installation records the check itself; an interrupted update or a state cut short does not.
        problem = 'incomplete: no installed files' if not state.get('files') else 'incomplete: the check is not recorded'
    if problem:
        agent, person, after = announce(dict(before), [], [('.ai-kit/state.json', problem)])
        if after != before:
            write_marker(path, after)
        return agent, person
    if state is None:
        return None, None  # never installed here: nothing to check
    agent, person, after = check(home, state, before, full)
    if after != before:
        write_marker(path, after)
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


def tool_name(payload):
    """The tool that just ran, by the name its CLI gives it (tool_name; Antigravity: toolCall.name); '' when not said."""
    call = payload.get('toolCall') if isinstance(payload.get('toolCall'), dict) else {}
    name = payload.get('tool_name') or call.get('name') or ''
    return name if isinstance(name, str) else ''


def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    payload = payload if isinstance(payload, dict) else {}
    if tool_name(payload) in READ_ONLY_TOOLS:
        print('{}')  # a tool that only reads changed nothing: no disk check
        return
    try:
        agent, person = checked(os.path.expanduser('~'))
        output = answer(payload, agent, person)
    except Exception:
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
