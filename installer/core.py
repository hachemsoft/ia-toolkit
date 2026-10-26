"""Shared building blocks of the kit, with nothing specific to a CLI: kit paths, errors, JSON, digests, managed blocks, commands."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone

# Kit content: next to the code in the repo or archive, under ai_kit/kit/ when the kit is installed as a package (pipx).
_PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = _PACKAGE_DIR/'kit' if (_PACKAGE_DIR/'kit'/'VERSION').is_file() else _PACKAGE_DIR.parent
START = '<!-- ai-toolkit:start -->'
END = '<!-- ai-toolkit:end -->'
KIT_CONTEXT = '00_KIT.md'
USER_CONTEXT = '30_USER.md'
CONTEXT_NAME = re.compile(r'[0-9]{2}_[A-Z0-9_]+\.md')
EMAIL = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')

class KitError(Exception):
    pass

def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as exc:
        raise KitError('Unreadable JSON: ' + str(path)) from exc
    if not isinstance(value, dict):
        raise KitError('JSON object expected: ' + str(path))
    return value

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe_id(name):
    if not isinstance(name, str) or not re.fullmatch('[a-z0-9][a-z0-9-]*', name):
        raise KitError('Invalid identifier: ' + repr(name))
    return name

def inside(base, relative):
    path = base / relative
    if not path.resolve().is_relative_to(base.resolve()):
        raise KitError('Path outside the allowed scope: ' + str(path))
    return path

PROJECT_ID = r'[a-z][a-z0-9-]{4,28}[a-z0-9]'

def merge_defaults(current, defaults):
    for key, value in defaults.items():
        if key not in current:
            current[key] = value
        elif isinstance(value, dict):
            if not isinstance(current[key], dict):
                raise KitError('Incompatible setting: ' + key)
            merge_defaults(current[key], value)
    return current

def quote_path(path):
    return '"'+str(path)+'"' if os.name == 'nt' else shlex.quote(str(path))

def hook_command(script):
    """Command a CLI runs for a kit guardrail: this Python, isolated (-I: no PYTHON* variables, no current folder on the import path)."""
    return quote_path(sys.executable)+' -I '+quote_path(script)

def split_block(text, markers, label):
    """Text before, managed block (markers included) and text after; error if the markers are damaged."""
    start, end = markers
    if start not in text and end not in text:
        return text, None, ''
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise KitError('Kit markers damaged in '+label+': put the block back between the two ai-kit markers or remove it entirely, then update.')
    before, rest = text.split(start, 1)
    block, after = rest.split(end, 1)
    return before, start+block+end, after

def place_block(text, block, position):
    """Inserts the managed block (or removes it if block is None), leaving the rest of the file unchanged."""
    rest = text.strip('\n')
    if block is None:
        return rest+'\n' if rest else ''
    if not rest:
        return block+'\n'
    return block+'\n\n'+rest+'\n' if position == 'top' else rest+'\n\n'+block+'\n'

def parse_frontmatter(text):
    """Minimal YAML front matter (key: value, lists [a, b] or JSON quotes) and body, without dependencies."""
    match = re.match(r'---\n(.*?)\n---\n?(.*)$', text, re.S)
    if not match:
        raise KitError('Front matter --- expected.')
    meta = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition(':')
        if not sep or not re.fullmatch(r'[a-z_]+', key.strip()):
            raise KitError('Unreadable front matter line: ' + line)
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            meta[key.strip()] = [v.strip().strip('"\'') for v in value[1:-1].split(',') if v.strip()]
        elif value.startswith('"'):
            meta[key.strip()] = json.loads(value)
        elif re.fullmatch(r'-?\d+', value):
            meta[key.strip()] = int(value)
        else:
            meta[key.strip()] = value.strip("'")
    return meta, match.group(2)

COMMANDS_DIR = 'commands'

def load_commands():
    """Kit commands, from the pivot source commands/<name>.md: front matter (name, description, category, stage, skills, artifact, order) and prompt; each adapter derives its own form."""
    commands = []
    for path in sorted((ROOT/COMMANDS_DIR).glob('*.md')):
        if path.name.upper() == 'README.MD':
            continue
        meta, body = parse_frontmatter(path.read_text(encoding='utf-8'))
        name = safe_id(str(meta.get('name', '')))
        if name != path.stem:
            raise KitError('Command ' + path.name + ': name must be ' + path.stem)
        if not isinstance(meta.get('description'), str) or not meta['description'].strip():
            raise KitError('Command ' + name + ': description missing.')
        if meta.get('category') not in ('workflow', 'tool'):
            raise KitError('Command ' + name + ': category must be workflow or tool.')
        skills = meta.get('skills', [])
        if not isinstance(skills, list) or not all(isinstance(x, str) for x in skills):
            raise KitError('Command ' + name + ': skills must be a list.')
        if '"""' in body:
            raise KitError('Command ' + name + ': the prompt cannot contain three double quotes.')
        command = {'name': name, 'description': meta['description'], 'category': meta['category'], 'skills': skills, 'prompt': body.strip() + '\n', 'order': int(meta.get('order', 1000))}
        for key in ('stage', 'artifact'):
            if meta.get(key):
                command[key] = meta[key]
        commands.append(command)
    commands.sort(key=lambda c: (c['order'], c['name']))
    return commands

