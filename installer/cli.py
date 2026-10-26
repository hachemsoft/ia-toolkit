"""AI Kit: installation orchestration. Builds a neutral plan, then each adapter (installer/adapters/) translates it for its CLI.
Never modifies a project repo."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

from .core import (_PACKAGE_DIR, ROOT, KIT_CONTEXT, USER_CONTEXT, EMAIL, KitError, read_json, json_bytes, digest,
                   safe_id, inside, hook_command, load_commands, _ts, friction_id, fixed_frictions)
from .adapters import ADAPTERS
from .interface import ContextHost, DoctorContext, LiveCheck, Plan

def practice_file(practice_id):
    """Source file of a practice and name of the context file it produces."""
    safe_id(practice_id)
    matches = sorted((ROOT/'practices').glob('[0-9][0-9]-'+practice_id+'.md'))
    if len(matches) != 1:
        raise KitError('Practice not found or ambiguous: ' + practice_id)
    source = matches[0]
    return source, source.stem[:2]+'_'+practice_id.upper().replace('-','_')+'.md'

def profile_menu():
    """(id, label) of every profile in profiles/, sorted by its "order": adding a profile is adding one file."""
    profiles = [read_json(p) for p in sorted((ROOT/'profiles').glob('*.json'))]
    return [(p['id'], p.get('label') or p['id']) for p in sorted(profiles, key=lambda p: (p.get('order', 1000), p['id']))]

def profile_ids():
    return sorted(p.stem for p in (ROOT/'profiles').glob('*.json'))

def managed_context_names(profile):
    names = [KIT_CONTEXT] + [practice_file(p)[1] for p in profile['practices']]
    if len(set(names)) != len(names):
        raise KitError('Duplicate practice prefixes in the profile.')
    return names

def validate_server(server):
    if not isinstance(server, dict):
        raise KitError('MCP configuration: object expected.')
    transports = [key for key in ('command','httpUrl','url') if server.get(key)]
    if len(transports) != 1:
        raise KitError('MCP: choose a single transport: command, httpUrl or url.')
    key = transports[0]
    if not isinstance(server[key], str):
        raise KitError('MCP: transport must be a string.')
    if key != 'command' and not server[key].startswith('https://'):
        raise KitError('Remote MCP: HTTPS URL expected.')
    if 'args' in server and (not isinstance(server['args'],list) or not all(isinstance(x,str) for x in server['args'])):
        raise KitError('MCP: args must be a list of strings.')
    # Never preselect automatic trust.
    if server.get('trust') is True:
        raise KitError('MCP: trust=true is not supported by this kit.')
    return server

def git_identity(home):
    """Global git identity read from the given home folder."""
    if not shutil.which('git'):
        return {}
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home), 'XDG_CONFIG_HOME': str(home/'.config'), 'GIT_CONFIG_NOSYSTEM': '1'}
    result = {}
    for key in ('email','name'):
        try:
            proc = subprocess.run(['git','config','--global','--get','user.'+key], capture_output=True, text=True, encoding='utf-8', env=env, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return {}
        value = proc.stdout.strip()
        if proc.returncode == 0 and value:
            result[key] = value
    if 'email' in result and not EMAIL.fullmatch(result['email']):
        result.pop('email')
    return result

def detect_identity(home):
    """Declarative identity: first available source. Never an authentication."""
    found = next(((a.NAME, a.active_account(home)) for a in ADAPTERS if a.active_account(home)), (None, None))
    git = git_identity(home)
    if found[1]:
        identity = {'email': found[1], 'source': found[0]}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    if git.get('email'):
        identity = {'email': git['email'], 'source': 'git'}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    try:
        login = getpass.getuser()
    except Exception:
        return {}
    return {'name': login, 'source': 'os'} if login else {}

def organization():
    """organization.json at the root of the kit: what the organization decides (expected email domains, defaults)."""
    org = read_json(ROOT/'organization.json', {})
    if not isinstance(org.get('defaults', {}), dict):
        raise KitError('organization.json: defaults must be an object.')
    return org

def merge_settings(base, extra):
    """Organization defaults, then the person's overrides on top: lists add up, objects combine, a single value is replaced.
    Keys starting with _ are documentation, $schema is for editors."""
    merged = {k: v for k, v in base.items() if not str(k).startswith(('_', '$'))}
    for key, value in extra.items():
        if str(key).startswith(('_', '$')):
            continue
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_settings(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            merged[key] = current + [v for v in value if v not in current]
        else:
            merged[key] = value
    return merged

def unknown_keys(settings):
    """Keys of an overrides.json (or organization defaults) the kit does not know: usually a typo. The schema is the list."""
    known = set(read_json(ROOT/'schemas'/'overrides.schema.json').get('properties', {}))
    return sorted(k for k in settings if not str(k).startswith(('_', '$')) and k not in known)

def setting_differences(base, effective, prefix=''):
    """Single values the person's overrides change compared with the organization defaults (for doctor)."""
    changed = []
    for key, value in base.items():
        if str(key).startswith(('_', '$')) or key not in effective:
            continue
        if isinstance(value, dict) and isinstance(effective[key], dict):
            changed += setting_differences(value, effective[key], prefix+key+'.')
        elif not isinstance(value, list) and effective[key] != value:
            changed.append(prefix+key)
    return changed

def allowed_domains():
    value = organization().get('allowed_domains', [])
    if not isinstance(value, list) or not all(isinstance(x,str) and x for x in value):
        raise KitError('organization.json: allowed_domains must be a list of domains.')
    return [x.lower().lstrip('@') for x in value]

def domain_allowed(email, domains):
    return not domains or email.rsplit('@',1)[-1].lower() in domains

def team_ids():
    """Teams that have their own practices: practices/20-<team>.md, besides the shared 20-team.md."""
    return sorted(p.stem[3:] for p in (ROOT/'practices').glob('20-*.md') if p.stem != '20-team')

