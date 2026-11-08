"""ai-kit validate [folder] (V2 slice 3, docs/v2/resources.md): what a content tree (the kit's own, or a Core repository before it
is tagged) must pass before any workstation installs it. Read-only; prints one line per problem; exit 1 when there is one.

Checks: the manifest (aikit.toml), every skill and agent describing itself (aikit-* metadata, name = folder or file name),
required skills that exist and no cycle, commands whose skills exist, no skill named like a command (Gemini makes a command
of each skill), every skill cited in a command or an orchestrator declared, and check_skills (secrets, pipe to shell,
prompt injection, guardrail off, configuration writes, undeclared scripts)."""
import importlib.util
from pathlib import Path
import re

from .config import check_source
from .core import ROOT, KitError, content_from, load_commands
from .frontmatter import aikit_metadata, parse
from .resolve import agent_catalog, skill_catalog


def check_skills_module():
    spec = importlib.util.spec_from_file_location('ai_kit_check_skills', ROOT/'runtime'/'check_skills.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def problems(root, engine_version):
    root = Path(root).resolve()
    found = []
    try:
        if check_source(root, engine_version) is None:
            found.append('aikit.toml: no manifest at the root (schema, name, kind, min_engine).')
    except KitError as exc:
        found.append(str(exc))
    try:
        skills = skill_catalog(root)
    except KitError as exc:
        return found + [str(exc)]
    try:
        agent_catalog(root)
    except KitError as exc:
        found.append(str(exc))
    for path in sorted((root/'skills').rglob('SKILL.md')):
        if 'version' not in aikit_metadata(parse(path.read_text(encoding='utf-8'))[0]):
            found.append(path.relative_to(root).as_posix()+': no aikit-version in metadata.')
    with content_from(root):
        try:
            commands = load_commands()
        except KitError as exc:
            return found + [str(exc)]
    names = {c['name'] for c in commands}
    for command in commands:
        for skill in command['skills']:
            if skill not in skills or 'path' not in skills[skill]:
                found.append('commands/'+command['name']+'.md: skill '+skill+' does not exist.')
    found += ['skills: '+s+' has the name of a command (Gemini makes a command of each skill): rename it.' for s in sorted(set(skills) & names)]
    # Every kit skill cited by name in a command prompt is one it declares (skills:) or an optional one a playbook adds.
    for command in commands:
        cited = set(re.findall(r'Activate the ([a-z0-9-]+) skill', command['prompt']))
        for skill in sorted(cited - set(command['skills'])):
            if skill in skills:
                found.append('commands/'+command['name']+'.md: activates '+skill+' without listing it in skills:.')
    module = check_skills_module()
    allowed = {(root/p).resolve() for p in module.KIT_ALLOWED}
    paths = [root/p for p in module.KIT_PATHS if (root/p).exists()]
    for path, line, rule, why in module.scan(paths, allowed):
        found.append(path.relative_to(root).as_posix()+(':'+str(line) if line else '')+': '+rule+': '+why)
    return found


def validate(folder, engine_version):
    found = problems(folder, engine_version)
    for line in found:
        print('[Check] '+line)
    print('Validate: '+(str(len(found))+' problem(s).' if found else 'nothing found.'))
    return 1 if found else 0
