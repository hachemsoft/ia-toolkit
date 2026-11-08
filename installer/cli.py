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
from datetime import datetime, timezone

from .core import (content_root, STATE_SCHEMA, check_state_schema, _PACKAGE_DIR, ROOT, KIT_CONTEXT, USER_CONTEXT, EMAIL, SECRET, KitError, friction_module, news_module, is_guardrail, read_json, json_bytes, digest,
                   safe_id, load_commands, load_agent, redact, user_context_refusal)
from .adapters import ADAPTERS
from .interface import ContextHost, Plan
from .settings import (practice_file, profile_menu, profile_ids, load_profile, managed_context_names, validate_server, SECRET_NAME, git_identity, detect_identity, organization, team_settings, resolve_mcp, merge_settings, unknown_keys, setting_differences, allowed_domains, domain_allowed, team_ids, profile_practices, RENAMED_SKILLS, resolve_skills, skill_note, RETIRED_KEYS, retired_key_notice, unknown_names, allowed_commands, selected_commands, LEGACY_KIT_DIR, recorded_targets, version_changes, PERSONAL_FILE, LEGACY_PERSONAL_FILE, personal_settings, CHOICE_KEYS, friction_tracker)  # noqa: F401 (re-exported)
from .console import styled_output
from .commit import (BACKUPS_KEPT, prune_backups, commit_changes, atomic_write, KIT_MANAGED, managed_roots, prune_empty_dirs)  # noqa: F401 (re-exported)
from .doctor import (GUARDRAIL_PROBES, command_parts, guardrail_checks, REPO_SKILL_DIRS, repo_root, repo_skill_overrides, mcp_report, print_summary, doctor, kit_version, source_folder, version_line, SCRIPT_INTERPRETER, kit_commands_on_path, runtime_checks, doctor_checks, release_check, live_checks, plain_text_problem)  # noqa: F401 (re-exported)
from .plan import (RENAMED_HOOKS, effective_settings, resolve_selection, personal_file, practice_layers, skill_sources, select_agents,
                   guardrails, remove_stale_files, refuse_links)
from .usage import (usage)  # noqa: F401 (re-exported)
from .config import (ManagedConfigError, load_managed, apply_values, locked_guardrails, filter_mcp, publication, managed_digest, AIKIT_FILE, check_source, load_aikit, aikit_from_overrides)  # noqa: F401 (re-exported)
from .lifecycle import (PERSONAL_KEPT, plan_command, remove_command, uninstall)  # noqa: F401 (re-exported)


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
        return ('## Frictions\nLog the friction yourself, without asking, by running the `/friction` command script with `--source agent`, then say so in one line and resume the work, when: '
                + FRICTION_SIGNALS + ' One factual sentence, never the text of a prompt, a secret, a name of a person or a client.\n\n')
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
    tools = definition.get('tools') or read_json(content_root()/'agents/defaults.json').get('tools', [])
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