def command_skill_text(command):
    """Command skill, for CLIs whose commands are skills: same name as the command, prompt without {{args}}."""
    body = command['prompt'].replace('{{args}}', 'the text the user typed after the command, or the current conversation')
    description = 'Kit command /'+command['name']+'. '+command['description']+'. Use when the user types /'+command['name']+' or explicitly asks for this step; do not activate on your own for unrelated requests.'
    return '---\nname: '+command['name']+'\ndescription: '+json.dumps(description)+'\n---\n\n'+body.strip()+'\n'

def run_timed(command, timeout, **kwargs):
    """subprocess.run with a timeout that stops the whole process group: a CLI that relaunches itself
    (node --max-old-space-size) would leave the child running as an orphan after a plain kill of the parent."""
    popen_kwargs = dict(kwargs)
    if os.name == 'nt':
        popen_kwargs['creationflags'] = popen_kwargs.get('creationflags', 0) | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs['start_new_session'] = True
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        else:
            import signal
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
        out, err = proc.communicate()
        raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)

def _ts(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
    except ValueError:
        return 0

def friction_id(ts, text):
    """Same id as runtime/friction.py: 6 hex characters from the date and the sentence (older lines get it when read)."""
    return hashlib.sha256((str(ts) + '|' + str(text)).encode('utf-8')).hexdigest()[:6]

FIXED_FRICTIONS = re.compile(r'\bfrictions?:\s*([0-9a-f]{6}(?:\s*,\s*[0-9a-f]{6})*)', re.I)

def fixed_frictions(changelog):
    """{friction id: version} for the ids a CHANGELOG cites as "(frictions: a1b2c3, d4e5f6)" under a "## <version>" heading."""
    fixed, version = {}, None
    for line in changelog.splitlines():
        if line.startswith('## '):
            version = line[3:].strip()
            continue
        for match in FIXED_FRICTIONS.finditer(line):
            for fid in re.split(r'\s*,\s*', match.group(1).lower()):
                fixed.setdefault(fid, version)
    return fixed

def record_auto_friction(home, diagnostic, cli='unknown'):
    """A failure seen by doctor --live becomes an `auth` friction, logged locally without asking (same format as /friction)."""
    if not (home/'.ai-kit/state.json').is_file():
        return
    try:
        state = read_json(home/'.ai-kit/state.json')
        system = {'darwin': 'mac', 'win32': 'windows'}.get(sys.platform, sys.platform)
        entry = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'category': 'auth', 'command': 'doctor',
                 'text': ' '.join(str(diagnostic).split())[:300], 'cli': cli, 'source': 'doctor',
                 'os': system, 'kit': str(state.get('version', '')), 'profile': str(state.get('profile', ''))}
        entry['id'] = friction_id(entry['ts'], entry['text'])
        with open(home/'.ai-kit/frictions.jsonl', 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except (OSError, KitError, ValueError):
        pass