def profile_practices(profile, team):
    """The profile's practices, with the shared team practice replaced by the person's team when it has its own file."""
    if team and team not in team_ids():
        raise KitError('Unknown team: '+team+'. Teams with practices: '+(', '.join(team_ids()) or 'none (practices/20-<team>.md)'))
    return [team if p == 'team' and team else p for p in profile['practices']]

def resolve_skills(profile, overrides, catalog, log=print):
    """Final selection: profile + extra, replacements followed, dependencies added, disabled skills respected."""
    disabled = set(overrides.get('disabled_skills', []))
    selected = []
    def add(name, via=None):
        safe_id(name)
        if name not in catalog:
            raise KitError('Unknown skill: '+name)
        entry = catalog[name]
        if entry.get('replaced_by'):
            log('Skill replaced: '+name+' → '+', '.join(entry['replaced_by']))
            for replacement in entry['replaced_by']:
                add(replacement, via)
            return
        if name in disabled:
            if via:
                raise KitError('Skill '+name+' is disabled in overrides.json but required by '+via+'.')
            return
        if name in selected:
            return
        selected.append(name)
        for dependency in entry.get('requires', []):
            add(dependency, name)
    for name in list(profile['skills']) + list(overrides.get('extra_skills', [])):
        add(name)
    return selected

def allowed_commands(profile_commands, overrides, command_names):
    """Allowed commands: the profile list (or all), plus extra_commands, minus disabled_commands; None when nothing restricts."""
    extra, disabled = overrides.get('extra_commands', []), set(overrides.get('disabled_commands', []))
    if profile_commands is None and not disabled:
        return None
    base = list(profile_commands) if profile_commands is not None else list(command_names)
    return [c for c in base + [e for e in extra if e not in base] if c not in disabled]

def selected_commands(selected, manifest, allowed=None):
    """Commands whose skills are all installed, in manifest order; restricted to the profile list if there is one."""
    return [c for c in manifest if all(s in selected for s in c['skills']) and (allowed is None or c['name'] in allowed)]

def command_lines(commands):
    lines = []
    for category, title in (('workflow', 'Steps'), ('tool', 'Tools')):
        names = [c for c in commands if c['category'] == category]
        if names:
            lines.append('### '+title)
            lines += ['- /'+c['name']+' — '+c['description'] for c in names]
    return '\n'.join(lines) if lines else '- No command installed.'

FRICTION_SIGNALS = 'the person corrects or undoes what you just did; a check is red after "done"; they give up or ask the same thing again; you work around a skill or a guardrail; the ceremony was out of proportion; you went against a rule written in AGENTS.md, the kit context or a playbook (category rule).'

def friction_rule(mode):
    """The Frictions section of 00_KIT.md from overrides.json (frictions: propose by default, auto, off)."""
    if mode == 'off':
        return ''
    if mode == 'auto':
        return ('## Frictions\nLog the friction yourself, without asking, by running the `/friction` command script, then say so in one line and resume the work, when: '
                + FRICTION_SIGNALS + ' One factual sentence, never the text of a prompt or a secret.\n\n')
    return '## Frictions\nOffer in one line to log a `/friction` (without writing it yourself) when: ' + FRICTION_SIGNALS + '\n\n'

def playbook_lines(selected, catalog):
    names = [s for s in selected if catalog[s].get('category') == 'domain']
    return '\n'.join('- '+s+' : '+catalog[s]['description'] for s in names) if names else '- No domain playbook installed.'

def user_context_text(identity):
    template = (ROOT/'templates/user-context.md').read_text(encoding='utf-8')
    parts = [identity.get('name'), '<'+identity['email']+'>' if identity.get('email') else None]
    line = ' '.join(p for p in parts if p)
    return template.replace('{identity}\n', 'Person: '+line+'\n' if line else '')


AGENT_INSTRUCTION = ('Read the instructions and context of the current repo. Do not assume that the skills, '
                     'the MCP tools or the full parent history are available. '
                     'Ask the parent for anything missing. Use only the allowed read tools.\n')

def context_locations():
    """Possible context folders, relative to the home folder: those of the CLIs that host it, then the kit's own."""
    return [a.HOME_DIR for a in ADAPTERS if isinstance(a, ContextHost)] + ['.ai-kit/context']

def context_location(home, active):
    """Folder for the layers and 30_USER.md: that of an active CLI that only reads its context from its own folder (context_dir),
    otherwise ~/.ai-kit/context, which the other CLIs include or copy."""
    host = next((a for a in active if isinstance(a, ContextHost)), None)
    return host.context_dir(home) if host else home/'.ai-kit'/'context'

TARGETS = {'auto': None, 'gemini': ('gemini',), 'agy': ('agy',), 'codex': ('codex',), 'both': ('gemini', 'agy'), 'all': tuple(a.NAME for a in ADAPTERS)}

def selected_adapters(target, home):
    """Adapters to install: those the target names; in auto, those whose CLI is present on the machine,
    or the first of ADAPTERS (default CLI) if none is detected, for a machine where the CLI will be installed later."""
    if target not in TARGETS:
        raise KitError('--target must be one of '+', '.join(TARGETS)+'.')
    wanted = TARGETS[target]
    if wanted is None:
        return [a for a in ADAPTERS if a.present(home)] or [ADAPTERS[0]]
    return [a for a in ADAPTERS if a.NAME in wanted]

LEGACY_KIT_DIR = '.ai-toolkit'  # kit folder name before 0.19