def apply(profile_id, home, dry_run=False, user=None, target=None, team=None, choices=None, report=None, progress=None, command=None, managed_file=None, extra_writes=None):
    """Full prevalidation, neutral plan, adapters, backup, then atomic write file by file.
    target: a --target value or a list of CLI names; None keeps the CLIs recorded by the previous installation.
    choices: new values for keys of the person's overrides.toml (CHOICE_KEYS), written with the rest of the installation,
    never before: a preview (dry_run) or a cancelled run leaves the file as it was.
    report: a dict filled with what the plan writes and removes (the interface's summary). progress(step, done, total):
    called as the files are really written. command: True/False to add or remove the `ai-kit` command (installer/command.py);
    None keeps the recorded choice (yes on a first installation). managed_file: the managed.toml to read instead of the administered
    path (tests only; never taken from the environment). Returns the notices shown to the person (also printed)."""
    home = home.resolve()
    if migrate_kit_dir(home, dry_run):
        return []  # --dry-run: the old folder is not renamed yet, the plan would be wrong
    kit = home / '.ai-kit'
    state = read_json(kit/'state.json')
    check_state_schema(state, kit/'state.json')
    check_source(content_root(), (ROOT/'VERSION').read_text(encoding='utf-8').strip())  # min_engine of the content (2.0)
    active = selected_adapters(target, home, recorded_targets(state))
    context_dir = context_location(home, active)
    profile_id = safe_id(profile_id)
    profile = load_profile(profile_id)
    # Team: chosen at setup (--team or the setup question), then kept for update.
    # 'none' (setup --team none) leaves the team; no value keeps the recorded one.
    team = None if team == 'none' else safe_id(team) if team else state.get('team')
    org_defaults, team_layer, personal, overrides, choices = effective_settings(kit, team, choices)
    # managed.toml (IT): every key it sets wins over the organization, the team and the person (ADR 0015).
    hook_specs = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
    managed = load_managed(managed_file, [n for n, s in hook_specs.items() if is_guardrail(s)])
    overrides, managed_notices = apply_values(overrides, managed)
    catalog = read_json(content_root()/'skills/catalog.json')
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
    kit_text = (content_root()/'templates/kit-context.md').read_text(encoding='utf-8').format(profile=profile_id, commands=command_lines(commands), playbooks=playbook_lines(selected, catalog), frictions=friction_rule(overrides.get('frictions', 'propose')))
    practice_names, practice_texts = practice_layers(profile)
    practices = '\n'.join(practice_texts)
    sources = skill_sources(selected, catalog)
    agent_catalog = read_json(content_root()/'agents/catalog.json')
    agents = select_agents(profile, overrides, agent_catalog, load_agent)
    hooks_dir = kit/'hooks'  # scripts shared by all CLIs, like kit/bin/friction.py
    hook_manifest, enabled_hooks, turned_off = guardrails(overrides, hooks_dir, locked_guardrails(managed), [n for n, v in (managed or {}).get('hooks', {}).items() if v is False])
    news = news_setting(overrides)
    kit_dir = kit_folder()
    # MCP: resolved from the three sources apart, not from the merged overrides ("github": true must not erase the server).
    servers, _ = resolve_mcp(org_defaults.get('mcp', {}), profile.get('mcp', []), personal.get('mcp', {}), team_layer.get('mcp', {}))  # undefined: doctor
    enabled_mcp, mcp_notices = filter_mcp({'ai-kit-'+name: server for name, server in servers.items()}, managed)
    aikit_notices = load_aikit(kit/AIKIT_FILE)[1] if (kit/AIKIT_FILE).exists() else []
    notices = personal_notices + aikit_notices + managed_notices + mcp_notices + ['[Info] Guardrail '+n+' stays on: your organization or IT locks it (organization.toml locked_hooks, managed.toml hooks.locked).' for n in turned_off]
    notices += ['[Info] hooks.'+old+' is now hooks.'+new+': your setting is applied; rename it in your overrides.toml.' for old, new in RENAMED_HOOKS.items() if old in (overrides.get('hooks') or {})]
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
    managed_write(kit/'bin'/'news.py', (ROOT/'runtime/news.py').read_bytes(), 'Kit script')
    command_state, command_after = plan_command(p, managed_write, command)
    managed_write(kit/'schemas'/'overrides.schema.json', (ROOT/'schemas/overrides.schema.json').read_bytes(), 'Kit schema')
    if (kit/AIKIT_FILE).exists():  # 2.0: the schema the person's aikit.toml points to
        managed_write(kit/'schemas'/'aikit.schema.json', (ROOT/'schemas/aikit.schema.json').read_bytes(), 'Kit schema')
    for name in enabled_hooks:
        managed_write(hooks_dir/hook_manifest[name]['script'], (ROOT/'runtime/hooks'/hook_manifest[name]['script']).read_bytes(), 'Guardrail' if is_guardrail(hook_manifest[name]) else 'Kit hook')
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
    tracker = friction_tracker(org_defaults_root(), personal)
    if tracker:
        # approval (default): nothing is sent on its own; the person sends from a terminal (ai-kit friction --sync). D5, ADR 0023.
        tracker = None if publication(managed) == 'disabled' else {**tracker, 'publication': publication(managed)}
    if org_defaults_root().get('friction_tracker') and tracker is None:
        p.notices.append('[Info] Frictions stay local: share_frictions = false in your overrides.toml (your organization set a friction tracker).')
    new_state = {'schema_version':STATE_SCHEMA,'version':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'profile':profile_id,'files':files,'mcp':enabled_mcp,'hooks':enabled_hooks,'user':identity,'blocks':p.blocks,'context_dir':context_dir.relative_to(home).as_posix(),'team':team,'targets':[a.NAME for a in active],'practices':profile['practices'],'command':command_state,'news':news,**({'managed':{'digest':managed_digest(managed_file)}} if managed is not None else {}),**({'kit_dir': kit_dir} if kit_dir else {}),**({'friction_tracker': tracker} if tracker else {}),
                 'installed':{'skills':selected,'commands':[c['name'] for c in commands],'agents':['ai-kit-'+a for a,_ in agents],'clis':[a.NAME for a in active],
                              'versions':installed_versions}}
    # V2 slice 2: lock.toml (written by sync and rollback) goes in the same transaction as the files it describes; its digest
    # in state.json lets doctor see a hand edit.
    lock_bytes = (extra_writes or {}).get(kit/'lock.toml')
    if lock_bytes is not None or state.get('lock'):
        new_state['lock'] = digest(lock_bytes) if lock_bytes is not None else state['lock']
    writes.update(extra_writes or {})
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
    print('Profile: '+profile_id+(' | team '+team if team else '')+' | '+str(len(selected))+' skills | '+str(len(agents))+' agents | '+str(sum(1 for n in enabled_hooks if is_guardrail(hook_manifest[n])))+' guardrails')
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


