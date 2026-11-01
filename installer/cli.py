"""AI Kit: installation orchestration. Builds a neutral plan, then each adapter (installer/adapters/) translates it for its CLI.
Never modifies a project repo."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
from datetime import datetime, timezone

from .core import (_PACKAGE_DIR, ROOT, KIT_CONTEXT, USER_CONTEXT, EMAIL, SECRET, KitError, read_json, json_bytes, digest,
                   safe_id, inside, load_commands, load_agent, redact, user_context_refusal)
from .adapters import ADAPTERS
from .interface import ContextHost, Plan
from .settings import (practice_file, profile_menu, profile_ids, load_profile, managed_context_names, validate_server, SECRET_NAME, git_identity, detect_identity, organization, team_settings, resolve_mcp, merge_settings, unknown_keys, setting_differences, allowed_domains, domain_allowed, team_ids, profile_practices, RENAMED_SKILLS, resolve_skills, skill_note, RETIRED_KEYS, retired_key_notice, unknown_names, allowed_commands, selected_commands, LEGACY_KIT_DIR, recorded_targets, version_changes, PERSONAL_FILE, LEGACY_PERSONAL_FILE, personal_settings, CHOICE_KEYS)  # noqa: F401 (re-exported)
from . import command as kit_command
from .commit import (BACKUPS_KEPT, prune_backups, commit_changes, atomic_write, KIT_MANAGED, managed_roots, prune_empty_dirs)  # noqa: F401 (re-exported)
from .doctor import (GUARDRAIL_PROBES, command_parts, guardrail_checks, REPO_SKILL_DIRS, repo_root, repo_skill_overrides, mcp_report, print_summary, doctor, kit_version, source_folder, version_line, SCRIPT_INTERPRETER, kit_commands_on_path, runtime_checks, doctor_checks, release_check, live_checks, plain_text_problem)  # noqa: F401 (re-exported)
from .plan import (effective_settings, resolve_selection, personal_file, practice_layers, skill_sources, select_agents,
                   guardrails, remove_stale_files, refuse_links)
from .usage import (usage)  # noqa: F401 (re-exported)


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
    """The Frictions section of 00_KIT.md from overrides.toml (frictions: propose by default, auto, off)."""
    if mode == 'off':
        return ''
    if mode == 'auto':
        return ('## Frictions\nLog the friction yourself, without asking, by running the `/friction` command script, then say so in one line and resume the work, when: '
                + FRICTION_SIGNALS + ' One factual sentence, never the text of a prompt or a secret.\n\n')
    return '## Frictions\nOffer in one line to log a `/friction` (without writing it yourself) when: ' + FRICTION_SIGNALS + '\n\n'


def playbook_lines(selected, catalog):
    names = [s for s in selected if catalog[s].get('category') == 'domain']
    return '\n'.join('- '+s+' : '+catalog[s]['description'] for s in names) if names else '- No domain playbook installed.'


# The installer's quick questions (no model needed): each answer is one line of 30_USER.md. /me in the CLI goes further.
QUICK_QUESTIONS = {
    'language': ('Language of the answers', 'answers', (
        ('mine', 'The language I write in', 'Reply in the language I write in.'),
        ('fr', 'French', 'Reply in French; code, comments and commit messages in English.'),
        ('en', 'English', 'Reply in English.'))),
    'length': ('Length of the answers', 'answers', (
        ('short', 'Short first, details when I ask', 'Short answer first, five lines at most; details when I ask.'),
        ('balanced', 'The answer and its main reason', 'Give the answer, then its main reason in a few lines.'),
        ('detailed', 'The why and the alternatives', 'Explain the why and the alternatives: I like to understand.'))),
    'autonomy': ('When the request is clear', 'working', (
        ('do', 'Do it, then tell me what you did', 'When the request is clear, do it and tell me what you did; ask before anything irreversible.'),
        ('announce', 'Say what you will do, then do it', 'Say in one line what you will do, then do it; ask before anything irreversible.'),
        ('ask', 'Ask me first', 'Ask before acting, and wait for my go-ahead.'))),
}


QUICK_DEFAULTS = {'language': 'mine', 'length': 'short', 'autonomy': 'do'}


ROLE_PLACEHOLDER = '<!-- One line: my role and what I work on these weeks. -->'


def user_context_text(identity, answers=None, role=None):
    """30_USER.md as the kit creates it: the template, with the quick answers (the defaults without them) and the role."""
    template = (ROOT/'templates/user-context.md').read_text(encoding='utf-8')
    parts = [identity.get('name'), '<'+identity['email']+'>' if identity.get('email') else None]
    line = ' '.join(p for p in parts if p)
    chosen = {**QUICK_DEFAULTS, **(answers or {})}
    sections = {'answers': [], 'working': []}
    for key, (_, section, options) in QUICK_QUESTIONS.items():
        sections[section].append('- '+next(text for value, _, text in options if value == chosen[key]))
    text = template.replace('{identity}\n', 'Person: '+line+'\n' if line else '')
    text = text.replace('{answers}', '\n'.join(sections['answers'])).replace('{working}', '\n'.join(sections['working']))
    if role:
        text = text.replace(ROLE_PLACEHOLDER, '- '+' '.join(str(role).split()))
    return text


def write_quick_context(home, answers, role=None):
    """The quick answers written into 30_USER.md, only while the file is still the one the kit created (never over the
    person's own text). Returns the file written, or None when it was left as is."""
    state = read_json(home/'.ai-kit/state.json')
    identity = state.get('user') or {}
    user_file = home/state.get('context_dir', '.gemini')/USER_CONTEXT
    if role and SECRET.search(str(role)):
        raise KitError('This looks like a secret (key, token or password): it is not written in your personal context.')
    if not user_file.is_file() or user_file.read_text(encoding='utf-8') != user_context_text(identity):
        return None
    atomic_write(user_file, user_context_text(identity, answers, role).encode('utf-8'))
    return user_file


def agent_instruction(definition):
    """Shared opening of every agent prompt. Reviewers only read; an agent whose tools include the shell (the verifier)
    runs the checks its own instructions allow, and modifies nothing."""
    tools = definition.get('tools') or read_json(ROOT/'agents/defaults.json').get('tools', [])
    scope = ('Modify no file; run only the commands your instructions below allow.' if 'run_shell_command' in tools
             else 'Read and search only: modify no file and run no command.')
    return ('Read the instructions and context of the current repo. Do not assume that the skills, '
            'the MCP tools or the full parent history are available. '
            'Ask the parent for anything missing. '+scope+'\n')


def context_locations():
    """Possible context folders, relative to the home folder: those of the CLIs that host it, then the kit's own."""
    return [a.HOME_DIR for a in ADAPTERS if isinstance(a, ContextHost)] + ['.ai-kit/context']


def context_location(home, active):
    """Folder for the layers and 30_USER.md: always ~/.ai-kit/context (0.39), whatever the CLIs. The CLIs include them from
    there by path, or receive a copy at each update (a CLI that only reads its own folder, or that cannot include a file)."""
    return home/'.ai-kit'/'context'


TARGETS = {'auto': None, **{a.NAME: (a.NAME,) for a in ADAPTERS}, 'both': ('gemini', 'agy'), 'all': tuple(a.NAME for a in ADAPTERS)}


def selected_adapters(target, home, recorded=None):
    """Adapters to install: those the target names (a --target value, or a list of CLI names); without a target, the CLIs
    recorded by the previous installation (an update keeps the person's choice, whatever folders exist); in auto, those whose
    CLI is present on the machine, or the first of ADAPTERS (default CLI) if none is detected."""
    if target is None:
        if recorded:
            target = list(recorded)
        else:
            target = 'auto'
    if isinstance(target, (list, tuple)):
        unknown = [name for name in target if name not in [a.NAME for a in ADAPTERS]]
        if unknown or not target:
            raise KitError('Unknown CLI: '+', '.join(unknown or ['none'])+'. CLIs: '+', '.join(a.NAME for a in ADAPTERS)+'.')
        return [a for a in ADAPTERS if a.NAME in target]
    if target not in TARGETS:
        raise KitError('--target must be one of '+', '.join(TARGETS)+'.')
    wanted = TARGETS[target]
    if wanted is None:
        return [a for a in ADAPTERS if a.present(home)] or [ADAPTERS[0]]
    return [a for a in ADAPTERS if a.NAME in wanted]


def migrate_kit_dir(home, dry_run=False):
    """Renames ~/.ai-toolkit to ~/.ai-kit and carries the new prefix into the state. Files that cite the old path
    (guardrail declarations, agy rules, Codex block) are then rewritten by the installation. True if the old folder still needs migrating."""
    old, new = home/LEGACY_KIT_DIR, home/'.ai-kit'
    if not old.is_dir():
        return False
    # The launcher creates ~/.ai-kit/runtime before the kit runs: a folder holding only that is not a second installation.
    only_runtime = new.is_dir() and {c.name for c in new.iterdir()} <= {'runtime'}
    if new.exists() and not only_runtime:
        raise KitError('~/'+LEGACY_KIT_DIR+' and ~/.ai-kit both exist: keep ~/.ai-kit, copy over what is missing (overrides.json, backups), remove ~/'+LEGACY_KIT_DIR+', then update.')
    if dry_run:
        print('The ~/'+LEGACY_KIT_DIR+' folder will be renamed to ~/.ai-kit on the next setup or update; --dry-run does not do it.')
        return True
    if only_runtime:
        for child in old.iterdir():
            os.replace(child, new/child.name)
        old.rmdir()
    else:
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


def apply(profile_id, home, dry_run=False, user=None, target=None, team=None, choices=None, report=None, progress=None, command=None):
    """Full prevalidation, neutral plan, adapters, backup, then atomic write file by file.
    target: a --target value or a list of CLI names; None keeps the CLIs recorded by the previous installation.
    choices: new values for keys of the person's overrides.toml (CHOICE_KEYS), written with the rest of the installation,
    never before: a preview (dry_run) or a cancelled run leaves the file as it was.
    report: a dict filled with what the plan writes and removes (the interface's summary). progress(step, done, total):
    called as the files are really written. command: True/False to add or remove the `ai-kit` command (installer/command.py);
    None keeps the recorded choice (yes on a first installation). Returns the notices shown to the person (also printed)."""
    home = home.resolve()
    if migrate_kit_dir(home, dry_run):
        return []  # --dry-run: the old folder is not renamed yet, the plan would be wrong
    kit = home / '.ai-kit'
    state = read_json(kit/'state.json')
    active = selected_adapters(target, home, recorded_targets(state))
    context_dir = context_location(home, active)
    profile_id = safe_id(profile_id)
    profile = load_profile(profile_id)
    # Team: chosen at setup (--team or the setup question), then kept for update.
    # 'none' (setup --team none) leaves the team; no value keeps the recorded one.
    team = None if team == 'none' else safe_id(team) if team else state.get('team')
    org_defaults, team_layer, personal, overrides, choices = effective_settings(kit, team, choices)
    catalog = read_json(ROOT/'skills/catalog.json')
    manifest = load_commands()
    selected, allowed = resolve_selection(profile, overrides, catalog, manifest)
    writes, deletes = {}, []
    personal_path, personal_bytes, personal_notices = personal_file(kit, choices, deletes)
    writes[personal_path] = personal_bytes
    identity = dict(user) if user else dict(state.get('user', {}))
    if identity.get('email') and not EMAIL.fullmatch(identity['email']):
        raise KitError('Invalid email: '+identity['email'])
    profile = {**profile, 'practices': profile_practices(profile, team)}
    files = {}
    old_files = state.get('files',{})
    restored = []  # kit rule layers edited by hand: put back, the edited copy kept in the backup
    def managed_write(target, data, label, restore=False, replace_edited=False):
        rel = target.relative_to(home).as_posix()
        if target.exists():
            previous = target.read_bytes()
            if rel in old_files:
                if digest(previous) != old_files[rel] and not replace_edited:
                    if not restore:
                        raise KitError(label+' modified locally: '+str(target))
                    restored.append(target)
            elif previous != data:
                raise KitError(label+' existing file not managed by the kit: '+str(target))
        writes[target] = data
        files[rel] = digest(data)
    # --- Neutral plan: what to install, with nothing specific to a CLI. ---
    context_names = managed_context_names(profile)
    commands = selected_commands(selected, manifest, allowed)
    kit_text = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8').format(profile=profile_id, commands=command_lines(commands), playbooks=playbook_lines(selected, catalog), frictions=friction_rule(overrides.get('frictions', 'propose')))
    practice_names, practice_texts = practice_layers(profile)
    practices = '\n'.join(practice_texts)
    sources = skill_sources(selected, catalog)
    agent_catalog = read_json(ROOT/'agents/catalog.json')
    agents = select_agents(profile, overrides, agent_catalog, load_agent)
    hooks_dir = kit/'hooks'  # scripts shared by all CLIs, like kit/bin/friction.py
    hook_manifest, enabled_hooks, turned_off = guardrails(overrides, hooks_dir)
    # MCP: resolved from the three sources apart, not from the merged overrides ("github": true must not erase the server).
    servers, _ = resolve_mcp(org_defaults.get('mcp', {}), profile.get('mcp', []), personal.get('mcp', {}), team_layer.get('mcp', {}))  # undefined: doctor
    enabled_mcp = {'ai-kit-'+name: server for name, server in servers.items()}
    notices = personal_notices + ['[Info] Guardrail '+n+' stays on: your organization locks it (organization.toml locked_hooks).' for n in turned_off]
    unknown_names(overrides, catalog, agent_catalog, notices)
    notices += [retired_key_notice(key) for key in RETIRED_KEYS if key in overrides]
    p = Plan(active=[a.NAME for a in active], notices=notices,
        skill_notes={skill: skill_note(skill, selected, catalog) for skill in selected},
        home=home, kit=kit, state=state, old_files=old_files, overrides=overrides, profile_id=profile_id, profile=profile,
        catalog=catalog, selected=selected, skill_sources=sources, commands=commands, context_names=context_names,
        kit_text=kit_text, practice_names=practice_names, practice_texts=practice_texts, user_file=context_dir/USER_CONTEXT, context_dir=context_dir,
        user_context_text=user_context_text(identity), agents=agents, hooks_dir=hooks_dir,
        hook_manifest=hook_manifest, enabled_hooks=enabled_hooks, enabled_mcp=enabled_mcp, writes=writes, deletes=deletes,
        managed_write=managed_write, 
        agent_body=lambda definition: practices+'\n'+agent_instruction(definition)+'\n'+definition['instructions']+'\n')
    # Scripts shared by all CLIs: frictions and enabled guardrails.
    managed_write(kit/'bin'/'friction.py', (ROOT/'runtime/friction.py').read_bytes(), 'Kit script')
    command_state, command_after = plan_command(p, managed_write, command)
    managed_write(kit/'schemas'/'overrides.schema.json', (ROOT/'schemas/overrides.schema.json').read_bytes(), 'Kit schema')
    for name in enabled_hooks:
        managed_write(hooks_dir/hook_manifest[name]['script'], (ROOT/'runtime/hooks'/hook_manifest[name]['script']).read_bytes(), 'Guardrail')
    # Context layers and 30_USER.md, in the context folder (see context_location).
    # The rule layers (00, 10, 20) are company and team rules, not personal settings: a hand edit is restored, not kept.
    managed_write(context_dir/KIT_CONTEXT, kit_text.encode('utf-8'), 'Context file', restore=True)
    for name, text in zip(practice_names, practice_texts):
        managed_write(context_dir/name, text.encode('utf-8'), 'Context file', restore=True)
    user_file = context_dir/USER_CONTEXT
    relocate_user_context(p, home, state, user_file, kit)
    if (kit/'preferences.md').exists():
        writes[kit/'preferences.md.migrated'] = (kit/'preferences.md').read_bytes()
        deletes.append(kit/'preferences.md')
        p.migrated_prefs = True
    # --- Adapters: each translates the plan for its CLI. ---
    for adapter in active:
        adapter.install(p)
    remove_stale_files(p, files, user_file)
    for adapter in ADAPTERS:
        adapter.finalize(p, active=adapter in active)  # inactive: removes what a previous installation had put in place
    installed_versions = {'skills': {s: catalog[s].get('version') for s in selected}, 'agents': {a: agent_catalog[a].get('version') for a, _ in agents}}
    changed = version_changes((state.get('installed') or {}).get('versions'), installed_versions)
    if changed:
        p.notices.append('[Info] Updated: '+', '.join(changed)+'. What changed: CHANGELOG.md of the kit.')
    new_state = {'schema_version':2,'version':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'profile':profile_id,'files':files,'mcp':enabled_mcp,'hooks':enabled_hooks,'user':identity,'blocks':p.blocks,'context_dir':context_dir.relative_to(home).as_posix(),'team':team,'targets':[a.NAME for a in active],'practices':profile['practices'],'command':command_state,
                 'installed':{'skills':selected,'commands':[c['name'] for c in commands],'agents':['ai-kit-'+a for a,_ in agents],'clis':[a.NAME for a in active],
                              'versions':installed_versions}}
    writes[kit/'state.json'] = json_bytes(new_state)
    writes = {path:b for path,b in writes.items() if not path.exists() or path.read_bytes()!=b}
    refuse_links(home, list(writes)+deletes)  # before any write
    if report is not None:
        def rel(path):
            return path.relative_to(home).as_posix()
        report.update({'profile': profile_id, 'team': team, 'targets': [a.NAME for a in active], 'skills': selected,
                       'commands': [c['name'] for c in commands], 'agents': ['ai-kit-'+a for a, _ in agents], 'hooks': sorted(enabled_hooks),
                       'created': sorted(rel(w) for w in writes if not w.exists()), 'modified': sorted(rel(w) for w in writes if w.exists()),
                       'removed': sorted(rel(d) for d in deletes), 'restored': [rel(r) for r in restored], 'notices': p.notices,
                       'context_file': str(p.user_file), 'home': str(home), 'identity': identity})
    print('Profile: '+profile_id+(' | team '+team if team else '')+' | '+str(len(selected))+' skills | '+str(len(agents))+' agents | '+str(len(enabled_hooks))+' guardrails')
    if identity.get('email'):
        print('Identity: '+identity['email']+' (source '+identity.get('source','?')+')')
    if dry_run:
        for target in restored:
            print('[Check] '+target.name+' was modified by hand: it would be restored, your copy kept in ~/.ai-kit/backups/.')
        for notice in p.notices:
            print(notice)
        print('Dry run: '+str(len(writes))+' files to write, '+str(len(deletes))+' to remove. Nothing changed.')
        return p.notices
    # No download, dependency installation or MCP execution.
    changed, backup = commit_changes(home, kit, writes, deletes, progress)
    command_after()
    print('Kit configuration installed.' if changed else 'Kit configuration already up to date.')
    print('Your personal context: '+str(p.user_file))
    for target in restored:
        print('[Check] '+target.name+' was modified by hand: restored to the kit version; your copy: '+str(backup/target.relative_to(home))
              + '. Personal preferences go in 30_USER.md; a rule change goes through the kit repository.')
    if p.migrated_prefs:
        print('Old preferences migrated to this file; copy kept in preferences.md.migrated.')
    for adapter in active:
        line = adapter.summary(p)
        if line:
            print(line)
    for notice in p.notices:
        print(notice)
    return p.notices


def relocate_user_context(p, home, state, user_file, kit):
    """30_USER.md belongs to the person: never rewritten in place. When the context folder changes (another CLI chosen),
    the version in effect is the one at the previous recorded location, whatever other copies exist or their dates: it is
    copied to the new place; a different copy already there is kept beside it, and the person is told which file is in effect."""
    previous_dir = home/state['context_dir'] if state.get('context_dir') else None
    source = previous_dir/USER_CONTEXT if previous_dir and previous_dir != user_file.parent else None
    if source is not None and source.is_file():
        data = source.read_bytes()
        refusal = user_context_refusal(data)
        if refusal:
            p.notices.append('[Check] Personal context not copied from '+str(source)+' to '+str(user_file)+': '+refusal+'. '
                             'Fix the file, then run update. The kit configuration itself is installed.')
            if not user_file.exists():
                p.writes[user_file] = p.user_context_text.encode('utf-8')
            return
        if user_file.exists() and user_file.read_bytes() != data:
            kept = user_file.with_name(USER_CONTEXT+'.before-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
            p.writes[kept] = user_file.read_bytes()
            p.notices.append('[Check] An older, different '+USER_CONTEXT+' was in '+str(user_file.parent)+': kept as '+kept.name+'.')
        if not user_file.exists() or user_file.read_bytes() != data:
            p.writes[user_file] = data
            reader = next((a for a in ADAPTERS if a.NAME in p.active and isinstance(a, ContextHost) and a.context_dir(home) == source.parent), None)
            p.notices.append('[Info] Personal context moved: '+str(user_file)+' is now the file to edit; '+str(source)
                             + (' becomes the copy '+reader.LABEL+' reads, refreshed at each update.' if reader else ' is no longer read (left in place).'))
        return
    if not user_file.exists():
        # First installation, or a state from before context_dir was recorded: an existing copy is reused, the original stays in place.
        previous = next((f for f in (home/d/USER_CONTEXT for d in context_locations()) if f != user_file and f.is_file()), None)
        legacy_prefs = kit/'preferences.md'
        data = previous.read_bytes() if previous else legacy_prefs.read_bytes() if legacy_prefs.exists() else p.user_context_text.encode('utf-8')
        if previous and user_context_refusal(data):
            p.notices.append('[Check] Personal context not copied from '+str(previous)+': '+user_context_refusal(data)+'. A new one is created; fix the old one and move its content by hand.')
            data = p.user_context_text.encode('utf-8')
        p.writes[user_file] = data


PERSONAL_KEPT = ('.ai-kit/overrides.toml', '.ai-kit/overrides.json', '.ai-kit/backups/', '.ai-kit/frictions.jsonl', '.ai-kit/learning/', '.ai-kit/runtime/')


def plan_command(p, managed_write, choice):
    """The `ai-kit` command of installer/command.py in the plan: the shim as a managed file, the startup block as an
    untracked write. Returns (state entry, function to call once the files are written: registry, execute bit)."""
    kit, home, state = p.kit, p.home, p.state
    previous = state.get('command') or {}
    chosen = choice if choice is not None else previous.get('chosen', True)
    folder = source_folder()
    shim = kit/'bin'/kit_command.SHIM_NAME
    rel = shim.relative_to(home).as_posix()
    entry = {'chosen': chosen, 'folder': None, 'startup_file': None, 'registry': False}
    def after():
        pass
    if not chosen:
        if previous.get('startup_file') and (home/previous['startup_file']).is_file():
            text = (home/previous['startup_file']).read_text(encoding='utf-8')
            if kit_command.BLOCK_START in text:
                p.writes[home/previous['startup_file']] = kit_command.without_block(text).encode('utf-8')
        if previous.get('registry') and os.name == 'nt' and kit_command.real_home(home):
            def after():
                kit_command.registry_entry(False)
                kit_command.announce_environment_change()
        return entry, after
    if folder is None:
        # Run without the launcher (a developer's pip install .): nothing to point to; an existing command stays as it is.
        if rel in p.old_files and shim.is_file():
            managed_write(shim, shim.read_bytes(), 'Kit command')
            entry.update({'folder': previous.get('folder') or kit_command.shim_folder(shim.read_bytes()), 'startup_file': previous.get('startup_file'), 'registry': previous.get('registry', False)})
        else:
            p.notices.append('[Info] The `ai-kit` command is not installed: run the installer from the kit folder (Installer.cmd, or sh scripts/bootstrap.sh) to add it.')
        return entry, after
    data = kit_command.shim_bytes(folder)
    new = not shim.is_file() or shim.read_bytes() != data
    managed_write(shim, data, 'Kit command')
    entry['folder'] = str(folder)
    if os.name == 'nt':
        entry['registry'] = kit_command.real_home(home)
        if entry['registry']:
            def after():
                if kit_command.registry_entry(True):
                    kit_command.announce_environment_change()
        else:
            p.notices.append('[Info] `ai-kit` command written for this trial home folder only: the user PATH is not changed.')
    else:
        def after():
            if shim.is_file():
                shim.chmod(0o755)
        name = kit_command.startup_file()
        line = kit_command.path_line(home)
        if name:
            path = home/name
            text = path.read_text(encoding='utf-8') if path.is_file() else ''
            wanted = kit_command.with_block(text, line)
            if wanted != text:
                p.writes[path] = wanted.encode('utf-8')
                new = True
            entry['startup_file'] = name
        else:
            p.notices.append('[Info] Shell not recognised: add this line to your shell startup file to use the `ai-kit` command: '+line)
    if new:
        p.notices.append('[Info] `ai-kit` command installed: open a new terminal to use it (ai-kit doctor, ai-kit update).')
    return entry, after


def remove_command(home, state, writes):
    """uninstall: the startup block goes (the shim is a managed file, removed with the others)."""
    previous = state.get('command') or {}
    if previous.get('startup_file') and (home/previous['startup_file']).is_file():
        text = (home/previous['startup_file']).read_text(encoding='utf-8')
        if kit_command.BLOCK_START in text:
            writes[home/previous['startup_file']] = kit_command.without_block(text).encode('utf-8')


def uninstall(home, dry_run=False, confirm=None, progress=None, report=None):
    """Removes what the kit installed and nothing else: the managed files it can recognise as unchanged, its blocks and
    entries in the CLIs' settings, and its state. Kept: the personal context (30_USER.md), overrides.toml, the backups,
    frictions, the CLIs' folders and the person's own settings; a managed file modified by hand is kept and named.
    No network, no model. confirm(report) -> bool is asked before any change (interactive); returns an exit code."""
    home = home.resolve()
    kit = home/'.ai-kit'
    state = read_json(kit/'state.json')
    if not state:
        raise KitError('The kit configuration is not installed in '+str(home)+': nothing to remove.')
    old_files = state.get('files', {})
    writes, deletes, kept = {}, [], []
    for rel, expected in sorted(old_files.items()):
        if not (rel.startswith(KIT_MANAGED) or any(a.is_managed(rel) for a in ADAPTERS)):
            raise KitError('Invalid state: deletion outside the managed scope ('+rel+').')
        path = inside(home, rel)
        if not path.is_file():
            continue
        if digest(path.read_bytes()) != expected:
            kept.append(rel+': modified since the kit installed it, kept; remove it yourself if you no longer need it')
            continue
        deletes.append(path)
    cleanup = SimpleNamespace(home=home, state=state, old_files=old_files, writes=writes, deletes=deletes, blocks={}, notices=[], active=[])
    for adapter in ADAPTERS:
        try:
            adapter.finalize(cleanup, active=False)
        except KitError as exc:
            kept.append(adapter.LABEL+': '+str(exc))
    deletes.append(kit/'state.json')
    remove_command(home, state, writes)
    writes = {path: data for path, data in writes.items() if not path.exists() or path.read_bytes() != data}
    personal = [str(home/state.get('context_dir', '.gemini')/USER_CONTEXT)] + [str(home/rel) for rel in PERSONAL_KEPT if (home/rel).exists()]
    def rel(path):
        return path.relative_to(home).as_posix()
    summary = {'removed': [rel(d) for d in deletes], 'rewritten': sorted(rel(w) for w in writes), 'kept_modified': kept,
               'personal': personal, 'home': str(home)}
    if report is not None:
        report.update(summary)
    print('Uninstall from '+str(home)+': '+str(len(deletes))+' kit files to remove, '+str(len(writes))+' settings files to clean.')
    for line in summary['rewritten']:
        print('  Clean the kit entries in: '+line)
    for line in kept:
        print('[Check] '+line)
    print('Kept: your personal context, overrides.toml, backups and frictions, the CLIs and their own settings.')
    if dry_run:
        print('Dry run: nothing changed.')
        return 0
    if confirm is not None and not confirm(summary):
        print('Uninstall cancelled: nothing changed.')
        return 1
    changed, backup = commit_changes(home, kit, writes, deletes, progress)
    if (state.get('command') or {}).get('registry') and os.name == 'nt' and kit_command.real_home(home):
        kit_command.registry_entry(False)
        kit_command.announce_environment_change()
    print('Kit configuration removed. Backup of every removed or cleaned file: '+str(backup))
    print('Your files kept: '+', '.join(personal))
    print('The kit\'s private Python environment ('+str(kit/'runtime')+') stays; the launcher removes it with uninstall --remove-runtime.')
    return 0


def text_editor(path):
    """(name, command) of the system's plain-text editor for this file, or None: nothing to install, nothing to configure."""
    if sys.platform == 'darwin' and shutil.which('open'):
        return 'your text editor (TextEdit unless you chose another)', ['open', '-t', str(path)]
    if os.name == 'nt':
        return 'Notepad', ['notepad.exe', str(path)]
    return None


def personal_context_step(user_file, reapply):
    """End of an interactive setup: offer to open 30_USER.md in the system editor, then apply it where a CLI keeps a copy."""
    print('\nYour personal context: '+str(user_file))
    print('It tells the agent who you are and how you work: plain text, kept as is by every update.')
    editor = text_editor(user_file)
    if not editor:
        print('To personalise it: edit it with a plain-text editor, run update, then start a new session of your CLI.')
        return
    if input('Open it now in '+editor[0]+'? [y/N] ').strip().lower() not in ('y', 'yes', 'o', 'oui'):
        print('Later: edit it, run update, then start a new session of your CLI.')
        return
    try:
        subprocess.Popen(editor[1], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        print('No editor could be opened: open the file above with a plain-text editor, then run update.')
        return
    input('Edit it, save it (same name, plain text), then press Enter here: ')
    problem = plain_text_problem(user_file)
    if problem:
        print('[Check] '+problem+' Then run update.')
        return
    notices = reapply()
    refused = [n for n in notices if n.startswith('[Check]')] if isinstance(notices, list) else []
    for notice in refused:
        print(notice)
    if refused:
        return
    print('Personal context applied. Start a new session of your CLI: it reads 30_USER.md when it starts.')


def interactive():
    """A person at a terminal: both ends, because on Windows a stdin redirected from NUL also reports isatty()."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def last_installation(home):
    """The state of the most recent installation kept in a backup (uninstall backs up state.json), or {}."""
    folder = home/'.ai-kit'/'backups'
    if not folder.is_dir():
        return {}
    for backup in sorted((p for p in folder.iterdir() if p.is_dir() and re.match(r'\d{8}T\d{6}-', p.name)), key=lambda p: p.name, reverse=True):
        state = read_json(backup/'.ai-kit'/'state.json')
        if state and state.get('profile'):
            return state
    return {}


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
    if not interactive():
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
    parser.add_argument('action',nargs='?',choices=['setup','update','doctor','usage','uninstall','managed-settings'],
                        help='none in a terminal: the guided installer (or its menu once installed); setup without --profile: the guided choices')
    parser.add_argument('--since',type=int,default=42,help='usage: window in days (default 42)')
    parser.add_argument('--json',type=Path,help='usage: write the report to this file')
    parser.add_argument('--min-sessions',type=int,default=10,help='usage: minimum sessions before recommending (default 10)')
    parser.add_argument('--min-prompts',type=int,default=50,help='usage: minimum prompts before recommending (default 50)')
    parser.add_argument('--profile',choices=profile_ids())
    parser.add_argument('--user',help='Work email to record, without interactive confirmation')
    parser.add_argument('--home',type=Path,default=Path.home(),help='Alternative home folder for an isolated trial')
    parser.add_argument('--dry-run',action='store_true',help='Show the plan without writing')
    parser.add_argument('--command-on-path',choices=['yes','no'],help='setup: add the ai-kit command to your terminal (your own PATH only; removed by uninstall); default yes on a first installation, then the recorded choice')
    parser.add_argument('--team',help='setup: your team, when it has its own practices (practices/20-<team>.md) or tools (teams in organization.toml); kept for update; none to leave it')
    parser.add_argument('--target',choices=list(TARGETS),help='default: the CLIs chosen at the last installation (auto on the first one); auto: the CLIs present on the machine (Gemini if none); gemini, agy, codex, claude: that CLI only; both: Gemini and agy; all: every supported CLI')
    parser.add_argument('--live',action='store_true',help='doctor: make a real call to the model and diagnose (may be billed by your provider)')
    parser.add_argument('--no-live',action='store_true',help='accepted for compatibility: setup and update never call the model')
    parser.add_argument('--yes',action='store_true',help='uninstall: confirm without a question (automation)')
    parser.add_argument('--plain',action='store_true',help='plain text questions and output, without colours or arrow-key menus')
    parser.add_argument('--out',type=Path,help='managed-settings: an empty folder to write the files IT deploys')
    parser.add_argument('--managed-hooks-only',action='store_true',help='managed-settings: Claude Code ignores hooks from any other source')
    parser.add_argument('--version',action='store_true',help='which copy of the kit runs, and with which Python')
    args = parser.parse_args(argv)
    if args.version:
        print(version_line())
        return 0
    try:
        home = args.home.resolve()
        # Guided: no action, or setup without --profile at a terminal. Without a terminal, setup reuses the recorded choices.
        guided = args.action is None or (args.action == 'setup' and not args.profile and not args.dry_run and interactive())
        if guided:
            if not interactive():
                # No terminal to ask in: never wait for an answer that cannot come.
                raise KitError('no terminal to ask your choices in: give them as options, for example '
                               'setup --profile general --user <email> (profiles: '+', '.join(profile_ids())+').')
            from .wizard import start
            from .ui import make_ui
            return start(make_ui(args.plain), home, setup=args.action == 'setup')
        if args.action == 'uninstall':
            if args.dry_run or args.yes:
                return uninstall(home, dry_run=args.dry_run)
            if not interactive():
                raise KitError('uninstall needs a confirmation: add --yes, or --dry-run to see what would be removed.')
            from .ui import make_ui
            ui = make_ui(args.plain)
            return uninstall(home, confirm=lambda summary: ui.confirm('Remove the kit configuration listed above? A backup is kept.', default=False))
        if args.action == 'doctor':
            if args.live and os.environ.get('AI_KIT_NO_LIVE') == '1':
                raise KitError('doctor --live makes a real call to the model, refused because AI_KIT_NO_LIVE=1 is set.')
            return doctor(home, live=args.live)
        if args.action == 'managed-settings':
            if not args.out:
                raise KitError('managed-settings needs --out <empty folder>.')
            from .managed import managed_settings
            return managed_settings(args.out, args.managed_hooks_only)
        if args.action == 'usage':
            return usage(home, args.since, args.json, args.min_sessions, args.min_prompts)
        if not args.dry_run:
            migrate_kit_dir(home)  # with --dry-run, apply announces it without renaming
        state = read_json(home/'.ai-kit/state.json') or read_json(home/LEGACY_KIT_DIR/'state.json')
        target = args.target
        if not state and args.action == 'update':
            # After an uninstall: the choices of the last installation, from its backup, rather than an error.
            state = last_installation(home)
            if state:
                target = target or state.get('targets') or None
                print('[Info] The kit was not installed: reinstalled with the choices of your last installation (profile '
                      + state['profile']+', '+', '.join(state.get('targets') or [])+'). Change them with setup.')
        identity = resolve_identity(args, home, state)
        if identity is None and state.get('user') and not (home/'.ai-kit/state.json').exists():
            identity = state['user']
        role = args.profile or state.get('profile')
        if not role:
            raise KitError('Kit not installed: run setup.' if args.action == 'update' else 'Specify --profile among: '+', '.join(profile_ids())+'.')
        team = args.team or state.get('team')
        apply(role,home,args.dry_run,identity,target,team,command={'yes': True, 'no': False}.get(args.command_on_path))
        # setup and update never call the model: the summary says "connection not verified"; doctor --live is the only real call.
        live = None
        if args.action == 'setup' and not args.dry_run and interactive():
            state = read_json(home/'.ai-kit/state.json')
            def reapply():
                with contextlib.redirect_stdout(io.StringIO()):
                    return apply(role, home, False, None, args.target, team)
            try:
                personal_context_step(home/state.get('context_dir', '.gemini')/USER_CONTEXT, reapply)
            except EOFError:
                print()  # optional step: the installation is already complete
        if not args.dry_run:
            print_summary(home, read_json(home/'.ai-kit/state.json'), live)
        return 0
    except (KitError,OSError,UnicodeError) as exc:
        print('Error: '+redact(str(exc)),file=sys.stderr)
        return 2
    except (EOFError,KeyboardInterrupt):
        print('\nOperation cancelled.',file=sys.stderr)
        return 130