def migrate_kit_dir(home, dry_run=False):
    """Renames ~/.ai-toolkit to ~/.ai-kit and carries the new prefix into the state. Files that cite the old path
    (guardrail declarations, agy rules, Codex block) are then rewritten by the installation. True if the old folder still needs migrating."""
    old, new = home/LEGACY_KIT_DIR, home/'.ai-kit'
    if not old.is_dir():
        return False
    if new.exists():
        raise KitError('~/'+LEGACY_KIT_DIR+' and ~/.ai-kit both exist: keep ~/.ai-kit, copy over what is missing (overrides.json, backups), remove ~/'+LEGACY_KIT_DIR+', then update.')
    if dry_run:
        print('The ~/'+LEGACY_KIT_DIR+' folder will be renamed to ~/.ai-kit on the next setup or update; --dry-run does not do it.')
        return True
    os.replace(old, new)
    state = read_json(new/'state.json')
    if state:
        prefix = LEGACY_KIT_DIR+'/'
        state['files'] = {('.ai-kit/'+rel[len(prefix):] if rel.startswith(prefix) else rel): value for rel, value in state.get('files', {}).items()}
        if str(state.get('context_dir', '')).startswith(prefix):
            state['context_dir'] = '.ai-kit/'+state['context_dir'][len(prefix):]
        atomic_write(new/'state.json', json_bytes(state))
    print('Kit folder renamed: ~/'+LEGACY_KIT_DIR+' becomes ~/.ai-kit.')
    return False

