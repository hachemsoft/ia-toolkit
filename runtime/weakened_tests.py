#!/usr/bin/env python3
"""Facts about the tests a change deletes, moves, disables or relaxes, for the review to judge (ADR 0027).

/review runs it before its passes (code-review skill); it lists, it never judges and never blocks. Read-only: it runs git
in read mode only (rev-parse, merge-base, diff, show, ls-files), with the repository's hooks, fsmonitor, external diff and
textconv neutralized, reads files, writes nothing, opens no connection, calls no model. Standard library only.

Usage: python3 weakened_tests.py [--base REF] [--repo PATH]
Scope: the same as the review: the branch's commits since the merge base with REF (default origin/HEAD, else main, else
master), the staged and unstaged changes, and the new untracked files.
Output (stdout, JSON): {"schema": 1, "base", "merge_base", "error", "facts": [...], "families_seen", "files_unrecognized",
"files_unreadable", "truncated"}. Exit code 0 when the output is valid (with or without facts), 2 when the repository
cannot be read. A file it cannot read is listed in files_unreadable and gives no fact: never a false one.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = 1
MAX_FACTS = 200
MAX_COMPARED = 1_000_000  # bytes: a bigger added file is never compared to find a moved test file
TEST_DIRS = {'test', 'tests', '__tests__', 'spec'}
DBT_RESOURCE_PATHS = {'model-paths': ['models'], 'seed-paths': ['seeds'], 'snapshot-paths': ['snapshots'],
                      'analysis-paths': ['analyses'], 'macro-paths': ['macros'], 'test-paths': ['tests']}
DBT_CONFIG = ('severity', 'error_if', 'warn_if', 'enabled', 'where', 'limit', 'fail_calc', 'store_failures')
LINE_MAX = 200


class RepoError(Exception):
    pass


class YamlError(Exception):
    pass


# --- Git, read-only ----------------------------------------------------------------------------------------------------

def git(repo, *args, check=True):
    """stdout of a read-only git command; the repository's hooks and fsmonitor are neutralized, no optional lock taken."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    proc = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath='+os.devnull, '-C', str(repo), *args],
                          capture_output=True, env=env, timeout=60)
    if check and proc.returncode != 0:
        raise RepoError(proc.stderr.decode('utf-8', 'replace').strip() or 'git '+args[0]+' failed')
    return proc.stdout.decode('utf-8', 'replace') if proc.returncode == 0 else None


def resolve_base(repo, base):
    if base:
        if git(repo, 'rev-parse', '--verify', '--quiet', base+'^{commit}', check=False) is None:
            raise RepoError('base not found: '+base)
        return base
    remote = git(repo, 'rev-parse', '--abbrev-ref', 'origin/HEAD', check=False)
    if remote and remote.strip() != 'origin/HEAD':
        return remote.strip()
    for name in ('main', 'master'):
        if git(repo, 'rev-parse', '--verify', '--quiet', name+'^{commit}', check=False) is not None:
            return name
    raise RepoError('no base: pass --base (no origin/HEAD, main or master)')


