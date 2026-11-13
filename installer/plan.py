"""The steps of a neutral plan, before any adapter: the settings that apply, what is selected, the personal file, the
practices, skills, agents and guardrails, and the old files to remove. apply (installer/cli.py) runs them in order."""

from .core import content_root, ROOT, USER_CONTEXT, KitError, read_json, digest, safe_id, inside, hook_command, hook_identity, adopt_user_copy
from .toml_files import set_schema, set_section_key
from .config import AIKIT_FILE
from .adapters import ADAPTERS
from .settings import (core_settings, team_settings, personal_settings, merge_settings, allowed_commands, resolve_skills,
                       practice_file, CHOICE_KEYS, SCALAR_CHOICES)
from .commit import KIT_MANAGED

LIST_KEYS = ('extra_skills', 'disabled_skills', 'extra_agents', 'disabled_agents', 'extra_commands', 'disabled_commands')


def effective_settings(kit, team, choices):
    """The Core's defaults, then the Team's settings, then the person's aikit.toml on top (never replaced wholesale),
    with the choices of this run. Returns (Core defaults, team layer, personal, merged overrides, choices)."""
    org_defaults, team_layer, personal = core_settings().get('defaults', {}), team_settings(team), personal_settings(kit)
    choices = {k: (v if k in SCALAR_CHOICES else list(v)) for k, v in (choices or {}).items()}
    if set(choices) - set(CHOICE_KEYS) - set(SCALAR_CHOICES):
        raise KitError('Unknown choice: '+', '.join(sorted(set(choices) - set(CHOICE_KEYS) - set(SCALAR_CHOICES))))
    personal = {**personal, **choices}
    overrides = merge_settings(merge_settings(org_defaults, team_layer), personal)
    if overrides.get('frictions', 'propose') not in ('propose', 'auto', 'off'):
        raise KitError('frictions must be propose (default), auto or off.')
    if not isinstance(overrides.get('parallel_agents', False), bool):
        raise KitError('parallel_agents must be true or false.')
    for key in LIST_KEYS:
        if not isinstance(overrides.get(key,[]),list) or not all(isinstance(x,str) for x in overrides.get(key,[])):
            raise KitError(key+' must be a list of names.')
    return org_defaults, team_layer, personal, overrides, choices


def resolve_selection(selection, overrides, catalog, manifest):
    """The skills and the commands to install. Returns (selected skills, allowed commands)."""
    command_names = [c['name'] for c in manifest]
    for key in ('extra_commands','disabled_commands'):
        for name in overrides.get(key, []):
            if name not in command_names:
                raise KitError(key+': unknown command '+name+'. Kit commands: '+', '.join(command_names))
    # A command added in one line (extra_commands) also installs its skills.
    extra_command_skills = [s for c in manifest if c['name'] in overrides.get('extra_commands', []) for s in c['skills']]
    selected = resolve_skills({**selection, 'skills': list(selection['skills']) + extra_command_skills}, overrides, catalog)
    return selected, allowed_commands(selection.get('commands'), overrides, command_names)


def personal_file(kit, choices, deletes):
    """The text of ~/.ai-kit/aikit.toml after this run: created once from the template, then only the chosen keys changed
    ([user] lists, [frictions] capture), the person's other keys and comments kept. Returns (path, bytes, notices)."""
    path = kit/AIKIT_FILE
    if path.exists() and not choices:
        return path, None, []  # nothing to record: the file stays byte for byte as the person left it
    crlf = path.exists() and b'\r\n' in path.read_bytes()  # keep the person's line endings (Notepad writes CRLF)
    if path.exists():
        text = path.read_text(encoding='utf-8-sig')
    else:
        # Created once, pointing to the schema copied into ~/.ai-kit (never to a kit folder that may be deleted).
        text = set_schema((ROOT/'templates/user-aikit.toml').read_text(encoding='utf-8'), (kit/'schemas'/'aikit.schema.json').as_uri())
    for key, values in choices.items():
        text = (set_section_key(text, 'frictions', 'capture', values, '~/.ai-kit/aikit.toml') if key == 'frictions'
                else set_section_key(text, 'user', key, list(values), '~/.ai-kit/aikit.toml'))
    return path, (text.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else text).encode('utf-8'), []


def practice_layers(selection):
    """The practice layers of the selection, in order. Returns (file names, texts)."""
    names, texts = [], []
    for practice_id in selection['practices']:
        source, name = practice_file(practice_id)
        names.append(name)
        texts.append(source.read_text(encoding='utf-8'))
    return names, texts