def apply(profile_id, home, dry_run=False, user=None, target='auto', team=None):
    """Full prevalidation, neutral plan, adapters, backup, then atomic write file by file."""
    home = home.resolve()
    if migrate_kit_dir(home, dry_run):
        return  # --dry-run: the old folder is not renamed yet, the plan would be wrong
    kit = home / '.ai-kit'
    active = selected_adapters(target, home)
    context_dir = context_location(home, active)
    profile_id = safe_id(profile_id)
    profile_path = ROOT/'profiles'/(profile_id+'.json')
    if not profile_path.exists():
        raise KitError('Unknown profile: '+profile_id)
    profile = read_json(profile_path)
    state = read_json(kit/'state.json')
    # Organization defaults, then the person's own overrides on top (never replaced wholesale).
    overrides = merge_settings(organization().get('defaults', {}), read_json(kit/'overrides.json', {}))
    if overrides.get('frictions', 'propose') not in ('propose', 'auto', 'off'):
        raise KitError('frictions must be propose (default), auto or off.')
    models = overrides.get('models', {})
    if not isinstance(models, dict) or not all(isinstance(k, str) and k in ('fast', 'deep', 'default') and isinstance(v, str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,60}', v) for k, v in models.items()):
        raise KitError('models must be an object {"fast"|"deep"|"default": "<model name>"}.')
    for key in ('extra_skills','disabled_skills','extra_agents','disabled_agents','extra_commands','disabled_commands'):
        if not isinstance(overrides.get(key,[]),list) or not all(isinstance(x,str) for x in overrides.get(key,[])):
            raise KitError(key+' must be a list of names.')
    catalog = read_json(ROOT/'skills/catalog.json')
    manifest = load_commands()
    command_names = [c['name'] for c in manifest]
    for key in ('extra_commands','disabled_commands'):
        for name in overrides.get(key, []):
            if name not in command_names:
                raise KitError(key+': unknown command '+name+'. Kit commands: '+', '.join(command_names))
    # A command added in one line (extra_commands) also installs its skills.
    extra_command_skills = [s for c in manifest if c['name'] in overrides.get('extra_commands', []) for s in c['skills']]
    selected = resolve_skills({**profile, 'skills': list(profile['skills']) + extra_command_skills}, overrides, catalog)
    allowed = allowed_commands(profile.get('commands'), overrides, command_names)
    writes, deletes = {}, []
    if not (kit/'overrides.json').exists():
        # Created once, pointing to the kit's schema so that editors complete and check the keys.
        starter = {'$schema': (ROOT/'schemas'/'overrides.schema.json').resolve().as_uri(), **read_json(ROOT/'templates/user-overrides.json')}
        writes[kit/'overrides.json'] = json_bytes(starter)
    identity = dict(user) if user else dict(state.get('user', {}))
    if identity.get('email') and not EMAIL.fullmatch(identity['email']):
        raise KitError('Invalid email: '+identity['email'])
    # Team: chosen at setup (--team or the setup question), then kept for update.
    team = safe_id(team) if team else state.get('team')
    profile = {**profile, 'practices': profile_practices(profile, team)}
    files = {}
    old_files = state.get('files',{})
    def managed_write(target, data, label):
        rel = target.relative_to(home).as_posix()
        if target.exists():
            previous = target.read_bytes()
            if rel in old_files:
                if digest(previous) != old_files[rel]:
                    raise KitError(label+' modified locally: '+str(target))
            elif previous != data:
                raise KitError(label+' existing file not managed by the kit: '+str(target))
        writes[target] = data
        files[rel] = digest(data)
    # --- Neutral plan: what to install, with nothing specific to a CLI. ---
    context_names = managed_context_names(profile)
    commands = selected_commands(selected, manifest, allowed)
    kit_text = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8').format(profile=profile_id, commands=command_lines(commands), playbooks=playbook_lines(selected, catalog), frictions=friction_rule(overrides.get('frictions', 'propose')))
    practice_names, practice_texts = [], []
    for practice_id in profile['practices']:
        source, name = practice_file(practice_id)
        practice_names.append(name)
        practice_texts.append(source.read_text(encoding='utf-8'))
    practices = '\n'.join(practice_texts)
    skill_sources = []
    for skill in selected:
        source = inside(ROOT,catalog[skill]['path'])
        if not (source/'SKILL.md').is_file():
            raise KitError('SKILL.md missing: '+skill)
        for src in source.rglob('*'):
            if src.is_symlink():
                raise KitError('Symbolic link not supported: '+str(src))
        skill_sources.append((skill, source))
    agent_catalog = read_json(ROOT/'agents/catalog.json')
    selected_agents = list(dict.fromkeys(profile.get('agents',[]) + overrides.get('extra_agents',[])))
    selected_agents = [x for x in selected_agents if x not in overrides.get('disabled_agents',[])]
    agents = []
    for agent in selected_agents:
        safe_id(agent)
        if agent not in agent_catalog:
            raise KitError('Unknown agent: '+agent)
        agents.append((agent, read_json(inside(ROOT,agent_catalog[agent]['path']))))
    hooks_dir = kit/'hooks'  # scripts shared by all CLIs, like kit/bin/friction.py
    hook_manifest = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
    wanted_hooks = overrides.get('hooks', {})
    if not isinstance(wanted_hooks, dict) or not all(isinstance(v, bool) for v in wanted_hooks.values()):
        raise KitError('hooks must be an object name → true/false.')
    enabled_hooks = {}
    # A guardrail marked "default" in the manifest is on unless overrides.json sets it to false.
    wanted_hooks = {**{n: True for n, spec in hook_manifest.items() if spec.get('default')}, **wanted_hooks}
    for name, flag in wanted_hooks.items():
        safe_id(name)
        if name not in hook_manifest:
            raise KitError('Unknown guardrail: '+name+'. Available: '+', '.join(sorted(hook_manifest)))
        if not flag:
            continue
        spec = hook_manifest[name]
        script = hooks_dir/spec['script']
        enabled_hooks[name] = {'event': spec['event'], 'group': {'matcher': spec['matcher'], 'hooks': [{'name': 'ai-kit-'+name, 'type': 'command', 'command': hook_command(script)}]}}
    mcp_entries = overrides.get('mcp',{})
    if not isinstance(mcp_entries,dict):
        raise KitError('mcp must be an object.')
    enabled_mcp = {}
    for name,entry in mcp_entries.items():
        safe_id(name)
        if not isinstance(entry,dict) or not isinstance(entry.get('enabled',False),bool):
            raise KitError('MCP: invalid entry or enabled value.')
        if entry.get('enabled'):
            enabled_mcp['ai-kit-'+name] = validate_server(entry.get('server'))
    p = Plan(active=[a.NAME for a in active],
        home=home, kit=kit, state=state, old_files=old_files, overrides=overrides, profile_id=profile_id, profile=profile,
        catalog=catalog, selected=selected, skill_sources=skill_sources, commands=commands, context_names=context_names,
        kit_text=kit_text, practice_names=practice_names, practice_texts=practice_texts, user_file=context_dir/USER_CONTEXT, context_dir=context_dir,
        user_context_text=user_context_text(identity), agents=agents, models=models, hooks_dir=hooks_dir,
        hook_manifest=hook_manifest, enabled_hooks=enabled_hooks, enabled_mcp=enabled_mcp, writes=writes, deletes=deletes,
        managed_write=managed_write, 
        agent_body=lambda definition: practices+'\n'+AGENT_INSTRUCTION+'\n'+definition['instructions']+'\n')
    # Scripts shared by all CLIs: frictions and enabled guardrails.
    managed_write(kit/'bin'/'friction.py', (ROOT/'runtime/friction.py').read_bytes(), 'Kit script')
    for name in enabled_hooks:
        managed_write(hooks_dir/hook_manifest[name]['script'], (ROOT/'runtime/hooks'/hook_manifest[name]['script']).read_bytes(), 'Guardrail')
    # Context layers and 30_USER.md, in the context folder (see context_location).
    managed_write(context_dir/KIT_CONTEXT, kit_text.encode('utf-8'), 'Context file')
    for name, text in zip(practice_names, practice_texts):
        managed_write(context_dir/name, text.encode('utf-8'), 'Context file')
    user_file = context_dir/USER_CONTEXT
    if not user_file.exists():
        # Created once, never rewritten or tracked. If the location changed, copy the existing version: the original stays in place.
        previous = next((f for f in (home/d/USER_CONTEXT for d in context_locations()) if f != user_file and f.is_file()), None)
        legacy_prefs = kit/'preferences.md'
        writes[user_file] = previous.read_bytes() if previous else legacy_prefs.read_bytes() if legacy_prefs.exists() else p.user_context_text.encode('utf-8')
    if (kit/'preferences.md').exists():
        writes[kit/'preferences.md.migrated'] = (kit/'preferences.md').read_bytes()
        deletes.append(kit/'preferences.md')
        p.migrated_prefs = True
    # --- Adapters: each translates the plan for its CLI. ---
    for adapter in active:
        adapter.install(p)
    for rel, previous_hash in old_files.items():
        if rel in files:
            continue
        target_path = inside(home,rel)
        if not (rel.startswith(KIT_MANAGED) or any(a.is_managed(rel) for a in ADAPTERS)):
            raise KitError('Invalid state: deletion outside the managed scope.')
        if target_path.exists():
            if digest(target_path.read_bytes()) != previous_hash:
                raise KitError('Old managed file modified locally: '+str(target_path))
            deletes.append(target_path)
    for adapter in ADAPTERS:
        adapter.finalize(p, active=adapter in active)  # inactive: removes what a previous installation had put in place
    new_state = {'schema_version':2,'version':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'profile':profile_id,'files':files,'mcp':enabled_mcp,'hooks':enabled_hooks,'user':identity,'blocks':p.blocks,'context_dir':context_dir.relative_to(home).as_posix(),'team':team,'practices':profile['practices'],
                 'installed':{'skills':selected,'commands':[c['name'] for c in commands],'agents':['ai-kit-'+a for a,_ in agents],'clis':[a.NAME for a in active]}}
    writes[kit/'state.json'] = json_bytes(new_state)
    writes = {path:b for path,b in writes.items() if not path.exists() or path.read_bytes()!=b}
    # Refuse links in managed paths before any write.
    for path in list(writes)+deletes:
        for part in (path,*path.parents):
            if part == home:
                break
            if part.is_symlink():
                raise KitError('Symbolic link in a managed path: '+str(part))
    print('Profile: '+profile_id+(' | team '+team if team else '')+' | '+str(len(selected))+' skills | '+str(len(agents))+' agents | '+str(len(enabled_mcp))+' MCP enabled | '+str(len(enabled_hooks))+' guardrails')
    if identity.get('email'):
        print('Identity: '+identity['email']+' (source '+identity.get('source','?')+')')
    if dry_run:
        print('Dry run: '+str(len(writes))+' files to write, '+str(len(deletes))+' to remove. Nothing changed.')
        return
    # No download, dependency installation or MCP execution.
    changed = list(writes)+deletes
    backup = kit/'backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    originals = {}
    for path in changed:
        originals[path] = path.read_bytes() if path.exists() else None
    if changed:
        backup.mkdir(parents=True,exist_ok=True)
        try:
            if os.name != 'nt':
                backup.chmod(0o700)
            for path,data in originals.items():
                if data is not None:
                    dest = backup/path.relative_to(home)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(data)
                    if os.name != 'nt':
                        dest.chmod(0o600)
            (backup/'manifest.json').write_bytes(json_bytes({'created':[p.relative_to(home).as_posix() for p,b in originals.items() if b is None],'restore':'Copy the backed-up files to the home folder; remove the created files only if unchanged.'}))
            if os.name != 'nt':
                (backup/'manifest.json').chmod(0o600)
            for path,data in writes.items():
                atomic_write(path,data)
            for path in deletes:
                path.unlink()
                prune_empty_dirs(path.parent, next((home/d for d in managed_roots(home) if path.is_relative_to(home/d)), home/'.ai-kit'))
        except OSError:
            for path,data in originals.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path,data)
            raise
    print('Installation complete.' if changed else 'Already up to date.')
    print('Your personal context: '+str(p.user_file))
    if p.migrated_prefs:
        print('Old preferences migrated to this file; copy kept in preferences.md.migrated.')
    print('Optional MCP: configure overrides.json then run update. See docs/mcp.md.')
    print(str(len(commands))+' commands installed; /guide explains where to start.')
    for adapter in active:
        line = adapter.summary(p)
        if line:
            print(line)
    print('Open a project, start the CLI and type /guide; CLI-specific checks: docs/cli/.')

