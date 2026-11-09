"""Resources described by their own files (V2 slice 3, docs/v2/resources.md): the skill and agent catalogs are rebuilt from the
aikit-* metadata of each SKILL.md and agent file, found by convention, instead of being read from skills/catalog.json and
agents/catalog.json (still present until slice 8; a test checks that both give the same catalog). Pure: reads files, no
other side effect. Also checks what a catalog alone could not: a dependency that does not exist, a cycle."""
from pathlib import Path

from .core import KitError
from .frontmatter import aikit_metadata, csv, parse

SKILL_KEYS = (('version', 'version', str), ('origin', 'origin', str), ('license', 'license', str), ('summary', 'description', str),
              ('category', 'category', str), ('tier', 'tier', str), ('requires', 'requires', csv),
              ('needs-agents', 'needs_agents', lambda v: v == 'true'), ('protected', 'protected', lambda v: v == 'true'), ('owner', 'owner', str),
              ('default', 'default', lambda v: v == 'true'))
AGENT_KEYS = (('version', 'version', str), ('origin', 'origin', str), ('protected', 'protected', lambda v: v == 'true'), ('owner', 'owner', str),
              ('default', 'default', lambda v: v == 'true'))


def entry_from(meta, keys, rel):
    found = aikit_metadata(meta)
    entry = {}
    for key, field, convert in keys:
        if key in found:
            entry[field] = convert(found[key])
    if not entry.get('protected'):
        entry.pop('protected', None)
    optional = {key[len('optional-'):]: value for key, value in found.items() if key.startswith('optional-')}
    if optional:
        entry['optional'] = optional
    return {'path': rel, **entry}


def skill_catalog(root):
    """{name: entry} like skills/catalog.json: every skills/**/SKILL.md, its folder name as identifier, plus the aliases."""
    root = Path(root)
    catalog = {}
    for path in sorted((root/'skills').rglob('SKILL.md'), key=lambda p: p.as_posix()):
        meta, _ = parse(path.read_text(encoding='utf-8'))
        name = path.parent.name
        if meta.get('name') != name:
            raise KitError(path.relative_to(root).as_posix()+': name "'+str(meta.get('name'))+'" must be its folder name "'+name+'".')
        if name in catalog:
            raise KitError('Two skills named '+name+': '+catalog[name]['path']+' and '+path.parent.relative_to(root).as_posix())
        catalog[name] = entry_from(meta, SKILL_KEYS, path.parent.relative_to(root).as_posix())
        if 'description' not in catalog[name] and isinstance(meta.get('description'), str):
            catalog[name]['description'] = meta['description']  # no aikit-summary: the skill's own description
    check_graph(catalog)
    return catalog


def agent_catalog(root):
    """{name: entry} like agents/catalog.json: every agents/**/<name>.md with a front matter name (README files are not agents)."""
    root = Path(root)
    catalog = {}
    for path in sorted((root/'agents').rglob('*.md'), key=lambda p: p.as_posix()):
        if path.name.upper() == 'README.MD':
            continue
        meta, _ = parse(path.read_text(encoding='utf-8'))
        if meta.get('name') != path.stem:
            raise KitError(path.relative_to(root).as_posix()+': name "'+str(meta.get('name'))+'" must be its file name "'+path.stem+'".')
        if 'version' not in aikit_metadata(meta):
            continue  # an example or a draft without metadata is not installable
        catalog[path.stem] = entry_from(meta, AGENT_KEYS, path.relative_to(root).as_posix())
    return catalog


def check_graph(catalog):
    """A required skill that does not exist, or a cycle of requirements, is refused before anything is installed."""
    for name, entry in catalog.items():
        for needed in entry.get('requires', []):
            if needed not in catalog or 'path' not in catalog[needed]:
                raise KitError('Skill '+name+' requires '+needed+', which does not exist.')
    state = {}
    def visit(name, trail):
        if state.get(name) == 'done':
            return
        if state.get(name) == 'open':
            raise KitError('Cycle of required skills: '+' -> '.join(trail[trail.index(name):]+[name]))
        state[name] = 'open'
        for needed in catalog[name].get('requires', []):
            visit(needed, trail+[name])
        state[name] = 'done'
    for name in catalog:
        visit(name, [])