def changes(repo, merge_base):
    """[(status, old_path, new_path)] from the merge base to the working tree, untracked files included as added."""
    fields = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '-M', '--name-status', '-z', merge_base).split('\0')
    found, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        if status in 'RC':
            found.append((status, fields[i+1], fields[i+2]))
            i += 3
        else:
            found.append((status, fields[i+1], fields[i+1]))
            i += 2
    for path in filter(None, git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')):
        found.append(('A', path, path))
    return found


def old_text(repo, merge_base, path):
    return git(repo, 'show', merge_base+':'+path, check=False) or ''


def new_text(repo, path):
    try:
        return (Path(repo)/path).read_bytes().decode('utf-8', 'replace')
    except OSError:
        return ''


# --- A small YAML reader: block mappings and lists, flow {} and [], block scalars skipped -------------------------------

def scan_quotes(line):
    """(the line with quoted text blanked, the quote still open at its end or None)."""
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
            out.append(' ' if ch != '"' and ch != "'" else ch)
        elif ch in '"\'' and (i == 0 or line[i-1] in ' \t:-[{,'):
            quote = ch
            out.append(ch)
        else:
            out.append(ch)
    return ''.join(out), quote


def strip_comment(line):
    blanked, _ = scan_quotes(line)
    for i, ch in enumerate(blanked):
        if ch == '#' and (i == 0 or blanked[i-1] in ' \t'):
            return line[:i]
    return line


def depth(blanked):
    return blanked.count('[') + blanked.count('{') - blanked.count(']') - blanked.count('}')


KEY = re.compile(r'''^("(?:[^"\\]|\\.)*"|'[^']*'|[^\s'"{\[#&*!|>%@`-][^:]*?|-[^\s:][^:]*?)\s*:(?:\s+|$)''')
BLOCK_SCALAR = re.compile(r'^[|>][-+0-9]*$')


def parse_yaml(text):
    try:
        return read_yaml(text)
    except YamlError:
        raise
    except Exception as error:  # a form this reader does not know: unreadable, never a crash
        raise YamlError(error.__class__.__name__)


def read_yaml(text):
    raw_lines = [strip_comment(raw).rstrip() for raw in text.replace('\r\n', '\n').split('\n')]
    lines, i = [], 0
    while i < len(raw_lines):
        body = raw_lines[i]
        i += 1
        if not body.strip() or body.strip() in ('---', '...'):
            continue
        content = body.lstrip(' ')
        if content.startswith('\t'):
            raise YamlError('tab indentation')
        blanked, quote = scan_quotes(content)
        while (quote or depth(blanked) > 0) and i < len(raw_lines):  # a quoted or flow value over several lines
            content += ' ' + raw_lines[i].strip()
            i += 1
            blanked, quote = scan_quotes(content)
        if quote or depth(blanked) > 0:
            raise YamlError('unterminated value')
        if re.search(r'(^|[\s\[{,:])[&*!][^\s]', blanked):
            raise YamlError('anchors, aliases and tags are not read')
        lines.append([len(body)-len(body.lstrip(' ')), content])
    if not lines:
        return None
    value, i = block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YamlError('unexpected indentation at a line')
    return value


def is_item(content):
    return content == '-' or content.startswith('- ')


def block(lines, i, indent):
    return (sequence if is_item(lines[i][1]) else mapping)(lines, i, indent)


def child(lines, i, indent, same_level_list=False):
    """The nested value after a 'key:' or '-' line ending at i-1, or None."""
    if i < len(lines) and (lines[i][0] > indent or (same_level_list and lines[i][0] == indent and is_item(lines[i][1]))):
        return block(lines, i, lines[i][0])
    return None, i


def skip_deeper(lines, i, indent):
    while i < len(lines) and lines[i][0] > indent:
        i += 1
    return i


def plain_value(lines, i, indent, rest):
    """A value on its line, and a plain scalar's continuation lines (more indented) joined to it."""
    if i < len(lines) and lines[i][0] > indent:
        if rest[0] in '"\'[{':
            raise YamlError('multi-line value')
        end = skip_deeper(lines, i, indent)
        return scalar(' '.join([rest] + [line[1] for line in lines[i:end]])), end
    return inline(rest), i


def mapping(lines, i, indent):
    result = {}
    while i < len(lines) and lines[i][0] == indent and not is_item(lines[i][1]):
        match = KEY.match(lines[i][1])
        if not match:
            raise YamlError('not a key: '+lines[i][1][:40])
        key, rest = scalar(match.group(1)), lines[i][1][match.end():].strip()
        i += 1
        if not rest:
            value, i = child(lines, i, indent, same_level_list=True)
        elif BLOCK_SCALAR.match(rest):
            value, i = '', skip_deeper(lines, i, indent)
        else:
            value, i = plain_value(lines, i, indent, rest)
        result[key] = value
    if i < len(lines) and lines[i][0] > indent:
        raise YamlError('unexpected indentation')
    return result, i


def sequence(lines, i, indent):
    result = []
    while i < len(lines) and lines[i][0] == indent and is_item(lines[i][1]):
        rest = lines[i][1][1:].lstrip(' ')
        if not rest:
            value, i = child(lines, i+1, indent)
        elif KEY.match(rest) and not rest.startswith(('{', '[')):
            column = indent + len(lines[i][1]) - len(rest)
            lines[i] = [column, rest]
            value, i = mapping(lines, i, column)
        elif BLOCK_SCALAR.match(rest):
            value, i = '', skip_deeper(lines, i+1, indent)
        else:
            value, i = plain_value(lines, i+1, indent, rest)
        result.append(value)
    return result, i


def scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in '"\'':
        inner = text[1:-1]
        return inner.replace("''", "'") if text[0] == "'" else inner.replace('\\"', '"').replace('\\\\', '\\')
    return {'true': True, 'false': False, 'True': True, 'False': False, 'null': None, '~': None}.get(text, text)


def inline(text):
    if text[0] not in '[{':
        return scalar(text)
    value, end = flow(text, 0)
    if text[end:].strip():
        raise YamlError('text after a flow value')
    return value


def skip_spaces(text, i):
    while i < len(text) and text[i] == ' ':
        i += 1
    return i


def flow(text, i):
    i = skip_spaces(text, i)
    if i >= len(text):
        raise YamlError('unterminated flow value')
    if text[i] in '[{':
        closing, i = (']' if text[i] == '[' else '}'), i+1
        items = [] if closing == ']' else {}
        while True:
            i = skip_spaces(text, i)
            if i < len(text) and text[i] == closing:
                return items, i+1
            if closing == '}':
                key, i = flow_token(text, i, ':')
                if i >= len(text) or text[i] != ':':
                    raise YamlError('flow mapping without ":"')
                value, i = flow(text, i+1)
                items[scalar(key)] = value
            else:
                value, i = flow(text, i)
                items.append(value)
            i = skip_spaces(text, i)
            if i < len(text) and text[i] == ',':
                i += 1
            elif i >= len(text) or text[i] != closing:
                raise YamlError('unterminated flow value')
    token, i = flow_token(text, i, ',]}')
    return scalar(token), i


def flow_token(text, i, stops):
    if i >= len(text):
        raise YamlError('unterminated flow value')
    if text[i] in '"\'':
        end = text.find(text[i], i+1)
        if end < 0:
            raise YamlError('unterminated string')
        return text[i:end+1], end+1
    start = i
    while i < len(text) and text[i] not in stops:
        i += 1
    return text[start:i].strip(), i


# --- dbt ---------------------------------------------------------------------------------------------------------------

def dbt_tests(doc):
    """[{key, context, name, type, args}] of a properties file; key: model.column.test, source.table.column.test…"""
    found, keys = [], set()
    def add(context, item):
        if isinstance(item, str):
            kind, name, args = item, item, {}
        elif isinstance(item, dict) and isinstance(item.get('test_name'), str):
            kind, args = item['test_name'], {k: v for k, v in item.items() if k not in ('test_name', 'name')}
            name = item['name'] if isinstance(item.get('name'), str) else kind
        elif isinstance(item, dict) and len(item) == 1 and isinstance(next(iter(item.values())), (dict, type(None))):
            kind, args = next(iter(item.items()))
            args = dict(args or {})
            name = args.pop('name') if isinstance(args.get('name'), str) else kind
        else:
            return
        key, n = '.'.join(context+[str(name)]), 2
        while key in keys:
            key, n = '.'.join(context+[str(name)])+'#'+str(n), n+1
        keys.add(key)
        found.append({'key': key, 'context': context, 'name': str(name), 'type': str(kind), 'args': args})
    def walk(node, context):
        if isinstance(node, dict):
            here = context+[node['name']] if isinstance(node.get('name'), str) else context
            for key, value in node.items():
                if key in ('tests', 'data_tests') and isinstance(value, list):
                    for item in value:
                        add(here, item)
                elif isinstance(value, (dict, list)):
                    walk(value, here)
        elif isinstance(node, list):
            for item in node:
                walk(item, context)
    walk(doc, [])
    return found


def dbt_nodes(doc):
    """Every named node of a properties file (model, source, table, column) as a tuple of names."""
    found = set()
    def walk(node, context):
        if isinstance(node, dict):
            here = context+[node['name']] if isinstance(node.get('name'), str) else context
            if here is not context:
                found.add(tuple(here))
            for key, value in node.items():
                if key not in ('tests', 'data_tests') and isinstance(value, (dict, list)):
                    walk(value, here)
        elif isinstance(node, list):
            for item in node:
                walk(item, context)
    walk(doc, [])
    return found


def project_test_config(doc):
    """{section path: {setting: value}} of the '+' settings under tests: / data_tests: in dbt_project.yml."""
    found = {}
    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.startswith('+'):
                    found.setdefault('.'.join(path), {})[key[1:]] = value
                elif isinstance(value, dict):
                    walk(value, path+[str(key)])
    for section in ('tests', 'data_tests'):
        if isinstance((doc or {}).get(section), dict):
            walk(doc[section], ['data_tests'])  # the older and newer names of one setting tree
    return found


def effective(sections, section):
    """The settings a section gets, its parents' first (dbt inherits them down the tree)."""
    parts, merged = section.split('.'), {}
    for n in range(1, len(parts)+1):
        merged.update(sections.get('.'.join(parts[:n]), {}))
    return merged


def split_args(args):
    args = args if isinstance(args, dict) else {}
    config = {k: args[k] for k in DBT_CONFIG if k in args}
    if isinstance(args.get('config'), dict):
        config.update(args['config'])
    rest = {k: v for k, v in args.items() if k != 'config' and k not in DBT_CONFIG}
    return config, rest


THRESHOLD = re.compile(r'^\s*(>=|>|<=|<|!=)\s*(-?\d+(?:\.\d+)?)\s*$')


def relaxed(old, new):
    """True when a threshold now lets more failures pass, False when it is tighter or equal, None when unknown."""
    def read(value):
        match = THRESHOLD.match(str('!=0' if value is None else value))
        if not match:
            return None
        op, number = match.group(1), float(match.group(2))
        return ('>', number) if op == '!=' and number == 0 else (op, number)
    a, b = read(old), read(new)
    if not a or not b or a[0] != b[0] or a[0] == '!=':
        return None
    return b[1] > a[1] if a[0] in ('>', '>=') else b[1] < a[1]


def is_false(value):
    return value is False or (isinstance(value, str) and value.strip().lower() in ('false', 'no', 'off'))


def compare_config(old, new):
    """[(kind, setting, before, after)] for one test's (or one project section's) settings, the rest as assertion_changed."""
    facts, handled = [], set()
    if is_false(new.get('enabled')) and not is_false(old.get('enabled')):
        facts.append(('test_disabled', 'enabled', old.get('enabled'), new.get('enabled')))
    handled.add('enabled')
    old_severity, new_severity = str(old.get('severity') or 'error').lower(), str(new.get('severity') or 'error').lower()
    if new_severity == 'warn' and old_severity != 'warn':
        facts.append(('severity_lowered', 'severity', old_severity, new_severity))
    handled.add('severity')
    for setting in ('error_if', 'warn_if'):
        if old.get(setting) != new.get(setting):
            verdict = relaxed(old.get(setting), new.get(setting))
            if verdict is True:
                facts.append(('threshold_relaxed', setting, old.get(setting), new.get(setting)))
            if verdict is not None:
                handled.add(setting)
        else:
            handled.add(setting)
    if any(old.get(k) != new.get(k) for k in set(old) | set(new) if k not in handled):
        facts.append(('assertion_changed', None, None, None))
    return facts


def locate(text, parts):
    """1-based line of the last of these names, found in order, or None."""
    lines, start, found = text.split('\n'), 0, None
    for part in parts:
        pattern = re.compile(r'(^|[\s\-{\[,:])["\']?'+re.escape(part)+r'["\']?(\s*[:,\]}]|\s*$)')
        for i in range(start, len(lines)):
            if pattern.search(lines[i]):
                found, start = i+1, i+1
                break
    return found


def short(value):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text[:LINE_MAX]


# --- Facts -------------------------------------------------------------------------------------------------------------

def fact(kind, path, family=None, line=None, test=None, before=None, after=None, moved_to=None):
    return {'kind': kind, 'family': family, 'path': path, 'line': line, 'test': test, 'before': short(before),
            'after': short(after), 'moved_to': moved_to}


def is_test_path(path):
    return any(part in TEST_DIRS for part in path.split('/')[:-1])


def under(root, rel):
    return rel if root == '' else root+'/'+rel


class Dbt:
    """The dbt projects of the repository: their roots and the folders dbt reads in each."""

    def __init__(self, repo, files):
        self.roots = {}
        for path in files:
            if path == 'dbt_project.yml' or path.endswith('/dbt_project.yml'):
                root = path[:-len('dbt_project.yml')].rstrip('/')
                try:
                    project = parse_yaml(new_text(repo, path)) or {}
                except YamlError:
                    project = {}
                folders = {}
                for key, default in DBT_RESOURCE_PATHS.items():
                    value = project.get(key) if isinstance(project, dict) else None
                    folders[key] = [str(v).strip('/') for v in value] if isinstance(value, list) and value else default
                self.roots[root] = folders

    def root_of(self, path):
        best = None
        for root in self.roots:
            if (root == '' or path.startswith(root+'/')) and (best is None or len(root) > len(best)):
                best = root
        return best

    def relative(self, path):
        root = self.root_of(path)
        return root, (None if root is None else path[len(root)+1 if root else 0:])

    def in_folders(self, path, keys):
        root, rel = self.relative(path)
        return root is not None and any(rel.startswith(f+'/') for k in keys for f in self.roots[root][k])

    def singular_test(self, path):
        return path.endswith('.sql') and self.in_folders(path, ['test-paths'])

    def properties(self, path, root):
        return (self.root_of(path) == root and path.endswith(('.yml', '.yaml'))
                and self.in_folders(path, list(DBT_RESOURCE_PATHS)))

    def touched(self, path):
        root, rel = self.relative(path)
        return root is not None and (rel == 'dbt_project.yml' or self.in_folders(path, list(DBT_RESOURCE_PATHS)))


def similarity(a, b):
    a, b = a.replace('\r\n', '\n'), b.replace('\r\n', '\n')
    if a == b:
        return 1.0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return matcher.ratio() if matcher.real_quick_ratio() >= 0.5 and matcher.quick_ratio() >= 0.5 else 0.0


def analyse(repo, merge_base):
    changed = changes(repo, merge_base)
    files = [p for p in git(repo, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0') if p]
    dbt = Dbt(repo, files)
    facts, unrecognized, unreadable = [], 0, []
    added, used = None, set()
    for status, old, new in changed:
        family = 'dbt' if dbt.singular_test(old) or dbt.singular_test(new) else None
        if not (family or is_test_path(old) or is_test_path(new)):
            continue
        if status == 'D':
            if added is None:  # read the added files only once, and only when a test file was deleted
                added = {}
                for s, _, path in changed:
                    full = Path(repo)/path
                    if s == 'A' and full.is_file() and full.stat().st_size <= MAX_COMPARED:
                        added[path] = new_text(repo, path)
            before = old_text(repo, merge_base, old)
            scored = sorted(((similarity(before, text), path) for path, text in added.items() if path not in used), reverse=True)
            twin = scored[0][1] if scored and scored[0][0] >= 0.5 else None
            if twin:
                used.add(twin)
                facts.append(fact('test_moved', old, family, moved_to=twin))
            else:
                facts.append(fact('test_file_deleted', old, family))
        elif status == 'R':
            facts.append(fact('test_moved', old, family, moved_to=new))
        elif family is None:
            unrecognized += 1
    for root in sorted(dbt.roots):
        facts.extend(dbt_facts(repo, merge_base, dbt, root, changed, files, unreadable))
    families = {'dbt'} if any(dbt.touched(p) for _, o, n in changed for p in (o, n)) else set()
    return facts, unrecognized, sorted(set(unreadable)), families


def dbt_facts(repo, merge_base, dbt, root, changed, files, unreadable):
    facts = []
    project = under(root, 'dbt_project.yml')
    status = next((s for s, o, n in changed if project in (o, n)), None)
    if status in ('M', 'R'):
        try:
            before = project_test_config(parse_yaml(old_text(repo, merge_base, project)))
            after = project_test_config(parse_yaml(new_text(repo, project)))
        except YamlError:
            unreadable.append(project)
            before = after = {}
        text = new_text(repo, project)
        for section in sorted(set(before) | set(after)):
            if before.get(section) == after.get(section):
                continue
            for kind, setting, old_value, new_value in compare_config(effective(before, section), effective(after, section)):
                where = locate(text, section.split('.')[1:] + (['+'+setting] if setting else []))
                facts.append(fact(kind, project, 'dbt', where, section,
                                  setting+': '+str(old_value) if setting else None, setting+': '+str(new_value) if setting else None))

    old_tests, new_tests, texts, old_nodes, new_nodes = {}, {}, {}, set(), set()
    for s, old, new in changed:
        sides = [] if s == 'A' else [('old', old)]
        sides += [] if s == 'D' else [('new', new)]
        sides = [(side, path) for side, path in sides if dbt.properties(path, root)]
        if not sides:
            continue
        read = {}
        try:
            for side, path in sides:
                text = old_text(repo, merge_base, path) if side == 'old' else new_text(repo, path)
                doc = parse_yaml(text)
                read[(side, path)] = (text, dbt_tests(doc), dbt_nodes(doc))
        except YamlError:
            unreadable.extend(path for _, path in sides)
            continue  # this file only: both of its sides are left out, the others still count
        for (side, path), (text, tests, nodes) in read.items():
            texts[(side, path)] = text
            (old_nodes if side == 'old' else new_nodes).update(nodes)
            for test in tests:
                (old_tests if side == 'old' else new_tests).setdefault(test['key'], dict(test, path=path))

    elsewhere = None
    def find_elsewhere(key):
        nonlocal elsewhere
        if elsewhere is None:
            elsewhere = {}
            changed_paths = {p for _, o, n in changed for p in (o, n)}
            for path in files:
                if dbt.properties(path, root) and path not in changed_paths:
                    try:
                        for test in dbt_tests(parse_yaml(new_text(repo, path))):
                            elsewhere.setdefault(test['key'], dict(test, path=path))
                    except YamlError:
                        continue
        return elsewhere.get(key)

    def renamed(a, b):
        """True when b is test a under a new name: the test itself renamed in place, or the one model, source, table or
        column that held it renamed (the old node is gone, the new one did not exist). Same type and arguments; its
        settings (severity, thresholds…) may change too, and are then compared like any kept test's."""
        if a['type'] != b['type'] or json.dumps(split_args(a['args'])[1], sort_keys=True) != json.dumps(split_args(b['args'])[1], sort_keys=True):
            return False
        old_context, new_context = tuple(a['context']), tuple(b['context'])
        if old_context == new_context:
            return a['name'] != b['name']
        if len(old_context) != len(new_context) or a['name'] != b['name']:
            return False
        differ = [i for i in range(len(old_context)) if old_context[i] != new_context[i]]
        if len(differ) != 1:
            return False
        level = differ[0]+1
        return old_context[:level] not in new_nodes and new_context[:level] not in old_nodes
    appeared = [new_tests[k] for k in sorted(new_tests) if k not in old_tests]
    for key in sorted(old_tests):
        old = old_tests[key]
        current = new_tests.get(key) or find_elsewhere(key)
        if current is None:
            current = next((t for t in sorted(appeared, key=lambda t: (t['path'] != old['path'], t['key'])) if renamed(old, t)), None)
            old_line = locate(texts.get(('old', old['path']), ''), old['context']+[old['name']])
            if current is None:
                facts.append(fact('test_removed', old['path'], 'dbt', old_line, key))
                continue
            appeared.remove(current)
            facts.append(fact('test_moved', old['path'], 'dbt', old_line, key, key, current['key'], moved_to=current['path']))
        elif current['path'] != old['path']:
            facts.append(fact('test_moved', old['path'], 'dbt', test=key, moved_to=current['path']))
        old_config, old_rest = split_args(old['args'])
        new_config, new_rest = split_args(current['args'])
        line = locate(texts.get(('new', current['path']), ''), current['context']+[current['name']])
        config_facts = compare_config(old_config, new_config)
        for kind, setting, before, after in config_facts:
            if kind != 'assertion_changed':
                facts.append(fact(kind, current['path'], 'dbt', line, key, setting+': '+str(before), setting+': '+str(after)))
        if old_rest != new_rest or any(kind == 'assertion_changed' for kind, *_ in config_facts):
            facts.append(fact('assertion_changed', current['path'], 'dbt', line, key, old['args'], current['args']))
    return facts


def report(repo, base_arg):
    out = {'schema': SCHEMA, 'base': base_arg, 'merge_base': None, 'error': None, 'facts': [], 'families_seen': [],
           'files_unrecognized': 0, 'files_unreadable': [], 'truncated': None}
    try:
        if git(repo, 'rev-parse', '--is-inside-work-tree', check=False) is None:
            raise RepoError('not a git repository: '+str(repo))
        base = resolve_base(repo, base_arg)
        merge_base = git(repo, 'merge-base', base, 'HEAD').strip()
        facts, unrecognized, unreadable, families = analyse(repo, merge_base)
    except (RepoError, OSError, subprocess.SubprocessError) as error:
        out['error'] = str(error) or error.__class__.__name__
        return out, 2
    facts.sort(key=lambda f: (f['path'], f['line'] or 0, f['test'] or '', f['kind']))
    out.update(base=base, merge_base=merge_base, families_seen=sorted(families | {f['family'] for f in facts if f['family']}),
               files_unrecognized=unrecognized, files_unreadable=unreadable)
    if len(facts) > MAX_FACTS:
        counts = {}
        for f in facts:
            counts[f['kind']] = counts.get(f['kind'], 0)+1
        out['truncated'], facts = counts, facts[:MAX_FACTS]
    out['facts'] = facts
    return out, 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='weakened_tests.py', description='Facts about weakened tests, for the review.')
    parser.add_argument('--base', help='the branch the work merges into (default: origin/HEAD, else main, else master)')
    parser.add_argument('--repo', default='.', help='the repository (default: the current folder)')
    args = parser.parse_args(argv)
    out, code = report(Path(args.repo), args.base)
    sys.stdout.write(json.dumps(out, ensure_ascii=True, indent=1)+'\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