KIT_MANAGED = ('.ai-kit/bin/', '.ai-kit/hooks/', '.ai-kit/context/')

def managed_roots(home):
    """Root folders where the kit puts files: its own and each CLI's."""
    return ['.ai-kit'] + sorted({a.HOME_DIR for a in ADAPTERS})

def prune_empty_dirs(directory, stop):
    """Remove empty folders left by a deletion, never a root folder or its structural folders."""
    roots = {stop} | {stop/name for name in ('skills', 'agents', 'commands', 'hooks', 'bin', 'config', 'config/plugins')}
    while directory not in roots and directory.is_relative_to(stop) and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent

def atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix='.ai-kit-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

# A known case each guardrail must block; doctor runs it to prove the guardrail works, not just that its file exists.
GUARDRAIL_PROBES = {
    'dbt-prod-guard': lambda home: {'tool_name': 'run_shell_command', 'tool_input': {'command': 'dbt run --target prod'}, 'cwd': str(home)},
    'protected-paths': lambda home: {'tool_name': 'write_file', 'tool_input': {'file_path': str(home/'.ai-kit'/'overrides.json')}, 'cwd': str(home)},
}

def command_parts(command):
    """Interpreter and script of a kit guardrail command (hook_command: "<python>" -I "<script>")."""
    parts = [part.strip('"\'') for part in (shlex.split(command, posix=(os.name != 'nt')) or [])]
    return (Path(parts[0]), Path(parts[-1])) if len(parts) >= 2 else (None, None)

def guardrail_checks(home, state, status):
    """Each enabled guardrail: its Python and script exist, and it really blocks a known case. A guardrail that cannot run lets everything through."""
    for name, hook in sorted(state.get('hooks', {}).items()):
        interpreter, script = command_parts(hook['group']['hooks'][0]['command'])
        if not interpreter or not interpreter.is_file():
            status(False, 'Guardrail '+name+': Python not found ('+str(interpreter)+'); run update to point to the current Python')
            continue
        if not script.is_file():
            status(False, 'Guardrail '+name+': script missing ('+str(script)+'); run update')
            continue
        probe = GUARDRAIL_PROBES.get(name)
        if not probe:
            continue
        env = {k: v for k, v in os.environ.items() if k != 'AI_KIT_ALLOW_PROD'}
        env.update({'HOME': str(home), 'USERPROFILE': str(home)})
        try:
            proc = subprocess.run([str(interpreter), '-I', str(script)], input=json.dumps(probe(home)), capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=20, env=env)
            answer = json.loads(proc.stdout or '{}')
        except (OSError, ValueError, subprocess.SubprocessError):
            answer = {}
        blocked = answer.get('decision') == 'deny' or answer.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'
        status(blocked, 'Guardrail '+name+': blocks a known case when run')

REPO_SKILL_DIRS = ('.agents/skills', '.gemini/skills', '.codex/skills')

def repo_root(start):
    """Folder holding .git, from start upwards; None outside a repo."""
    current = Path(start).resolve()
    for folder in [current] + list(current.parents):
        if (folder/'.git').exists():
            return folder
    return None

