"""Minimal YAML front matter without dependencies: scalars, flow lists [a, b], block
lists (- a), and one-level tables of scalars (metadata:). Anything deeper is refused, never guessed."""
import json
import re

from .core import KitError, redact

KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')
AIKIT_PREFIX = 'aikit-'


def scalar(value):
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            raise KitError('Unreadable quoted value: '+redact(value)) from None
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    if value.startswith('[') and value.endswith(']'):
        return [scalar(v) if v.strip().startswith(('"', "'")) else v.strip() for v in split_flow(value[1:-1]) if v.strip()]
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    return value


def split_flow(text):
    """Comma-separated items of a flow list, commas inside quotes kept."""
    items, current, quote = [], '', None
    for char in text:
        if quote:
            current += char
            if char == quote:
                quote = None
        elif char in '"\'':
            quote, current = char, current + char
        elif char == ',':
            items.append(current)
            current = ''
        else:
            current += char
    items.append(current)
    return items


def split(text):
    """(front matter text, body) or KitError."""
    match = re.match(r'---\r?\n(.*?)\r?\n---\r?\n?(.*)$', text, re.S)
    if not match:
        raise KitError('Front matter --- expected.')
    return match.group(1), match.group(2)


def parse(text):
    """(meta dict, body)."""
    block, body = split(text)
    meta, table, items = {}, None, None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        line = raw.strip()
        if indent == 0:
            table = items = None
            key, sep, value = line.partition(':')
            if not sep or not KEY.fullmatch(key.strip()):
                raise KitError('Unreadable front matter line: '+redact(raw))
            key = key.strip()
            if value.strip():
                meta[key] = scalar(value)
            else:
                meta[key] = None  # a table or a block list follows
                table, items = key, key
            continue
        if table is None:
            raise KitError('Unexpected indentation in front matter: '+redact(raw))
        if line.startswith('- '):
            if meta[items] is None:
                meta[items] = []
            if not isinstance(meta[items], list):
                raise KitError('Mixed list and table in front matter: '+redact(raw))
            meta[items].append(scalar(line[2:]))
            continue
        key, sep, value = line.partition(':')
        if not sep or not KEY.fullmatch(key.strip()) or not value.strip():
            raise KitError('Front matter nested deeper than one level is not supported: '+redact(raw))
        if meta[table] is None:
            meta[table] = {}
        if not isinstance(meta[table], dict):
            raise KitError('Mixed list and table in front matter: '+redact(raw))
        meta[table][key.strip()] = scalar(value)
    return {k: ('' if v is None else v) for k, v in meta.items()}, body


def aikit_metadata(meta):
    """The kit's own keys of metadata (aikit-*), as strings; read by AI Kit, never meant for the agent."""
    table = meta.get('metadata') or {}
    return {k[len(AIKIT_PREFIX):]: str(v) for k, v in table.items() if isinstance(table, dict) and k.startswith(AIKIT_PREFIX)}


def strip_aikit(text):
    """The file as installed: the aikit-* lines of metadata removed, and metadata itself when nothing else is left in it.
    Everything else (order, quotes, comments) is kept byte for byte."""
    try:
        block, body = split(text)
    except KitError:
        return text
    lines, out, in_meta, meta_index, kept_in_meta = block.split('\n'), [], False, None, 0
    for line in lines:
        indent = len(line) - len(line.lstrip(' '))
        if indent == 0 and line.strip():
            if in_meta and kept_in_meta == 0 and meta_index is not None:
                del out[meta_index]
            in_meta = line.split(':', 1)[0].strip() == 'metadata' and not line.split(':', 1)[1].strip()
            meta_index, kept_in_meta = (len(out), 0) if in_meta else (None, 0)
            out.append(line)
            continue
        if in_meta and line.strip().startswith(AIKIT_PREFIX):
            continue
        if in_meta and line.strip():
            kept_in_meta += 1
        out.append(line)
    if in_meta and kept_in_meta == 0 and meta_index is not None:
        del out[meta_index]
    head = text[:text.index(block)]
    return head + '\n'.join(out) + text[text.index(block)+len(block):]


def csv(value):
    return [v.strip() for v in str(value or '').split(',') if v.strip()]
