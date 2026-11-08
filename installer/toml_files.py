"""The kit's TOML files: the person's overrides.toml, the organization's organization.toml and the profiles. Read with
tomllib (standard library); written only in two narrow ways, both checked by reading the result back:
a whole file when an overrides.json is migrated, and one top-level list at a time, the rest of the file (comments
included) kept as is."""
import json
from pathlib import Path
import re

from .core import KitError, redact

import tomllib  # standard library since Python 3.11, the kit's minimum (2.0.0)

TOML_HINTS = (
    ('Invalid value', 'a value is not valid: a text must be in double quotes, a list in [ ], true and false in lower case'),
    ("Expected '=' after a key", 'a key is missing its = and value, or a key has a space or an accent: put it in double quotes'),
    ('Cannot overwrite a value', 'a key or a [section] is written twice'),
    ('Cannot declare', 'a [section] is written twice, or clashes with a key of the same name'),
    ('Unclosed array', 'a list is missing its closing ]'),
    ('Unclosed inline table', 'an inline table is missing its closing }'),
    ('Unterminated string', 'a text is missing its closing double quote'),
    ('Illegal character', 'a line break or tab inside a text: write \\n, or use a multi-line text in triple quotes'),
    ('Unescaped', 'a backslash inside a text: double it (\\\\), or use single quotes, for example for a Windows path'),
    ('Expected newline or end of document', 'something follows a value on the same line: one key = value per line'),
)
WHERE = re.compile(r'\s*\(at line (\d+), column (\d+)\)\s*$')
BARE_KEY = re.compile(r'[A-Za-z0-9_-]+')

def toml_error(path, text, exc):
    """Where (line, column, the line itself with any secret redacted) and what is wrong, in plain words."""
    message = str(exc)
    where = WHERE.search(message)
    raw = WHERE.sub('', message)
    hint = next((plain for start, plain in TOML_HINTS if raw.startswith(start)), raw)
    if not where:
        return str(path) + ': ' + hint + '.'
    line_no, col = int(where.group(1)), int(where.group(2))
    lines = text.splitlines() or ['']
    line = lines[min(line_no, len(lines)) - 1]
    return (str(path) + ', line ' + str(line_no) + ', column ' + str(col) + ': ' + hint + '.\n'
            + '    ' + redact(line.rstrip()) + '\n    ' + ' ' * max(col - 1, 0) + '^\n'
            + 'TOML: one key = value per line, texts in double quotes, lists in [ ], # starts a comment. A valid example: docs/customization.md.')

def parse_toml(text, path='TOML'):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise KitError(toml_error(path, text, exc)) from exc

def read_toml(path, default=None):
    path = Path(path)
    if not path.exists():
        return {} if default is None else default
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise KitError('Unreadable file: ' + str(path) + ' (' + str(exc) + ')') from exc
    return parse_toml(text, path)

# --- Writing ---------------------------------------------------------------------------------------------------------

def toml_key(key):
    return key if BARE_KEY.fullmatch(key) else json.dumps(key, ensure_ascii=False)

def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        # A JSON string is a valid TOML basic string, except that TOML wants \u escapes for control characters, which
        # json.dumps already writes.
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(toml_key(k) + ' = ' + toml_value(v) for k, v in value.items() if not documentation(k)) + ' }' if value else '{}'
    raise KitError('Value not representable in TOML: ' + repr(value))

def documentation(key):
    """Keys starting with _ (explanations) or $ ($schema) held documentation in the JSON files; in TOML they are comments."""
    return str(key).startswith(('_', '$'))

def without_documentation(value):
    if isinstance(value, dict):
        return {k: without_documentation(v) for k, v in value.items() if not documentation(k)}
    if isinstance(value, list):
        return [without_documentation(v) for v in value]
    return value

def comment_lines(text):
    return ['# ' + line if line else '#' for line in str(text).splitlines()]