def repo_skill_overrides(state, cwd):
    """Skills of the current repo that carry the name of a kit skill or command: the CLI uses them instead of the kit's."""
    root = repo_root(cwd)
    if not root:
        return None, []
    installed = state.get('installed') or {}
    names = set(installed.get('skills', [])) | set(installed.get('commands', []))
    found = []
    for folder in dict.fromkeys([Path(cwd).resolve(), root]):
        for rel in REPO_SKILL_DIRS:
            base = folder/rel
            if base.is_dir():
                found += [(child.name, (base/child.name).relative_to(root).as_posix()) for child in sorted(base.iterdir())
                          if child.name in names and (child/'SKILL.md').is_file()]
    return root, found

def doctor(home, cwd=None):
    issues = 0
    def status(ok,message):
        nonlocal issues
        print(('[OK] ' if ok else '[Check] ')+message)
        if not ok:
            issues += 1
    status(sys.version_info >= (3,9),'Python 3.9 minimum')
    if (home/LEGACY_KIT_DIR).exists():
        status(False,'Old ~/'+LEGACY_KIT_DIR+' folder present: run update, which renames it to ~/.ai-kit')
    state = read_json(home/'.ai-kit/state.json')
    status(bool(state),'Kit installation; run setup if missing.')
    hints = []
    if state:
        print('Profile: '+state['profile']+' | version '+state['version'])
        identity = state.get('user', {})
        print('Recorded identity: '+(identity.get('email') or identity.get('name') or 'none')+(' (source '+identity['source']+')' if identity.get('source') else ''))
        profile = read_json(ROOT/'profiles'/(safe_id(state['profile'])+'.json'))
        profile = {**profile, 'practices': state.get('practices') or profile['practices']}  # with the person's team
        ctx = DoctorContext(profile=profile, load_commands=load_commands, managed_context_names=managed_context_names,
                                    allowed_domains=allowed_domains, domain_allowed=domain_allowed)
        context = state.get('context_dir', '.gemini')
        status((home/context/USER_CONTEXT).is_file(),'Personal context present: '+context+'/'+USER_CONTEXT)
        for rel,expected in state.get('files',{}).items():
            path = inside(home,rel)
            status(path.is_file() and digest(path.read_bytes())==expected,rel)
        guardrail_checks(home, state, status)
        folder_version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
        status(state.get('version') == folder_version, 'Installed version '+str(state.get('version'))+' matches the kit folder'+('' if state.get('version') == folder_version else ' ('+folder_version+'): run update'))
        org_defaults = organization().get('defaults', {})
        personal = read_json(home/'.ai-kit/overrides.json', {})
        for label, settings in (('~/.ai-kit/overrides.json', personal), ('organization.json defaults', org_defaults)):
            unknown = unknown_keys(settings)
            status(not unknown, label+': only known keys'+(' (unknown: '+', '.join(unknown)+'; a typo? keys are listed in schemas/overrides.schema.json)' if unknown else ''))
        changed = setting_differences(org_defaults, merge_settings(org_defaults, read_json(home/'.ai-kit/overrides.json', {})))
        if changed:
            print('[Info] Your overrides.json changes organization defaults: '+', '.join(changed))
        if state.get('team'):
            print('[Info] Team: '+state['team']+' (practices/20-'+state['team']+'.md)')
        root, overrides = repo_skill_overrides(state, cwd or os.getcwd())
        if overrides:
            print('[Info] This repo ('+root.name+') replaces kit skills: '+', '.join(path for _, path in overrides)
                  + '. The CLI uses them instead of the kit\'s; check what they do (and protect .agents/ with CODEOWNERS).')
        elif root:
            print('[OK] No kit skill replaced by this repo ('+root.name+')')
        installed = set(state.get('installed', {}).get('clis') or [a.NAME for a in ADAPTERS])
        for adapter in ADAPTERS:
            if adapter.NAME in installed:
                adapter.doctor(home, state, status, ctx)
                hints.append(adapter.doctor_hint())
        for name in profile['mcp']['recommended']:
            print('[Optional] '+name+': '+('configured' if 'ai-kit-'+name in state.get('mcp',{}) else 'not configured'))
    print('Local diagnosis only: authentication, MCP connection and IAM rights not tested; doctor --live makes a real call to the model.')
    for hint in hints:
        if hint:
            print(hint)
    return 1 if issues else 0

