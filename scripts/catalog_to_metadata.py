"""One-time migration (V2 slice 3): the fields of skills/catalog.json and agents/catalog.json written as aikit-* metadata in
each SKILL.md and agent file, so that the resources describe themselves (docs/v2/resources.md). Idempotent: an existing aikit-*
line is replaced. The catalogs stay until slice 8; a test checks that the catalog rebuilt from the files equals them.

Usage: python3 scripts/catalog_to_metadata.py [--check]
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SKILL_FIELDS = (('version', 'version'), ('origin', 'origin'), ('license', 'license'), ('summary', 'description'), ('category', 'category'),
                ('tier', 'tier'), ('requires', 'requires'), ('needs-agents', 'needs_agents'), ('owner', 'owner'))
AGENT_FIELDS = (('version', 'version'), ('origin', 'origin'), ('owner', 'owner'))


def value_text(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return ','.join(value)
    return str(value)


def with_metadata(text, pairs):
    """The file with its front matter's metadata holding exactly these aikit-* pairs (other metadata kept)."""
    match = re.match(r'(---\n)(.*?)(\n---\n?)(.*)$', text, re.S)
    if not match:
        raise SystemExit('front matter expected')
    lines = [line for line in match.group(2).split('\n') if not line.strip().startswith('aikit-')]
    # mr: the nested metadata.credits table (not readable by the one-level parser) becomes one text.
    if any(line.strip() == 'credits:' for line in lines):
        start = next(i for i, line in enumerate(lines) if line.strip() == 'credits:')
        end = start+1
        while end < len(lines) and lines[end].startswith('    '):
            end += 1
        parts = dict(line.strip().split(': ', 1) for line in lines[start+1:end])
        credit = parts.get('skill', '')+' by '+parts.get('author', '')+' ('+parts.get('organisation', '')+'), '+parts.get('url', '').strip('"')
        lines[start:end] = ['  credits: '+json.dumps(credit)]
    new = ['  aikit-'+key+': '+json.dumps(value_text(value)) for key, value in pairs]
    if 'metadata:' in lines:
        at = lines.index('metadata:')+1
        while at < len(lines) and lines[at].startswith('  '):
            at += 1
        lines[at:at] = new
    elif new:
        lines += ['metadata:'] + new
    return match.group(1)+'\n'.join(lines)+match.group(3)+match.group(4)


def plan():
    changes = {}
    for kind, catalog, fields, file_of in (('skills', 'skills/catalog.json', SKILL_FIELDS, lambda e: ROOT/e['path']/'SKILL.md'),
                                           ('agents', 'agents/catalog.json', AGENT_FIELDS, lambda e: ROOT/e['path'])):
        for name, entry in json.loads((ROOT/catalog).read_text(encoding='utf-8')).items():
            if 'path' not in entry:
                continue  # an alias (replaced_by): kept in the engine, installer/resolve.py
            path = file_of(entry)
            pairs = [(key, entry[field]) for key, field in fields if field in entry]
            # optional: one key per skill, its value the fallback text shown when that skill is not installed.
            pairs += [('optional-'+skill, text) for skill, text in (entry.get('optional') or {}).items()] if kind == 'skills' else []
            text = path.read_text(encoding='utf-8')
            new = with_metadata(text, pairs)
            if new != text:
                changes[path] = new
    return changes


def main(argv):
    changes = plan()
    if '--check' in argv:
        for path in changes:
            print('not migrated: '+path.relative_to(ROOT).as_posix())
        return 1 if changes else 0
    for path, text in changes.items():
        path.write_text(text, encoding='utf-8')
    print(str(len(changes))+' files migrated.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