def migrate_config(home, dry_run=False):
    """overrides.toml -> aikit.toml (2.0), once: overrides.toml is kept as it is (AI Kit 0.52 reads it after a return), and
    is no longer read once aikit.toml exists. Prints where each setting went."""
    kit = home/'.ai-kit'
    if (kit/AIKIT_FILE).exists():
        print('[Info] ~/.ai-kit/aikit.toml already exists: nothing to migrate.')
        return
    text, report = aikit_from_overrides(personal_settings(kit), (kit/'schemas'/'aikit.schema.json').as_uri())
    print('Migration of your settings to ~/.ai-kit/aikit.toml'+(' (preview, nothing written)' if dry_run else '')+':')
    for line in report or ['nothing to carry over: aikit.toml starts empty']:
        print('  '+line)
    if not dry_run:
        refuse_links(home, [kit/AIKIT_FILE])
        kit.mkdir(parents=True, exist_ok=True)
        atomic_write(kit/AIKIT_FILE, text.encode('utf-8'))
        print('[OK] ~/.ai-kit/aikit.toml written; overrides.toml is kept for AI Kit 0.52 and no longer read.')


def org_defaults_root():
    """The whole organization.toml (friction_tracker is a top-level table, not a default)."""
    return organization()


FRICTION_MODES = ('propose', 'auto', 'off')


def news_setting(overrides):
    """[news] of the merged settings, for state.json: check_remote (the whats-new hook reads the kit's remote once a day), true by default."""
    news = overrides.get('news', {})
    if not isinstance(news, dict) or not isinstance(news.get('check_remote', True), bool) or any(k not in ('check_remote',) for k in news):
        raise KitError('news must be a table with check_remote = true or false.')
    return {'check_remote': news.get('check_remote', True)}


def kit_folder():
    """The kit folder the whats-new hook reads (git fetch): the one the launcher runs from, else this clone; none for a pip install."""
    folder = os.environ.get('AI_KIT_SOURCE_DIR')
    if folder:
        return folder
    return str(ROOT) if (ROOT/'.git').exists() else None


def news_action(argv):
    """ai-kit news: the script the agent runs on a refused update (runtime/news.py, one implementation) run from the
    terminal, with --home: --later, --list, --check."""
    parser = argparse.ArgumentParser(prog='ai-kit news', add_help=False)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--plain', action='store_true')
    args, rest = parser.parse_known_args(argv)
    return news_module().main([*rest, '--home', str(args.home.resolve())])


def new_action(argv):
    """ai-kit new: a component of the kit, in its clone (installer/new.py)."""
    from .new import main as new_main
    return new_main(argv, repo=kit_folder())


