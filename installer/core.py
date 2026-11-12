"""Shared building blocks of the kit, with nothing specific to a CLI: kit paths, errors, JSON, digests, managed blocks, commands."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from datetime import datetime

# Kit content: next to the code in the repo or archive, under ai_kit/kit/ when the kit is installed as a package (pipx).
_PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = _PACKAGE_DIR/'kit' if (_PACKAGE_DIR/'kit'/'VERSION').is_file() else _PACKAGE_DIR.parent
# Two roots (V2, ADR 0013). ROOT is the engine's: its code, runtime/ (hooks, friction), schemas/, its own templates,
# VERSION. The content (skills, agents, commands, context, mcp/servers.toml, the kit context template) is read from
# content_root(): the package or the clone for now, a Core source extracted at a locked tag later.
_CONTENT = [ROOT]

def content_root():
    """Where the kit's content is read from."""
    return _CONTENT[0]

@contextlib.contextmanager
def content_from(path):
    """Read the content from another tree for the duration of the block (a source extracted at a tag; tests)."""
    previous, _CONTENT[0] = _CONTENT[0], Path(path)
    try:
        yield _CONTENT[0]
    finally:
        _CONTENT[0] = previous
START = '<!-- ai-toolkit:start -->'
END = '<!-- ai-toolkit:end -->'
KIT_CONTEXT = '00_KIT.md'
USER_CONTEXT = 'USER.md'  # 3.0: the person's context (ADR 0024)
CONTEXT_NAME = re.compile(r'(?:[0-9]{2}_[A-Z0-9_]+|USER)\.md')  # the layers and the person's USER.md
EMAIL = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
# What looks like a secret, the redaction and the friction ids live in runtime/friction.py, the script /friction runs:
# the kit package loads that very file (one implementation; in the installed package it is ai_kit/kit/runtime/friction.py).
def friction_module():
    """runtime/friction.py as a module, loaded once from the kit's own files."""
    if 'friction' not in _MODULES:
        import importlib.util
        spec = importlib.util.spec_from_file_location('ai_kit_friction', ROOT/'runtime'/'friction.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES['friction'] = module
    return _MODULES['friction']


_MODULES = {}  # runtime scripts loaded once: friction.py
SECRET = friction_module().SECRET
redact = friction_module().redact
friction_id = friction_module().friction_id

class KitError(Exception):
    pass

def user_context_refusal(data):
    """Why a USER.md must not be copied elsewhere (secret, not plain UTF-8 text), or None. The value is never quoted."""
    if data.lstrip().startswith(b'{\\rtf'):
        return 'it was saved as rich text, not plain text'
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return 'it is not UTF-8 text'
    if SECRET.search(text):
        return 'it seems to contain a secret (key, token or password)'
    return None

def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise KitError('Unreadable file: ' + str(path) + ' (' + str(exc) + ')') from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise KitError(json_error(path, text, exc)) from exc
    if not isinstance(value, dict):
        raise KitError(str(path) + ': a JSON object { … } is expected at the top level.')
    return value

# Version of the layout of ~/.ai-kit/state.json this kit writes and understands. A state without the field predates it and is
# migrated; a higher or malformed one was written by another kit and is never rewritten (V2 slice 0).
STATE_SCHEMA = 2

def check_state_schema(state, path):
    """KitError when state.json comes from a kit this one cannot safely rewrite."""
    if 'schema_version' not in state:
        return
    version = state['schema_version']
    if isinstance(version, bool) or not isinstance(version, int) or version > STATE_SCHEMA:
        raise KitError(str(path) + ' has schema ' + repr(version) + ', written by a newer AI Kit; this version understands up to '
                       + str(STATE_SCHEMA) + '. Update the kit, or use the one that wrote it. Nothing was changed.')

# json's messages, said plainly, with the usual cause.
JSON_HINTS = (
    ("Expecting ',' delimiter", 'a comma is missing between two entries'),
    ('Illegal trailing comma', 'a comma is left before } or ]'),  # Python 3.13 and later
    ('Expecting property name enclosed in double quotes', 'a key must be in double quotes, or a comma is left before } or ]'),
    ('Expecting value', 'a value is missing, or a comma is left before } or ], or a text is not in double quotes'),
    ("Expecting ':' delimiter", 'a colon is missing between a key and its value'),
    ('Unterminated string', 'a text is missing its closing double quote'),
    ('Invalid control character', 'a line break or tab inside a text: write \\n or remove it'),
    ('Invalid \\escape', 'a backslash inside a text: double it (\\\\), for example in a Windows path'),
    ('Extra data', 'something follows the end of the object: an extra } or a second object'),
)

def json_error(path, text, exc):
    """One message that says where (line, column, the line itself, any secret in it redacted) and what (in plain words) is wrong in a JSON file."""
    hint = next((plain for raw, plain in JSON_HINTS if exc.msg.startswith(raw)), exc.msg)
    lines = text.splitlines() or ['']
    line = lines[min(exc.lineno, len(lines)) - 1]
    return (str(path) + ', line ' + str(exc.lineno) + ', column ' + str(exc.colno) + ': ' + hint + '.\n'
            + '    ' + redact(line.rstrip()) + '\n    ' + ' ' * max(exc.colno - 1, 0) + '^\n'
            + 'JSON allows no comments; keys starting with _ can hold explanations. A valid example: docs/configuration.md.')

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

# Manifest events (Gemini CLI's names) and their name in the CLIs that use Claude Code's: a guardrail runs before a tool,
# the whats-new hook at session start. A hook that is not a guardrail is never locked or managed by IT.
CLI_EVENTS = {'BeforeTool': 'PreToolUse'}

def cli_event(event):
    return CLI_EVENTS.get(event, event)

def is_guardrail(spec):
    return spec.get('event') == 'BeforeTool'

def hook_command(script):
    """Command a CLI runs for a kit guardrail: this Python, isolated (-I: no PYTHON* variables, no current folder on the import path)."""
    return quote_path(sys.executable)+' -I '+quote_path(script)

def split_block(text, markers, label):
    """Text before, managed block (markers included) and text after; error if the markers are damaged."""
    start, end = markers
    if start not in text and end not in text:
        return text, None, ''
    if start not in text and text.count(end) == 1:
        # Same end marker, a start marker with other words: a whole block, written by another version of the kit.
        family = start.split(' : ')[0]
        lines = text.split('\n')
        starts = [i for i, line in enumerate(lines) if line.startswith(family)]
        if len(starts) == 1 and starts[0] < next(i for i, line in enumerate(lines) if end in line):
            raise KitError('Kit block of another version of the kit in '+label+': remove it entirely, from its "'+family+'" line to its "'+end
                           +'" line, then run the command again.')
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise KitError('Kit markers damaged in '+label+': put the block back between the two ai-kit markers or remove it entirely, then ai-kit sync --offline.')
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
    """Front matter and body (installer/frontmatter.py: scalars, lists, one-level metadata table, no dependency)."""
    from .frontmatter import parse
    return parse(text)

def adopt_user_copy(p, copy, last):
    """A copy of USER.md the person edited by hand: when the file itself did not
    change since it was copied, the edit becomes the file; otherwise the file wins and the person is told. True when the
    edit was taken."""
    data = p.writes[p.user_file] if p.user_file in p.writes else p.user_file.read_bytes() if p.user_file.exists() else b''
    edited = copy.read_bytes()
    refusal = user_context_refusal(edited)
    if refusal:
        p.notices.append('[Check] '+str(copy)+' is a copy and was edited, but '+refusal+': not taken into '+str(p.user_file)
                         + '. Fix it there; the kit configuration itself is installed.')
        return False
    if digest(data) == last:
        p.writes[p.user_file] = edited
        p.notices.append('[Info] You edited '+str(copy)+', a copy: your change is now in '+str(p.user_file)+', the file to edit.')
        return True
    p.notices.append('[Check] '+str(copy)+' is a copy and was edited, while '+str(p.user_file)+' changed too: the file wins. '
                     'Your edit is kept in this update\'s backup (or left in place when the copy is no longer needed). Edit '+str(p.user_file)+'.')
    return False

def load_agent(path):
    """agents/internal/<category>/<name>.md: the agent's settings in the front matter, its instructions as the body."""
    meta, body = parse_frontmatter(Path(path).read_text(encoding='utf-8'))
    meta.pop('metadata', None)  # AI Kit's own keys (aikit-version...), never written into a CLI's agent file
    return {**meta, 'instructions': body.strip()}

DEFAULT_PREFIX = 'ai-kit-'
PREFIX = re.compile(r'([a-z0-9][a-z0-9-]{0,19})?')

def skill_prefix(overrides):
    """The prefix the kit gives its skills and commands where a name is already taken (skill_prefix, ai-kit- by default)."""
    value = overrides.get('skill_prefix', DEFAULT_PREFIX)
    if not isinstance(value, str) or not PREFIX.fullmatch(value):
        raise KitError('skill_prefix must be up to 20 lowercase letters, digits or dashes (for example "ai-kit-" or "kit-"), or "" for none.')
    return value

def taken(path, rel, old_files):
    """A file or folder that exists and that the kit did not install: a name the person already uses."""
    if not path.exists():
        return False
    if path.is_dir():
        return not any(r.startswith(rel+'/') for r in old_files)
    return rel not in old_files

def free_name(name, path_for, rel_for, old_files, prefix, what, also=()):
    """name if the kit can use it, prefix+name when one of the person's own skills or commands already has it. also: other
    (path_for, rel_for) places whose name the CLI turns into the same command."""
    if not any(taken(path(name), rel(name), old_files) for path, rel in ((path_for, rel_for), *also)):
        return name
    if not prefix:
        raise KitError('The kit '+what+' '+name+' has the name of one of your own, and skill_prefix is empty: set a prefix (for example "ai-kit-").')
    return prefix+name

def rename_references(text, mapping):
    """Rewrites, in a kit text, the references to renamed skills or commands: `name`, "name", /name, the name skill."""
    if not mapping:
        return text
    alternatives = '|'.join(re.escape(n) for n in sorted(mapping, key=len, reverse=True))
    pattern = re.compile(r'(?<![\w/.-])(`|"|/|\$)?(' + alternatives + r')(?![\w-])(?=(`|"|\s+skill\b)?)')
    def replace(match):
        opener, name, closer = match.group(1), match.group(2), match.group(3)
        if not opener and not closer:
            return match.group(0)  # a plain word: the CLI's context says how to read it
        return (opener or '') + mapping[name]
    return pattern.sub(replace, text)

def front_matter_name(text, name):
    """The name: line of a skill's front matter, whatever the line endings (a Windows checkout has CRLF)."""
    return re.sub(r'^(---\r?\n(?:.*\r?\n)*?)name:[^\r\n]*(\r?\n)', lambda m: m.group(1)+'name: '+name+m.group(2), text, count=1)

def renamed_skill_file(data, src, source, mapping, own_name):
    """A skill file as installed under a renamed scheme: references rewritten, and the SKILL.md front matter named."""
    if src.suffix != '.md' or (not mapping and own_name is None):
        return data
    text = rename_references(data.decode('utf-8'), mapping)
    if own_name is not None and src == source/'SKILL.md':
        text = front_matter_name(text, own_name)
    return text.encode('utf-8')


def kit_name(name, known):
    """The kit name behind an installed name: tdd for ai-kit-tdd, whatever prefix was used; the name itself otherwise."""
    if name in known:
        return name
    return next((k for k in sorted(known, key=len, reverse=True) if len(name) > len(k) and name.endswith(k)), name)

def renamed_notice(label, skills, commands, sigil='/'):
    """One line saying which kit skills and commands a CLI received under another name, and why."""
    parts = ['skill '+o+' as '+n for o, n in sorted(skills.items()) if o != n] + ['command '+sigil+o+' as '+sigil+n for o, n in sorted(commands.items()) if o != n]
    if not parts:
        return None
    return '[Info] '+label+': '+', '.join(parts)+' installed under another name, because one of your own already has the name.'

SKILL_READ = re.compile(r'[\\/]skills[\\/]+([A-Za-z0-9_-]+)[\\/]+SKILL\.md')

def skills_read(text, kit_skills):
    """The kit skills whose SKILL.md a tool call reads (a CLI loading a skill reads its file), by kit name."""
    names = {kit_name(m.group(1), kit_skills) for m in SKILL_READ.finditer(text)}
    return sorted(n for n in names if n in kit_skills)

LIVE_PROMPT = 'Reply with OK only.'

def network_problem(output, label, service='its service', hosts="the service's hosts"):
    """Network, proxy or certificate failure in a CLI's output: the installation is complete, access to the model is what
    fails. The fixes respect the company network: never bypass the proxy, never disable certificate checks."""
    if re.search(r'Proxy Authentication Required|status: 407|"code": 407|\b407\b', output):
        return ('The company proxy asks for authentication (HTTP 407).',
                'Ask IT how command-line tools authenticate to the proxy on your workstation; '+label+' uses the proxy set in HTTPS_PROXY.')
    if re.search(r'SELF_SIGNED_CERT_IN_CHAIN|UNABLE_TO_GET_ISSUER_CERT|UNABLE_TO_VERIFY_LEAF_SIGNATURE|self[- ]signed certificate in certificate chain'
                 r'|unable to get local issuer certificate|invalid peer certificate|UnknownIssuer|certificate verify failed', output, re.I):
        return ('The company network inspects HTTPS and '+label+' does not know the company root certificate.',
                'Ask IT for the company root certificate and how to declare it for command-line tools (NODE_EXTRA_CA_CERTS for Node.js, SSL_CERT_FILE for others). Never disable certificate checks.')
    if re.search(r'ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|fetch failed|getaddrinfo|socket hang up'
                 r'|dns error|Connection refused|error sending request|Could not resolve host', output, re.I):
        return (label+' cannot reach '+service+': no network, or the network blocks it.',
                'The kit itself is installed and works offline. Connect to the network; behind a company proxy, the CLI uses the proxy set by IT (HTTPS_PROXY); if it is still blocked, ask IT to allow '+hosts+' for '+label+'.')
    return None

def live_call(home, cli, label, command, rules, timeout=90):
    """doctor --live: one real call to the model through the CLI, from an empty folder; 0 when it answers. rules: (pattern,
    diagnosis, fix) read in order on its output, after the network causes. A failure is logged as an auth friction."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = run_timed(command, timeout, cwd=tmp, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL)
            output, code, timed_out = (proc.stdout or '')+'\n'+(proc.stderr or ''), proc.returncode, False
        except subprocess.TimeoutExpired as exc:
            def text(v):
                return v.decode('utf-8', 'replace') if isinstance(v, bytes) else (v or '')
            output, code, timed_out = text(exc.stdout)+'\n'+text(exc.stderr), None, True
        except OSError as exc:
            output, code, timed_out = str(exc), None, False
    if code == 0 and re.search(r'\bOK\b', output):
        print('[OK] Real call to the model: '+label+' answers.')
        return 0
    found = network_problem(output, label) or next(((d, f) for pattern, d, f in rules if re.search(pattern, output, re.I)), None)
    if not found:
        found = ((label+' did not answer in time.') if timed_out else (label+' did not answer as expected (code '+str(code)+').'),
                 'Start '+command[0]+' in a terminal: it says what is missing (sign-in, network); the full output of '+' '.join(command[:2])+' … helps IT.')
    print('[Check] '+found[0])
    print('        Fix: '+found[1])
    record_auto_friction(home, found[0], cli)
    return 1

COMMANDS_DIR = 'commands'

def load_commands():
    """Kit commands, from the pivot source commands/<name>.md: front matter (name, description, category, stage, skills, artifact, order) and prompt; each adapter derives its own form."""
    commands = []
    for path in sorted((content_root()/COMMANDS_DIR).glob('*.md')):
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
        command = {'name': name, 'description': meta['description'], 'category': meta['category'], 'skills': skills, 'prompt': body.strip() + '\n', 'order': int(meta.get('order', 1000)),
                   'default': str(meta.get('default', 'true')).lower() != 'false'}  # in the Core default selection unless default: false
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

FIXED_FRICTIONS = re.compile(r'\bfrictions?:\s*([0-9a-f]{6}(?:\s*,\s*[0-9a-f]{6})*)', re.I)

def fixed_frictions(changelog):
    """{friction id: version} for the ids a CHANGELOG cites as "(frictions: a1b2c3, d4e5f6)" under a "## <version>" heading."""
    fixed, version = {}, None
    for line in changelog.splitlines():
        if line.startswith('## '):
            version = (line[3:].split() or [''])[0]  # '## 4.1.0 (2026-11-10)'
            continue
        for match in FIXED_FRICTIONS.finditer(line):
            for fid in re.split(r'\s*,\s*', match.group(1).lower()):
                fixed.setdefault(fid, version)
    return fixed

def record_auto_friction(home, diagnostic, cli='unknown'):
    """A failure seen by doctor --live becomes an `auth` friction, logged locally without asking (same format as /friction:
    the same function writes it)."""
    if not (home/'.ai-kit/state.json').is_file():
        return
    try:
        friction_module().record('auth', diagnostic, 'doctor', cli, source='doctor', home=str(home))
    except (OSError, ValueError):
        pass