def usage(home, since_days=42, as_json=None, min_sessions=10, min_prompts=50):
    """Usage report for the usage review (docs/usage-review.md): commands typed, skills activated, agents called, from the logs each CLI already writes."""
    from collections import Counter
    state = read_json(home/'.ai-kit/state.json')
    if not state and (home/LEGACY_KIT_DIR).exists():
        raise KitError('Old ~/'+LEGACY_KIT_DIR+' folder: run update, which renames it to ~/.ai-kit, then usage.')
    if not state:
        raise KitError('Kit not installed: run setup.')
    catalog = read_json(ROOT/'skills/catalog.json')
    installed = state.get('installed') or next(a for a in ADAPTERS if isinstance(a, ContextHost)).installed_from_files(state)
    installed_skills, installed_commands, installed_agents = (sorted(installed.get(k, [])) for k in ('skills', 'commands', 'agents'))
    cutoff = datetime.now(timezone.utc).timestamp() - since_days*86400
    commands, skills, agents = Counter(), Counter(), Counter()
    unknown_commands = Counter()
    repeated = errors = prompts = 0
    sessions_seen, seen_texts = set(), {}
    # Each adapter reads its CLI's logs and returns neutral events (prompt, skill, agent, error).
    for adapter in ADAPTERS:
        for event in adapter.history(home, state):
            if event.get('ts', 0) < cutoff:
                continue
            session = event.get('session')
            if session:
                sessions_seen.add(session)
            kind = event['kind']
            if kind == 'error':
                errors += 1
            elif kind == 'skill':
                skills[event['name']] += 1
            elif kind == 'agent':
                agents[event['name']] += 1
            elif kind == 'prompt':
                prompts += 1
                shown = event['text']
                match = re.match(r'^[$/]([a-z][a-z0-9:-]*)', shown)
                if match:
                    if match.group(1) in installed_commands:
                        commands[match.group(1)] += 1
                    elif not any(match.group(1) in a.BUILTIN_COMMANDS for a in ADAPTERS):
                        unknown_commands[match.group(1)] += 1
                text = ' '.join(shown.split()).lower()
                if len(text) >= 15:
                    seen = seen_texts.setdefault(session, set())
                    if text in seen:
                        repeated += 1
                    seen.add(text)
    sessions = len(sessions_seen)
    unused_commands = [c for c in installed_commands if commands[c] == 0]
    unused_skills = [s for s in installed_skills if skills[s] == 0 and s not in installed_commands]  # a skill named after a command is measured by the command
    unused_agents = [a for a in installed_agents if agents[a] == 0]
    by_name = {c['name']: c for c in load_commands()}
    required_by_used = set(skills)
    for name in commands:
        required_by_used.update(by_name.get(name, {}).get('skills', []))
    frontier = list(required_by_used)
    while frontier:
        for dependency in catalog.get(frontier.pop(), {}).get('requires', []):
            if dependency not in required_by_used:
                required_by_used.add(dependency)
                frontier.append(dependency)
    def core_candidates():
        out = []
        for s in unused_skills:
            entry = catalog.get(s, {})
            if entry.get('tier') == 'core' and s not in required_by_used and entry.get('category') in ('workflow','tool'):
                out.append(s)
        return out
    # Frictions logged by /friction: ~/.ai-kit/frictions.jsonl, one line per friction, within the window.
    frictions, own_ids = [], []
    frictions_file = home/'.ai-kit/frictions.jsonl'
    if frictions_file.is_file():
        for line in frictions_file.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            entry['id'] = entry.get('id') or friction_id(entry.get('ts'), entry.get('text'))  # lines written before ids existed
            own_ids.append(entry['id'])
            if _ts(entry.get('ts')) >= cutoff:
                frictions.append({k: entry.get(k) for k in ('id', 'ts', 'category', 'command', 'text', 'cli', 'os', 'kit', 'profile', 'source') if entry.get(k) is not None})
    # Frictions of this person that a released version says it fixed: "(frictions: a1b2c3, …)" in the kit's CHANGELOG.
    changelog = ROOT/'CHANGELOG.md'
    fixed = fixed_frictions(changelog.read_text(encoding='utf-8')) if changelog.is_file() else {}
    fixed_own = {fid: fixed[fid] for fid in own_ids if fid in fixed}
    frictions_by_category = Counter(str(f.get('category')) for f in frictions)
    enough = sessions >= min_sessions and prompts >= min_prompts
    report = {'window_days': since_days, 'sessions': sessions, 'prompts': prompts, 'errors': errors,
              'commands': dict(commands), 'skills': dict(skills), 'agents': dict(agents),
              'unused_commands': unused_commands, 'unused_skills': unused_skills, 'unused_agents': unused_agents,
              'core_candidates_to_demote': core_candidates() if enough else [], 'enough_data': enough,
              'frictions': frictions, 'frictions_by_category': dict(frictions_by_category),
              'unknown_commands': dict(unknown_commands), 'repeated_prompts': repeated, 'frictions_fixed': fixed_own}
    print('Window: '+str(since_days)+' days | '+str(sessions)+' sessions | '+str(prompts)+' prompts | '+str(errors)+' errors')
    print('Commands typed: '+(', '.join(k+' ×'+str(v) for k,v in commands.most_common()) or 'none'))
    print('Skills activated: '+(', '.join(k+' ×'+str(v) for k,v in skills.most_common()) or 'none'))
    print('Agents called: '+(', '.join(k+' ×'+str(v) for k,v in agents.most_common()) or 'none'))
    print('Never used: '+str(len(unused_commands))+' commands, '+str(len(unused_skills))+' skills, '+str(len(unused_agents))+' agents.')
    print('Unknown commands typed: '+(', '.join('/'+k+' ×'+str(v) for k,v in unknown_commands.most_common()) or 'none')+' | requests repeated within one session: '+str(repeated))
    if fixed_own:
        print('Your frictions fixed by the kit: '+', '.join(fid+' in '+str(version) for fid, version in fixed_own.items()))
    print('Frictions logged: '+str(len(frictions))+(' ('+', '.join(k+' ×'+str(v) for k,v in frictions_by_category.most_common())+')' if frictions else '')+'; /friction to log one.')
    if not enough:
        print('Not enough data to recommend (threshold: '+str(min_sessions)+' sessions and '+str(min_prompts)+' prompts in the window; --min-sessions and --min-prompts to adjust it). No recommendation.')
    elif report['core_candidates_to_demote']:
        print('Candidates to remove from the core (never activated, not required by a used command): '+', '.join(report['core_candidates_to_demote']))
    else:
        print('No core skill to remove over this window.')
    print('Procedure: docs/usage-review.md. The logs read are local; nothing is sent.')
    if as_json:
        as_json.write_text(json_bytes(report).decode('utf-8'), encoding='utf-8')
    return 0

def release_check():
    """doctor --live: a newer published version of the kit (git tags of the kit folder's remote), without blocking anything."""
    if not (ROOT/'.git').exists() or not shutil.which('git'):
        return
    try:
        subprocess.run(['git', '-C', str(ROOT), 'fetch', '--tags', '--quiet'], capture_output=True, timeout=20)
        tags = subprocess.run(['git', '-C', str(ROOT), 'tag', '--list', 'v*', '--sort=-v:refname'], capture_output=True, text=True, timeout=10).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return
    current = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
    def key(version):
        return tuple(int(x) for x in re.findall(r'\d+', version)[:3])
    if tags and key(tags[0]) > key(current):
        print('[Info] AI Kit '+tags[0].lstrip('v')+' is published (this folder: '+current+'): run update, which fetches it.')