def friction_action(argv):
    """ai-kit friction: the /friction script itself (runtime/friction.py, one implementation) run from the terminal,
    with --home; --list for the last frictions; --mode [propose|auto|off] to show or change the frictions setting of
    overrides.toml, then reapply the agents' context (the rule lives in 00_KIT.md)."""
    parser = argparse.ArgumentParser(prog='ai-kit friction', add_help=False)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--mode', nargs='?', const='', default=None)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--plain', action='store_true')
    args, rest = parser.parse_known_args(argv)
    home = args.home.resolve()
    if args.mode is None:
        return friction_module().main([*rest, '--home', str(home)])
    state = read_json(home/'.ai-kit/state.json')
    if not state:
        raise KitError('Kit not installed: run setup.')
    org_defaults, team_layer, personal, overrides, _ = effective_settings(home/'.ai-kit', state.get('team'), None)
    current = overrides.get('frictions', 'propose')
    origin = ('your overrides.toml' if 'frictions' in personal else 'your team' if 'frictions' in team_layer
              else "your organization's defaults" if 'frictions' in org_defaults else 'kit default')
    if args.mode == '':
        print('Frictions mode: '+current+' ('+origin+').')
        print('propose: the agent offers /friction on a friction signal and you confirm. auto: it logs the friction itself and says so in one line. off: no friction rule.')
        print('Change it: ai-kit friction --mode <propose|auto|off>. Log one now: ai-kit friction --category <'+'|'.join(friction_module().CATEGORIES)+'> --text "<one sentence>".')
        return 0
    if args.mode not in FRICTION_MODES:
        raise KitError('frictions must be propose, auto or off (given: '+args.mode+').')
    if args.mode == 'auto' and not args.yes and interactive():
        from .ui import make_ui
        if not make_ui(args.plain).confirm('In auto mode the agent writes a friction line itself, without asking, on each friction signal (one factual sentence, locally, nothing sent). Switch to auto?', default=False):
            print('Nothing changed: frictions mode stays '+current+'.')
            return 1
    with contextlib.redirect_stdout(io.StringIO()):
        apply(state['profile'], home, False, None, None, state.get('team'), choices={'frictions': args.mode})
    print('Frictions mode: '+args.mode+' (your overrides.toml); the agents\' context is updated. Start a new session of your CLI.')
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
    if sys.version_info < (3,11):
        print('Python 3.11 minimum required (AI Kit 2.0; workstations on Python 3.9 or 3.10 stay on AI Kit 0.52).',file=sys.stderr)
        return 2
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ('friction', 'news', 'new'):
        # The /friction and news scripts, and new, from the terminal: their own options. Colour as for the other actions.
        with styled_output(plain='--plain' in argv):
            try:
                return {'friction': friction_action, 'news': news_action, 'new': new_action}[argv[0]](argv[1:])
            except (KitError, OSError, UnicodeError) as exc:
                print('Error: '+redact(str(exc)), file=sys.stderr)
                return 3 if isinstance(exc, ManagedConfigError) else 2  # 3: managed.toml cannot be applied (ADR 0015)
            except (EOFError, KeyboardInterrupt):
                print('\nOperation cancelled.', file=sys.stderr)
                return 130
            except SystemExit as exc:  # the script's own argparse: usage already printed
                return exc.code if isinstance(exc.code, int) else 2
    parser = argparse.ArgumentParser(prog='ai-kit' if _PACKAGE_DIR.name == 'ai_kit' else 'python3 -m installer', description='AI Kit — '+', '.join(a.LABEL for a in ADAPTERS)+'; Mac and Windows')
    parser.add_argument('action',nargs='?',choices=['setup','update','sync','rollback','doctor','usage','uninstall','managed-settings','friction','news','new'],
                        help='none in a terminal: the guided installer (or its menu once installed); setup without --profile: the guided choices; sync: install the highest stable tag of your Core source (--dry-run to preview); rollback: back to the previous Core; friction: log a friction (--category, --text), --list the last ones, --mode [propose|auto|off]; news: what the kit announced at session start (--list), --later to refuse a proposed update, --check to read the kit remote now; new: create a skill, an agent, a command or a profile in a clone of the kit')
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
    parser.add_argument('--managed-mcp-only',action='store_true',help='managed-settings: Claude Code and Codex CLI allow only the MCP servers organization.toml defines')
    parser.add_argument('--version',action='store_true',help='which copy of the kit runs, and with which Python')
    parser.add_argument('--migrate-config',action='store_true',help='update: write ~/.ai-kit/aikit.toml (AI Kit 2) from your overrides.toml, which stays as it is for AI Kit 0.52, and say where each setting went')
    args = parser.parse_args(argv)
    if args.action == 'new':  # an option before it: the early branch of new did not see it; never fall through to apply
        parser.error('write the options after it: ai-kit new <type> ...')
    if args.version:
        print(version_line())
        return 0
    # Colour by prefix for the command-line actions; the guided screens have their own interface (installer/console.py).
    guided_screen = args.action is None or (args.action == 'setup' and not args.profile and not args.dry_run)
    with styled_output(plain=args.plain or guided_screen):
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
                return managed_settings(args.out, args.managed_hooks_only, args.managed_mcp_only)
            if args.action == 'usage':
                return usage(home, args.since, args.json, args.min_sessions, args.min_prompts)
            if args.migrate_config:
                if args.action != 'update':
                    raise KitError('--migrate-config goes with update: ai-kit update --migrate-config.')
                migrate_config(home, args.dry_run)
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
                raise KitError('Kit not installed: run setup.' if args.action in ('update', 'sync', 'rollback') else 'Specify --profile among: '+', '.join(profile_ids())+'.')
            team = args.team or state.get('team')
            # V2 slice 2: the content is the locked Core when one is synced; sync and rollback change it (lock.toml in the same transaction).
            from .sync import activation
            hook_specs = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
            def confirm(question):
                if not interactive():
                    return False
                from .ui import make_ui
                return make_ui(args.plain).confirm(question, default=False)
            with activation(home, args.action, args.dry_run, confirm, guardrail_names=[n for n, s in hook_specs.items() if is_guardrail(s)]) as extra:
                apply(role,home,args.dry_run,identity,target,team,command={'yes': True, 'no': False}.get(args.command_on_path), extra_writes=extra)
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
            return 3 if isinstance(exc, ManagedConfigError) else 2  # 3: managed.toml cannot be applied (ADR 0015)
        except (EOFError,KeyboardInterrupt):
            print('\nOperation cancelled.',file=sys.stderr)
            return 130