def skill_sources(selected, catalog):
    """(skill, source folder) for each selected skill; a missing SKILL.md or a symbolic link stops the installation."""
    sources = []
    for skill in selected:
        source = inside(content_root(),catalog[skill]['path'])
        if not (source/'SKILL.md').is_file():
            raise KitError('SKILL.md missing: '+skill)
        for src in source.rglob('*'):
            if src.is_symlink():
                raise KitError('Symbolic link not supported: '+str(src))
        sources.append((skill, source))
    return sources


def select_agents(selection, overrides, agent_catalog, load_agent):
    """(name, definition) of the selection's agents, with the person's extra and disabled ones."""
    names = list(dict.fromkeys(selection.get('agents',[]) + overrides.get('extra_agents',[])))
    names = [x for x in names if x not in overrides.get('disabled_agents',[])]
    agents = []
    for agent in names:
        safe_id(agent)
        if agent not in agent_catalog:
            raise KitError('Unknown agent: '+agent)
        agents.append((agent, load_agent(inside(content_root(),agent_catalog[agent]['path']))))
    return agents


def guardrails(overrides, hooks_dir, managed_locked=(), managed_off=()):
    """The guardrails to enable. A guardrail marked "default" in the manifest is on unless the person's aikit.toml sets it to
    false; one IT locks (managed.toml hooks.locked) stays on, whatever a Team or a person writes.
    Returns (manifest, enabled guardrails, the locked ones a setting tried to turn off)."""
    hook_manifest = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
    wanted_hooks = overrides.get('hooks', {})
    if not isinstance(wanted_hooks, dict) or not all(isinstance(v, bool) for v in wanted_hooks.values()):
        raise KitError('hooks must be an object name → true/false.')
    wanted_hooks = {**{n: True for n, spec in hook_manifest.items() if spec.get('default')}, **wanted_hooks}
    # IT's locks (managed.toml hooks.locked); a guardrail IT turns off is not locked (ADR 0015).
    locked = [n for n in dict.fromkeys(managed_locked) if n not in managed_off]
    turned_off = [n for n in locked if wanted_hooks.get(n) is False]
    wanted_hooks.update({n: True for n in locked})
    for name in wanted_hooks:
        safe_id(name)
        if name not in hook_manifest:
            raise KitError('Unknown guardrail: '+name+'. Available: '+', '.join(sorted(hook_manifest)))
    on = [n for n, flag in wanted_hooks.items() if flag]
    enabled_hooks = {}
    for name in on:
        spec = hook_manifest[name]
        # Guardrails served by one script share one hook: the same group for each, written once by the adapters.
        hook_name, names = hook_identity(hook_manifest, name, on)
        enabled_hooks[name] = {'event': spec['event'], 'group': {**({'matcher': spec['matcher']} if spec['matcher'] else {}), 'hooks': [{'name': 'ai-kit-'+hook_name, 'type': 'command', 'command': hook_command(hooks_dir/spec['script'], names), 'timeout': 20000}]}}  # ms (Gemini CLI); the other adapters write their own form
    return hook_manifest, enabled_hooks, turned_off


def remove_stale_files(p, files, user_file):
    """Files of the previous installation this one no longer writes go into p.deletes; a file edited by hand stops the
    installation, except a USER.md copy, adopted so that the person's edit is never lost."""
    for rel, previous_hash in p.old_files.items():
        if rel in files:
            continue
        target_path = inside(p.home,rel)
        if not (rel.startswith(KIT_MANAGED) or any(a.is_managed(rel) for a in ADAPTERS)) or target_path == user_file:
            raise KitError('Invalid state: deletion outside the managed scope.')
        if target_path.exists():
            if digest(target_path.read_bytes()) != previous_hash:
                if target_path.name == USER_CONTEXT and target_path != user_file:
                    if adopt_user_copy(p, target_path, previous_hash):
                        p.deletes.append(target_path)
                    continue
                raise KitError('Old managed file modified locally: '+str(target_path)+'. Nothing was changed. Keep your copy elsewhere, '
                               'delete this file, then run the command again.')
            p.deletes.append(target_path)


def refuse_links(home, paths):
    """A symbolic link anywhere in a managed path stops the installation before any write."""
    for path in paths:
        for part in (path,*path.parents):
            if part == home:
                break
            if part.is_symlink():
                raise KitError('Symbolic link in a managed path: '+str(part))