def live_checks(home, announce=False):
    """Real call to the model by each installed CLI that supports it (live); 1 if one does not answer."""
    code = 0
    for adapter in ADAPTERS:
        if isinstance(adapter, LiveCheck) and shutil.which(adapter.COMMAND):
            if announce:
                print('Checking with a real call to the model, '+adapter.LABEL+' (--no-live to skip):')
            code = max(code, adapter.live(home))
    return code

def resolve_identity(args, home, state):
    """Identity confirmed interactively, --user otherwise; never imposed."""
    if args.user:
        if not EMAIL.fullmatch(args.user):
            raise KitError('--user expects an email.')
        return {'email': args.user, 'source': 'option'}
    if args.action == 'update' and state.get('user'):
        return None
    detected = detect_identity(home)
    shown = detected.get('email') or detected.get('name')
    if not sys.stdin.isatty():
        if shown:
            print('Detected identity not confirmed: '+shown+'; use --user to record it.')
        return {}
    prompt = ('Detected identity: '+shown+' (source '+detected['source']+'). Press Enter to confirm, or type your email: ') if shown else 'Your work email (Enter to skip): '
    answer = input(prompt).strip()
    if not answer:
        return detected
    if not EMAIL.fullmatch(answer):
        raise KitError('Invalid email.')
    return {'email': answer, 'source': 'input'}

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')  # console that cannot encode a character: replace it rather than crash
        except (AttributeError, ValueError):
            pass
    if sys.version_info < (3,9):
        print('Python 3.9 minimum required (3.11 or newer recommended).',file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(prog='ai-kit' if _PACKAGE_DIR.name == 'ai_kit' else 'python3 -m installer', description='AI Kit — '+', '.join(a.LABEL for a in ADAPTERS)+'; Mac and Windows')
    parser.add_argument('action',choices=['setup','update','doctor','usage'])
    parser.add_argument('--since',type=int,default=42,help='usage: window in days (default 42)')
    parser.add_argument('--json',type=Path,help='usage: write the report to this file')
    parser.add_argument('--min-sessions',type=int,default=10,help='usage: minimum sessions before recommending (default 10)')
    parser.add_argument('--min-prompts',type=int,default=50,help='usage: minimum prompts before recommending (default 50)')
    parser.add_argument('--profile',choices=profile_ids())
    parser.add_argument('--user',help='Work email to record, without interactive confirmation')
    parser.add_argument('--home',type=Path,default=Path.home(),help='Alternative home folder for an isolated trial')
    parser.add_argument('--dry-run',action='store_true',help='Show the plan without writing')
    parser.add_argument('--team',help='setup: your team, when it has its own practices (practices/20-<team>.md); kept for update')
    parser.add_argument('--target',choices=list(TARGETS),default='auto',help='auto: the CLIs present on the machine (Gemini if none); gemini, agy, codex: that CLI only; both: Gemini and agy; all: every supported CLI')
    parser.add_argument('--live',action='store_true',help='doctor: make a real call to the model and diagnose')
    parser.add_argument('--no-live',action='store_true',help='setup/update: do not check with a real call to the model')
    args = parser.parse_args(argv)
    try:
        home = args.home.resolve()
        if args.action == 'doctor':
            code = doctor(home)
            if args.live:
                release_check()
                code = max(code, live_checks(home))
            return code
        if args.action == 'usage':
            return usage(home, args.since, args.json, args.min_sessions, args.min_prompts)
        if not args.dry_run:
            migrate_kit_dir(home)  # with --dry-run, apply announces it without renaming
        state = read_json(home/'.ai-kit/state.json') or read_json(home/LEGACY_KIT_DIR/'state.json')
        identity = resolve_identity(args, home, state)
        role = args.profile or state.get('profile')
        if not role:
            if args.action == 'update':
                raise KitError('Kit not installed: run setup.')
            if not sys.stdin.isatty():
                raise KitError('Specify --profile among: '+', '.join(profile_ids())+'.')
            choices = profile_menu()
            print('Welcome to the AI Kit\n'+'\n'.join(str(i+1)+'. '+label for i,(_,label) in enumerate(choices)))
            answer = input('Your profile [1-'+str(len(choices))+']: ').strip()
            if answer not in [str(i+1) for i in range(len(choices))]:
                raise KitError('Choose a number between 1 and '+str(len(choices))+'.')
            role = choices[int(answer)-1][0]
        team = args.team or state.get('team')
        if not team and args.action == 'setup' and team_ids() and sys.stdin.isatty():
            teams = team_ids()
            print('Teams with their own practices:\n'+'\n'.join(str(i+1)+'. '+t for i, t in enumerate(teams))+'\n'+str(len(teams)+1)+'. none of these (shared team practices)')
            answer = input('Your team [1-'+str(len(teams)+1)+'] (Enter = none): ').strip()
            if answer and answer not in [str(i+1) for i in range(len(teams)+1)]:
                raise KitError('Choose a number between 1 and '+str(len(teams)+1)+'.')
            team = teams[int(answer)-1] if answer and int(answer) <= len(teams) else None
        apply(role,home,args.dry_run,identity,args.target,team)
        for adapter in selected_adapters(args.target, home):
            if not shutil.which(adapter.COMMAND):
                print(adapter.LABEL+' not on the PATH: configuration ready; install and authenticate it following the IT procedure.')
        if not args.dry_run and not args.no_live and os.environ.get('AI_KIT_NO_LIVE') != '1' and live_checks(home, announce=True):
            print('Installation done, but the model does not answer yet: apply the fix above then run doctor --live again.')
        return 0
    except (KitError,OSError,UnicodeError) as exc:
        print('Error: '+str(exc),file=sys.stderr)
        return 2
    except (EOFError,KeyboardInterrupt):
        print('\nOperation cancelled.',file=sys.stderr)
        return 130