def assignment(key, value, width=100):
    """key = value; a long list of plain values is wrapped, several per line, with a trailing comma."""
    line = toml_key(key) + ' = ' + toml_value(value)
    if len(line) <= width or not isinstance(value, list) or any(isinstance(v, (list, dict)) for v in value):
        return line
    rows, row = [], ''
    for item in (toml_value(v) + ',' for v in value):
        if row and len(row) + 1 + len(item) > width - 2:
            rows.append(row)
            row = ''
        row = (row + ' ' + item) if row else item
    rows.append(row)
    return toml_key(key) + ' = [\n' + '\n'.join('  ' + r for r in rows) + '\n]'

def dump_toml(data, schema=None):
    """A whole TOML document from a JSON object: $schema becomes the #:schema line editors read, a text under a key
    starting with _ becomes a comment where it was, a nested object a [section]. Checked by reading it back."""
    lines = ['#:schema ' + schema] if schema else []

    def inline(path, value):
        # Inside a section, a small object of plain values reads better on one line: env = { TOKEN = "${TOKEN}" }.
        return bool(path) and isinstance(value, dict) and not any(isinstance(v, dict) or documentation(k) for k, v in value.items())

    def section(path, table):
        notes = [line for k, v in table.items() if str(k).startswith('_') and isinstance(v, str) for line in comment_lines(v)]
        values = [(k, v) for k, v in table.items() if not documentation(k) and (not isinstance(v, dict) or inline(path, v))]
        tables = [(k, v) for k, v in table.items() if not documentation(k) and isinstance(v, dict) and not inline(path, v)]
        if path and (values or notes or not tables):
            if lines and lines[-1] != '':
                lines.append('')
            lines.append('[' + '.'.join(toml_key(k) for k in path) + ']')
        lines.extend(notes)
        lines.extend(assignment(k, v) for k, v in values)
        for k, v in tables:
            section(path + [k], v)

    section([], data)
    text = '\n'.join(lines).strip('\n') + '\n'
    if parse_toml(text) != without_documentation(data):
        raise KitError('The conversion to TOML would change a value: nothing was converted. Please report it.')
    return text

def set_list(text, key, values, path='overrides.toml'):
    """The document with the top-level key set to a list of names, everything else untouched (comments, order, other
    keys); the key is added before the first [section] when absent. Checked by reading the result back."""
    return set_key(text, key, list(values), path, 'the list ')


def set_key(text, key, value, path='overrides.toml', label=''):
    """The document with the top-level key set to a value (a list or a plain value), everything else untouched."""
    lines = text.split('\n')
    first_section = next((i for i, line in enumerate(lines) if re.match(r'\s*\[', line)), len(lines))
    start = next((i for i in range(first_section) if re.match(r'\s*' + re.escape(key) + r'\s*=', lines[i])), None)
    new_line = key + ' = ' + toml_value(value)
    if start is None:
        insert = first_section
        while insert > 0 and lines[insert - 1].strip() == '':
            insert -= 1
        lines[insert:insert] = [new_line]
    else:
        end = value_end(lines, start)
        lines[start:end + 1] = [new_line]
    result = '\n'.join(lines)
    expected = {**parse_toml(text, path), key: value}
    if parse_toml(result, path) != expected:
        raise KitError(str(path) + ': ' + label + key + ' could not be updated without changing something else; edit it by hand.')
    return result

def value_end(lines, start):
    """Index of the last line of the value that starts at lines[start] (a list can span lines): brackets are counted
    outside texts and comments."""
    depth, seen, quote = 0, False, None
    for index in range(start, len(lines)):
        line = lines[index]
        position = line.index('=') + 1 if index == start else 0
        while position < len(line):
            char = line[position]
            if quote:
                if char == '\\' and quote == '"':
                    position += 1
                elif char == quote:
                    quote = None
            elif char in '"\'':
                quote = char
            elif char == '#':
                break
            elif char in '[{':
                depth, seen = depth + 1, True
            elif char in ']}':
                depth -= 1
            position += 1
        if not seen or depth <= 0:
            return index
    return len(lines) - 1

def set_schema(text, uri):
    """The #:schema line pointing to uri, added at the top when missing."""
    if re.search(r'(?m)^#:schema .*$', text):
        return re.sub(r'(?m)^#:schema .*$', lambda m: '#:schema ' + uri, text, count=1)
    return '#:schema ' + uri + '\n' + text
