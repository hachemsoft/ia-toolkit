"""AI Kit: installation orchestration. Builds a neutral plan, then each adapter (installer/adapters/) translates it for its CLI.
Never modifies a project repo."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

from . import resolve
from .core import (content_root, STATE_SCHEMA, check_state_schema, _PACKAGE_DIR, ROOT, KIT_CONTEXT, USER_CONTEXT, EMAIL, SECRET, KitError, friction_module, is_guardrail, read_json, json_bytes, digest,
                   safe_id, load_commands, load_agent, redact, user_context_refusal)
from .adapters import ADAPTERS
from .interface import ContextHost, Plan
from .settings import (CORE_SELECTION, core_selection, context_folder, practice_file, managed_context_names, validate_server, SECRET_NAME, git_identity, detect_identity, organization, team_settings, resolve_mcp, merge_settings, unknown_keys, setting_differences, resolve_skills, skill_note, unknown_names, allowed_commands, selected_commands, recorded_targets, version_changes, PERSONAL_FILE, personal_settings, CHOICE_KEYS, friction_tracker)  # noqa: F401 (re-exported)
from .console import styled_output
from .commit import (BACKUPS_KEPT, prune_backups, commit_changes, atomic_write, KIT_MANAGED, managed_roots, prune_empty_dirs)  # noqa: F401 (re-exported)
from .doctor import (GUARDRAIL_PROBES, command_parts, guardrail_checks, REPO_SKILL_DIRS, repo_root, repo_skill_overrides, mcp_report, print_summary, doctor, kit_version, source_folder, version_line, SCRIPT_INTERPRETER, kit_commands_on_path, runtime_checks, doctor_checks, release_check, live_checks, plain_text_problem)  # noqa: F401 (re-exported)
from .plan import (effective_settings, resolve_selection, personal_file, practice_layers, skill_sources, select_agents,
                   guardrails, remove_stale_files, refuse_links)
from .usage import (usage)  # noqa: F401 (re-exported)
from .toml_files import parse_toml, read_toml, set_section_key  # noqa: F401 (also re-exported)
from .v2_commands import core_synced, resource_sources, user_edit, sync_configured  # noqa: F401 (re-exported)
from .config import (team_mcp_gate, ManagedConfigError, load_managed, apply_values, locked_guardrails, filter_mcp, publication, managed_digest, AIKIT_FILE, check_source, load_aikit)  # noqa: F401 (re-exported)
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
    """The Frictions section of 00_KIT.md from aikit.toml (frictions: propose by default, auto, off)."""
    if mode == 'off':
        return ''
    if mode == 'auto':
        return ('## Frictions\nLog the friction yourself, without asking, by running the `/friction` command script with `--source agent`, then say so in one line and resume the work, when: '
                + FRICTION_SIGNALS + ' One factual sentence, never the text of a prompt, a secret, a name of a person or a client.\n\n')
    return '## Frictions\nOffer in one line to log a `/friction` (without writing it yourself) when: ' + FRICTION_SIGNALS + '\n\n'


def playbook_lines(selected, catalog):
    names = [s for s in selected if catalog[s].get('category') == 'domain']
    return '\n'.join('- '+s+' : '+catalog[s]['description'] for s in names) if names else '- No domain playbook installed.'


# The installer's quick questions (no model needed): each answer is one line of USER.md. /me in the CLI goes further.
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
    """USER.md as the kit creates it: the template, with the quick answers (the defaults without them) and the role."""
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
    """The quick answers written into USER.md, only while the file is still the one the kit created (never over the
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
    """Folder for the layers and USER.md: always ~/.ai-kit/context (0.39), whatever the CLIs. The CLIs include them from
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


def apply(profile_id, home, dry_run=False, user=None, target=None, team=None, choices=None, report=None, progress=None, command=None, managed_file=None, extra_writes=None):
    """Full prevalidation, neutral plan, adapters, backup, then atomic write file by file.
    target: a --target value or a list of CLI names; None keeps the CLIs recorded by the previous installation.
    choices: new values for keys of the person's aikit.toml (CHOICE_KEYS), written with the rest of the installation,
    never before: a preview (dry_run) or a cancelled run leaves the file as it was.
    report: a dict filled with what the plan writes and removes (the interface's summary). progress(step, done, total):
    called as the files are really written. command: True/False to add or remove the `ai-kit` command (installer/command.py);
    None keeps the recorded choice (yes on a first installation). managed_file: the managed.toml to read instead of the administered
    path (tests only; never taken from the environment). Returns the notices shown to the person (also printed)."""
    home = home.resolve()
    kit = home / '.ai-kit'
    # V2: with a Core or a Team synced, every installation (the guided installer, a re-apply) uses the locked content, never the
    # package's; sync, team use and rollback pass their own content and writes (extra_writes).
    first_shipped = SHIPPED[0] is not None and not read_toml(kit/'lock.toml', {}).get('sources')
    if extra_writes is None and (first_shipped or (content_root() == ROOT and read_toml(kit/'lock.toml', {}).get('sources'))):
        from .sync import activation
        # 2.2: a first installation from the release ZIP activates the Core it ships (lock.toml written with the files).
        with activation(home, 'sync' if first_shipped else 'update', dry_run, managed_file=managed_file,
                        bundle=SHIPPED[0] if first_shipped else None, shipped=first_shipped) as act:
            return apply(profile_id, home, dry_run, user, target, act.team or team, choices, report, progress, command, managed_file, act.writes)
    state = read_json(kit/'state.json')
    check_state_schema(state, kit/'state.json')
    check_source(content_root(), (ROOT/'VERSION').read_text(encoding='utf-8').strip())  # min_engine of the content (2.0)
    active = selected_adapters(target, home, recorded_targets(state))
    context_dir = context_location(home, active)
    # 2.2: no profiles (ADR 0018): the Core default selection; profile_id is kept for the callers of the V1 API, never read.
    profile_id = CORE_SELECTION
    profile = core_selection()
    # Team: chosen at setup (--team or the setup question), then kept for update.
    # 'none' (setup --team none) leaves the team; no value keeps the recorded one.
    team = None if team == 'none' else safe_id(team) if team else state.get('team')
    org_defaults, team_layer, personal, overrides, choices = effective_settings(kit, team, choices)
    # managed.toml (IT): every key it sets wins over the organization, the team and the person (ADR 0015).
    hook_specs = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
    managed = load_managed(managed_file, [n for n, s in hook_specs.items() if is_guardrail(s)])
    overrides, managed_notices = apply_values(overrides, managed)
    catalog = resolve.skill_catalog(content_root())
    manifest = load_commands()
    selected, allowed = resolve_selection(profile, overrides, catalog, manifest)
    writes, deletes = {}, []
    personal_path, personal_bytes, personal_notices = personal_file(kit, choices, deletes)
    writes[personal_path] = personal_bytes
    identity = dict(user) if user else dict(state.get('user', {}))
    if identity.get('email') and not EMAIL.fullmatch(identity['email']):
        raise KitError('Invalid email: '+identity['email'])
    if team and (context_folder()/('20-'+team+'.md')).is_file():
        profile = {**profile, 'practices': ['company', team]}  # the active Team's context replaces the default team layer
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
    agent_catalog = resolve.agent_catalog(content_root())
    agents = select_agents(profile, overrides, agent_catalog, load_agent)
    hooks_dir = kit/'hooks'  # scripts shared by all CLIs, like kit/bin/friction.py
    hook_manifest, enabled_hooks, turned_off = guardrails(overrides, hooks_dir, locked_guardrails(managed), [n for n, v in (managed or {}).get('hooks', {}).items() if v is False])
    kit_dir = kit_folder()
    # MCP: resolved from the three sources apart, not from the merged overrides ("github": true must not erase the server).
    servers, _ = resolve_mcp(org_defaults.get('mcp', {}), profile.get('mcp', []), personal.get('mcp', {}), team_layer.get('mcp', {}))  # undefined: doctor
    enabled_mcp, mcp_notices = filter_mcp({'ai-kit-'+name: server for name, server in servers.items()}, managed)
    team_servers = {n: e.get('server', {}) for n, e in (team_layer.get('mcp') or {}).items() if isinstance(e, dict) and e.get('team')}
    enabled_mcp, team_notices, mcp_approvals = team_mcp_gate(enabled_mcp, team_servers, managed, state.get('mcp_approvals'), APPROVE[0])
    mcp_notices += team_notices
    aikit_notices = load_aikit(kit/AIKIT_FILE)[1] if (kit/AIKIT_FILE).exists() else []  # unknown keys
    notices = personal_notices + aikit_notices + managed_notices + mcp_notices + ['[Info] Guardrail '+n+' stays on: your organization or IT locks it (managed.toml hooks.locked).' for n in turned_off]
    unknown_names(overrides, catalog, agent_catalog, notices)
    p = Plan(active=[a.NAME for a in active], notices=notices,
        skill_notes={skill: skill_note(skill, selected, catalog) for skill in selected},
        home=home, kit=kit, state=state, old_files=old_files, overrides=overrides,
        catalog=catalog, selected=selected, skill_sources=sources, commands=commands, context_names=context_names,
        kit_text=kit_text, practice_names=practice_names, practice_texts=practice_texts, user_file=context_dir/USER_CONTEXT, context_dir=context_dir,
        user_context_text=user_context_text(identity), agents=agents, hooks_dir=hooks_dir,
        hook_manifest=hook_manifest, enabled_hooks=enabled_hooks, enabled_mcp=enabled_mcp, writes=writes, deletes=deletes,
        managed_write=managed_write, 
        agent_body=lambda definition: practices+'\n'+agent_instruction(definition)+'\n'+definition['instructions']+'\n')
    # Scripts shared by all CLIs: frictions and enabled guardrails.
    managed_write(kit/'bin'/'friction.py', (ROOT/'runtime/friction.py').read_bytes(), 'Kit script')
    # What the session hook announces: the active content's CHANGELOG and NEWS, copied (no network at session start).
    for name in ('CHANGELOG.md', 'NEWS.md'):
        source = content_root()/name if (content_root()/name).is_file() else ROOT/name
        if source.is_file():
            managed_write(kit/'news'/name, source.read_bytes(), 'Kit news')
    command_state, command_after = plan_command(p, managed_write, command)
    managed_write(kit/'schemas'/'aikit.schema.json', (ROOT/'schemas/aikit.schema.json').read_bytes(), 'Kit schema')  # what aikit.toml points to
    for name in enabled_hooks:
        managed_write(hooks_dir/hook_manifest[name]['script'], (ROOT/'runtime/hooks'/hook_manifest[name]['script']).read_bytes(), 'Guardrail' if is_guardrail(hook_manifest[name]) else 'Kit hook')
    # Context layers and USER.md, in the context folder (see context_location).
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
    tracker = friction_tracker(personal, managed)
    if tracker:
        # approval (default): nothing is sent on its own; the person sends from a terminal (ai-kit friction --sync). D5, ADR 0023.
        tracker = None if publication(managed) == 'disabled' else {**tracker, 'publication': publication(managed)}
    if ((managed or {}).get('frictions') or {}).get('tracker') and tracker is None:
        p.notices.append('[Info] Frictions stay local: frictions.publication = "disabled" in your aikit.toml (your organization set a friction tracker).')
    new_state = {'schema_version':STATE_SCHEMA,'version':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'profile':profile_id,'files':files,'mcp':enabled_mcp,'hooks':enabled_hooks,'user':identity,'blocks':p.blocks,'context_dir':context_dir.relative_to(home).as_posix(),'team':team,'targets':[a.NAME for a in active],'practices':profile['practices'],'command':command_state,'frictions_retention':(managed or {}).get('frictions', {}).get('retention_days', 30),**({'mcp_approvals':mcp_approvals} if mcp_approvals else {}),**({'managed':{'digest':managed_digest(managed_file)}} if managed is not None else {}),**({'kit_dir': kit_dir} if kit_dir else {}),**({'friction_tracker': tracker} if tracker else {}),
                 'installed':{'sources':resource_sources(selected, catalog, agents, agent_catalog, core_synced(kit, extra_writes)),'skills':selected,'commands':[c['name'] for c in commands],'agents':['ai-kit-'+a for a,_ in agents],'clis':[a.NAME for a in active],
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
    print('Core selection'+(' | team '+team if team else '')+' | '+str(len(selected))+' skills | '+str(len(agents))+' agents | '+str(sum(1 for n in enabled_hooks if is_guardrail(hook_manifest[n])))+' guardrails')
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
              + '. Personal preferences go in USER.md; a rule change goes through the kit repository.')
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
    """USER.md belongs to the person: never rewritten in place. When the context folder changes (another CLI chosen),
    the version in effect is the one at the previous recorded location, whatever other copies exist or their dates: it is
    copied to the new place; a different copy already there is kept beside it, and the person is told which file is in effect."""
    previous_dir = home/state['context_dir'] if state.get('context_dir') else None
    source = previous_dir/USER_CONTEXT if previous_dir and previous_dir != user_file.parent else None
    if source is not None and source.is_file():
        data = source.read_bytes()
        refusal = user_context_refusal(data)
        if refusal:
            p.notices.append('[Check] Personal context not copied from '+str(source)+' to '+str(user_file)+': '+refusal+'. '
                             'Fix the file, then run ai-kit sync --offline. The kit configuration itself is installed.')
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


def org_defaults_root():
    """The Core's settings (its MCP servers)."""
    return organization()


FRICTION_MODES = ('propose', 'auto', 'off')


def kit_folder():
    """The kit folder the whats-new hook reads (git fetch): the one the launcher runs from, else this clone; none for a pip install."""
    folder = os.environ.get('AI_KIT_SOURCE_DIR')
    if folder:
        return folder
    return str(ROOT) if (ROOT/'.git').exists() else None


def friction_action(argv):
    """ai-kit friction: the /friction script itself (runtime/friction.py) from the terminal, with --home. --list shows the last
    frictions; --publish sends the waiting ones to the tracker IT set (the person's act, refused to the agent). How the agent
    captures frictions is the frictions.capture key of aikit.toml (or managed.toml)."""
    parser = argparse.ArgumentParser(prog='ai-kit friction', add_help=False)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--publish', action='store_true')
    args, rest = parser.parse_known_args(argv)
    return friction_module().main([*rest, *(['--sync'] if args.publish else []), '--home', str(args.home.resolve())])


def text_editor(path):
    """(name, command) of the system's plain-text editor for this file, or None: nothing to install, nothing to configure."""
    if sys.platform == 'darwin' and shutil.which('open'):
        return 'your text editor (TextEdit unless you chose another)', ['open', '-t', str(path)]
    if os.name == 'nt':
        return 'Notepad', ['notepad.exe', str(path)]
    return None


def interactive():
    """A person at a terminal: both ends, because on Windows a stdin redirected from NUL also reports isatty()."""
    return sys.stdin.isatty() and sys.stdout.isatty()


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
    if argv and argv[0] == 'friction':
        # The /friction script from the terminal: its own options.
        with styled_output(plain='--plain' in argv):
            try:
                return friction_action(argv[1:])
            except (KitError, OSError, UnicodeError) as exc:
                print('Error: '+redact(str(exc)), file=sys.stderr)
                return 3 if isinstance(exc, ManagedConfigError) else 1  # 3: managed.toml cannot be applied (ADR 0015)
            except (EOFError, KeyboardInterrupt):
                print('\nOperation cancelled.', file=sys.stderr)
                return 130
            except SystemExit as exc:  # the script's own argparse: usage already printed
                return exc.code if isinstance(exc.code, int) else 2
    # 2.2: the package holds only the engine; the content of this run comes from the clone, the locked Core, the Core the
    # release ZIP ships, or the launcher's folder (installer/bootstrap.py).
    home_arg = next((argv[i+1] for i, a in enumerate(argv[:-1]) if a == '--home'), None) or next((a.split('=', 1)[1] for a in argv if a.startswith('--home=')), None)
    from .bootstrap import run_content
    try:
        content = run_content(Path(home_arg).expanduser().resolve() if home_arg else Path.home())
        shipped = content.__enter__()
    except (KitError, OSError) as exc:
        print('Error: '+redact(str(exc)), file=sys.stderr)
        return 3 if isinstance(exc, ManagedConfigError) else 2
    SHIPPED[0] = shipped
    try:
        return command_main(argv)
    finally:
        SHIPPED[0] = None
        content.__exit__(None, None, None)


APPROVE = [None]  # a question for a Team's local MCP server, set by the command line when a person is at a terminal
SHIPPED = [None]  # the Core bundle the release ZIP ships, while a first installation must activate it


def command_main(argv):
    """The AI Kit 3 command line (ADR 0025, docs/v2/cli.md). Exit codes: 0 success, 1 refused or failed (nothing changed, or all
    restored), 2 usage, 3 administered configuration unusable, 130 interrupted."""
    parser = argparse.ArgumentParser(prog='ai-kit' if _PACKAGE_DIR.name == 'ai_kit' else 'python3 -m installer', description='AI Kit — '+', '.join(a.LABEL for a in ADAPTERS)+'; Mac and Windows')
    parser.add_argument('action', nargs='?', choices=['init', 'sync', 'team', 'status', 'doctor', 'rollback', 'user', 'uninstall', 'usage', 'friction', 'managed-settings', 'validate'],
                        help='init: install, or check and re-apply; sync: the highest stable tag of your Core and Team (--dry-run, --offline: re-apply without network, --from-bundle FILE); '
                             'team list | team use <name> [--url URL] | team use none; status [--verbose]; doctor [--live]; rollback; user edit; uninstall; usage; '
                             'friction --list | --publish; managed-settings --out FOLDER; validate [--path FOLDER]. No action: status.')
    parser.add_argument('rest', nargs='*', help='team: list, or use <name>; user: edit')
    parser.add_argument('--home', type=Path, default=Path.home(), help='Alternative home folder for an isolated trial')
    parser.add_argument('--user', help='init: the work email to record, without a question')
    parser.add_argument('--target', choices=list(TARGETS), help='init: the CLIs to configure (default: those recorded, else the ones present; auto, gemini, agy, codex, claude, both, all)')
    parser.add_argument('--command-on-path', choices=['yes', 'no'], help='init: add the ai-kit command to your terminal (your own PATH only); default yes the first time')
    parser.add_argument('--dry-run', action='store_true', help='init, sync, uninstall: show what would change, write nothing')
    parser.add_argument('--offline', action='store_true', help='sync: re-apply the locked Core and Team from the cache, without network')
    parser.add_argument('--from-bundle', type=Path, help='sync: the Core from a git bundle file (offline), as the release ZIP ships it')
    parser.add_argument('--url', help='team use: the repository URL of a Team not known yet')
    parser.add_argument('--verbose', action='store_true', help='status: where each setting comes from, installed resources, capabilities')
    parser.add_argument('--live', action='store_true', help='doctor: a real call to the model (may be billed); needs --yes without a terminal')
    parser.add_argument('--yes', action='store_true', help='uninstall, doctor --live: confirm without a question')
    parser.add_argument('--plain', action='store_true', help='plain text questions and output, without colours')
    parser.add_argument('--out', type=Path, help='managed-settings: an empty folder to write the files IT deploys')
    parser.add_argument('--managed-hooks-only', action='store_true', help='managed-settings: Claude Code ignores hooks from any other source')
    parser.add_argument('--managed-mcp-only', action='store_true', help='managed-settings: Claude Code and Codex CLI allow only the MCP servers the Core defines')
    parser.add_argument('--path', type=Path, help='validate: the Core or Team repository to check (default: the kit content)')
    parser.add_argument('--since', type=int, default=42, help='usage: window in days (default 42)')
    parser.add_argument('--json', type=Path, help='usage: write the report to this file')
    parser.add_argument('--min-sessions', type=int, default=10, help='usage: minimum sessions before recommending (default 10)')
    parser.add_argument('--min-prompts', type=int, default=50, help='usage: minimum prompts before recommending (default 50)')
    parser.add_argument('--version', action='store_true', help='which copy of the kit runs, and with which Python')
    args = parser.parse_args(argv)
    if args.rest and args.action not in ('team', 'user'):
        parser.error('unexpected argument: '+' '.join(args.rest))
    if (args.offline or args.from_bundle) and args.action != 'sync':
        parser.error('--offline and --from-bundle go with sync')
    if args.offline and args.from_bundle:
        parser.error('--offline re-applies what is installed; --from-bundle installs a Core: choose one')
    if args.version:
        print(version_line())
        return 0
    with styled_output(plain=args.plain):
        try:
            home = args.home.resolve()
            if args.action in (None, 'status'):
                from .status import status
                code = status(home, args.verbose)
                if args.action is None:
                    print('Commands: ai-kit init, sync, team, status, doctor, rollback, user edit, uninstall, usage, friction, managed-settings, validate (ai-kit --help).')
                return code
            if args.action == 'uninstall':
                if args.dry_run or args.yes:
                    return uninstall(home, dry_run=args.dry_run)
                if not interactive():
                    raise UsageError('uninstall needs a confirmation: add --yes, or --dry-run to see what would be removed.')
                from .ui import make_ui
                ui = make_ui(args.plain)
                return uninstall(home, confirm=lambda summary: ui.confirm('Remove the kit configuration listed above? A backup is kept.', default=False))
            if args.action == 'doctor':
                if args.live and os.environ.get('AI_KIT_NO_LIVE') == '1':
                    raise KitError('doctor --live makes a real call to the model, refused because AI_KIT_NO_LIVE=1 is set.')
                if args.live and not args.yes and not interactive():
                    raise UsageError('doctor --live makes a real call to the model: add --yes to confirm without a terminal.')
                return doctor(home, live=args.live)
            if args.action == 'managed-settings':
                if not args.out:
                    raise UsageError('managed-settings needs --out <empty folder>.')
                from .managed import managed_settings
                return managed_settings(args.out, args.managed_hooks_only, args.managed_mcp_only)
            if args.action == 'validate':
                from .validate import validate
                return validate(args.path or content_root(), (ROOT/'VERSION').read_text(encoding='utf-8').strip())
            if args.action == 'user':
                if args.rest != ['edit']:
                    raise UsageError('user needs: user edit.')
                return user_edit(home, interactive())
            if args.action == 'team' and args.rest[:1] == ['list']:
                from .sync import team_list
                return team_list(home)
            if args.action == 'team' and (args.rest[:1] != ['use'] or len(args.rest) != 2):
                raise UsageError('team needs: team list, team use <name> [--url <URL>], or team use none.')
            if args.action == 'usage':
                return usage(home, args.since, args.json, args.min_sessions, args.min_prompts)
            state = read_json(home/'.ai-kit/state.json')
            if not state and args.action != 'init':
                raise KitError('Kit not installed: run ai-kit init.')
            identity = resolve_identity(args, home, state)
            from .sync import activation
            hook_specs = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
            def confirm(question):
                if not interactive():
                    return False
                from .ui import make_ui
                return make_ui(args.plain).confirm(question, default=False)
            def ask_url(name):
                if not interactive():
                    return None
                from .ui import make_ui
                return make_ui(args.plain).text('Repository URL of the Team '+name+' (https://... or git@...)') or None
            locked = bool(read_toml(home/'.ai-kit/lock.toml', {}).get('sources'))
            APPROVE[0] = confirm if interactive() else None
            first_shipped = SHIPPED[0] is not None and not locked and args.action in ('init', 'sync')
            if args.action == 'team':
                action = 'team-use'
            elif args.action == 'rollback':
                action = 'rollback'
            elif args.action == 'sync':
                action = 'update' if args.offline else 'sync'
            else:  # init: a first installation syncs its Core (the shipped one, or the source set); later, it re-applies
                action = 'sync' if first_shipped or (not locked and sync_configured(home)) else 'update'
            with activation(home, action, args.dry_run, confirm, guardrail_names=[n for n, s in hook_specs.items() if is_guardrail(s)],
                            team_name=args.rest[1] if args.action == 'team' else None, team_url=args.url, ask_url=ask_url,
                            bundle=args.from_bundle or (SHIPPED[0] if first_shipped else None), shipped=first_shipped) as act:
                apply(CORE_SELECTION, home, args.dry_run, identity, args.target, act.team or state.get('team'),
                      command={'yes': True, 'no': False}.get(args.command_on_path), extra_writes=act.writes)
            if not args.dry_run:
                print_summary(home, read_json(home/'.ai-kit/state.json'), None)
            return 0
        except UsageError as exc:
            print('Error: '+redact(str(exc)), file=sys.stderr)
            return 2
        except ManagedConfigError as exc:
            print('Error: '+redact(str(exc)), file=sys.stderr)
            return 3  # managed.toml cannot be applied (ADR 0015)
        except (KitError, OSError, UnicodeError) as exc:
            print('Error: '+redact(str(exc)), file=sys.stderr)
            return 1  # refused or failed: nothing changed, or everything was put back
        except (EOFError, KeyboardInterrupt):
            print('\nOperation cancelled.', file=sys.stderr)
            return 130


class UsageError(KitError):
    """A command used the wrong way (exit code 2)."""
