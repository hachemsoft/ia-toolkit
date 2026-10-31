"""Guided installer: what a person sees when they start the kit without options. It shows the workstation, asks the
choices, shows what will change, and only then calls the engine (cli.apply, cli.uninstall, cli.doctor): there is no
second installation logic here. Nothing is applied before "Install"; the model is never called unless the person picks
the dedicated, billed check."""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys

from . import cli
from .adapters import ADAPTERS
from .core import ROOT, EMAIL, KitError, read_json, load_commands
from .ui import Cancelled


def quietly(function, *args, **kwargs):
    """Runs an engine function, its printed lines captured (the interface shows them its own way): (result, lines)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = function(*args, **kwargs)
    return result, [line for line in out.getvalue().splitlines()]


# The engine's messages name command-line actions; in the menu, the same actions are menu choices.
MENU_WORDS = ((re.compile(r'\brun doctor again\b'), 'choose "Check the installation" again in this menu'),
              (re.compile(r'\b(?:then )?run update\b'), lambda m: ('then ' if m.group(0).startswith('then') else '')+'choose "Update" in this menu'),
              (re.compile(r'\brun doctor --live\b'), 'choose the Advanced check in this menu'))

def menu_wording(lines):
    out = []
    for line in lines:
        for pattern, words in MENU_WORDS:
            line = pattern.sub(words, line)
        out.append(line)
    return out


def kit_version():
    return (ROOT/'VERSION').read_text(encoding='utf-8').strip()


def workstation(ui, home, state):
    rows = [('Python', sys.version.split()[0], 'ok')]
    for adapter in ADAPTERS:
        found = shutil.which(adapter.COMMAND)
        rows.append((adapter.LABEL, 'found' if found else 'not found on this workstation', 'ok' if found else 'missing'))
    rows.append(('AI Kit', 'installed: version '+str(state.get('version'))+', profile '+str(state.get('profile')) if state else 'not installed yet',
                 'ok' if state else 'info'))
    rows.append(('Connection to the model', 'not checked: the installer never calls the model', 'info'))
    ui.table('This workstation', rows)


def choose_targets(ui, home, state):
    recorded = cli.recorded_targets(state)
    default = list(recorded) if recorded else [a.NAME for a in cli.selected_adapters('auto', home)]
    choices = []
    for adapter in ADAPTERS:
        found = shutil.which(adapter.COMMAND)
        note = ' (found)' if found else ' (not found: configuration prepared for when IT installs it)'
        choices.append((adapter.NAME, adapter.LABEL+note, adapter.NAME in default))
    return ui.checkbox('Which CLIs do you use?', choices, minimum=1)


def profiles():
    """(id, name, short description), in the profiles' order."""
    out = []
    for profile_id, label in cli.profile_menu():
        name, _, description = label.partition(':')
        out.append((profile_id, name.strip(), description.strip()))
    return out


def choose_profile(ui, state):
    choices = [(pid, name+(' — '+description if description else '')) for pid, name, description in profiles()]
    default = state.get('profile') if state.get('profile') in dict(choices) else 'general'
    return ui.select('Your profile (a starting point: playbooks can be added or removed next)', choices, default)


def choose_team(ui, state):
    teams = cli.team_ids()
    if not teams:
        return None
    choices = [(team, team) for team in teams]+[('none', 'None of these (shared team practices)')]
    return ui.select('Your team', choices, state.get('team') or 'none')


def choose_identity(ui, home, state):
    recorded = state.get('user') or {}
    detected = recorded if recorded.get('email') else cli.detect_identity(home)
    default = detected.get('email', '')
    def valid(value):
        return None if not value or EMAIL.fullmatch(value) else 'This is not an email address.'
    answer = ui.text('Your work email (written at the top of your personal context; empty to skip)', default, valid)
    if not answer:
        return {'name': detected['name'], 'source': detected.get('source', 'os')} if detected.get('name') else {}
    if answer == detected.get('email'):
        return dict(detected)
    return {'email': answer, 'source': 'input'}


def labelled(name, entry):
    needs = entry.get('requires', [])
    return name+' — '+entry.get('description', '')+(' (also installs '+', '.join(needs)+')' if needs else '')


def customize(ui, home, profile_id):
    """None to keep the profile as proposed; otherwise the new lists for overrides.json. A choice the person turned off
    stays off: nothing is ticked again behind their back, and a conflict is explained, not resolved silently."""
    keep = ui.select('Skills, commands and agents', [('keep', 'Keep what the profile proposes (recommended)'),
                                                      ('adjust', 'Adjust playbooks, tools, commands and agents')], 'keep')
    if keep == 'keep':
        return None
    profile = read_json(ROOT/'profiles'/(profile_id+'.json'))
    catalog = read_json(ROOT/'skills/catalog.json')
    agent_catalog = read_json(ROOT/'agents/catalog.json')
    manifest = load_commands()
    personal = read_json(home/'.ai-kit/overrides.json', {})
    extra = [cli.RENAMED_SKILLS.get(s, s) for s in personal.get('extra_skills', [])]
    disabled = [cli.RENAMED_SKILLS.get(s, s) for s in personal.get('disabled_skills', [])]
    effective = (set(profile['skills']) | set(extra)) - set(disabled)
    playbooks = [s for s, e in catalog.items() if e.get('category') == 'domain' and not e.get('replaced_by')]
    tools = [s for s, e in catalog.items() if e.get('tier') == 'optional' and not e.get('replaced_by') and s not in profile['skills']]
    while True:
        picked = ui.checkbox('Domain playbooks (the agent follows them when the task fits)',
                             [(s, labelled(s, catalog[s]), s in effective) for s in playbooks])
        picked += ui.checkbox('Optional tools', [(s, labelled(s, catalog[s]), s in effective) for s in tools])
        shown = set(playbooks) | set(tools)
        new_extra = [s for s in extra if s not in shown] + [s for s in picked if s not in profile['skills'] and s not in extra]
        new_disabled = [s for s in disabled if s not in shown] + [s for s in profile['skills'] if s in shown and s not in picked]
        try:
            resolved = cli.resolve_skills(profile, {'extra_skills': new_extra, 'disabled_skills': new_disabled}, catalog, log=lambda *_: None)
        except KitError as exc:
            ui.warn(str(exc)+' Tick it again, or untick what needs it.')
            effective = set(picked)
            continue
        added = [s for s in resolved if s not in picked and s not in profile['skills']]
        if added:
            ui.print('Also installed, because your choices need them: '+', '.join(added)+'.')
        break
    names = [c['name'] for c in manifest]
    base_commands = list(profile['commands']) if profile.get('commands') is not None else names
    allowed = cli.allowed_commands(profile.get('commands'), personal, names) or names
    commands = ui.checkbox('Commands (shortcuts you type in the CLI; plain sentences work too)',
                           [(c['name'], '/'+c['name']+' — '+c['description'], c['name'] in allowed) for c in manifest])
    base_agents = list(profile.get('agents', []))
    current_agents = (set(base_agents) | set(personal.get('extra_agents', []))) - set(personal.get('disabled_agents', []))
    agents = ui.checkbox('Review agents (the main agent delegates to them)',
                         [(a, a, a in current_agents) for a in agent_catalog])
    return {'extra_skills': new_extra, 'disabled_skills': new_disabled,
            'extra_commands': [c for c in commands if c not in base_commands],
            'disabled_commands': [c for c in base_commands if c not in commands],
            'extra_agents': [a for a in agents if a not in base_agents],
            'disabled_agents': [a for a in base_agents if a not in agents]}


def by_folder(paths):
    counts = {}
    for rel in paths:
        root = '~/'+'/'.join(rel.split('/')[:1])
        counts[root] = counts.get(root, 0)+1
    return ', '.join(root+' '+str(n) for root, n in sorted(counts.items()))


def review(ui, home, plan):
    """Shows what will change, from a dry run of the engine: 'install', 'back' or 'cancel'."""
    report = {}
    quietly(cli.apply, plan['profile'], home, True, plan['identity'], plan['targets'], plan['team'], choices=plan['choices'], report=report)
    labels = {a.NAME: a.LABEL for a in ADAPTERS}
    lines = ['Profile: '+report['profile']+' ('+str(len(report['skills']))+' skills, '+str(len(report['commands']))+' commands, '
             + str(len(report['agents']))+' agents, '+str(len(report['hooks']))+' guardrails)',
             'CLIs: '+', '.join(labels[n] for n in report['targets'])]
    if report.get('team'):
        lines.append('Team: '+report['team'])
    if report['identity'].get('email'):
        lines.append('Identity: '+report['identity']['email'])
    lines.append('Files: '+str(len(report['created']))+' new, '+str(len(report['modified']))+' updated, '+str(len(report['removed']))+' removed'
                 + (' ('+by_folder(report['created']+report['modified']+report['removed'])+')' if report['created'] or report['modified'] or report['removed'] else ''))
    if report['removed']:
        shown = report['removed'][:6]
        lines.append('Removed: '+', '.join(shown)+(' and '+str(len(report['removed'])-6)+' more' if len(report['removed']) > 6 else ''))
    lines.append('Kept as they are: your personal context ('+report['context_file']+')'
                 + ('; overrides.json gets only the lists you changed' if plan['choices'] else '; overrides.json'))
    lines.append('Where: '+report['home'])
    lines.append('No call to the model: nothing is billed, the connection stays "not checked".')
    lines += report['notices']
    ui.panel('Before installing', lines)
    return ui.select('Apply these changes?', [('install', 'Install'), ('back', 'Back: change my choices'), ('cancel', 'Cancel')], 'install')


def install(ui, home, plan):
    with ui.progress('Installing…') as step:
        notices, lines = quietly(cli.apply, plan['profile'], home, False, plan['identity'], plan['targets'], plan['team'],
                                 choices=plan['choices'], progress=step)
    result(ui, home, notices)


def result(ui, home, notices=()):
    state = read_json(home/'.ai-kit/state.json')
    _, lines = quietly(cli.print_summary, home, state, None)
    ui.panel('Result', menu_wording([line for line in lines if line.strip() and line.strip() != 'Summary'] + list(notices)))


def open_context(ui, home):
    state = read_json(home/'.ai-kit/state.json')
    user_file = home/state.get('context_dir', '.gemini')/'30_USER.md'
    ui.print('Your personal context: '+str(user_file))
    ui.print('It tells the agent who you are and how you work: plain text, kept as is by every update.')
    editor = cli.text_editor(user_file)
    if not editor:
        ui.print('Edit it with a plain-text editor, then choose "Update" in this menu and start a new session of your CLI.')
        return 0
    if not ui.confirm('Open it now in '+editor[0]+'?', default=True):
        return 0
    try:
        subprocess.Popen(editor[1], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        ui.warn('No editor could be opened: open the file above with a plain-text editor, then update.')
        return 0
    ui.pause('Edit it, save it (same name, plain text), then press Enter here')
    problem = cli.plain_text_problem(user_file)
    if problem:
        ui.warn(problem+' Then update.')
        return 1
    notices, _ = quietly(cli.apply, state['profile'], home, False, None)
    for notice in notices:
        ui.warn(notice)
    ui.print('Personal context applied. Start a new session of your CLI: it reads it when it starts.')
    return 0


def choose_and_install(ui, home, state):
    """The choices, the review, then the installation. Back returns to the choices with the answers kept."""
    plan = {'targets': None, 'profile': None, 'team': None, 'identity': None, 'choices': None}
    current = dict(state)
    while True:
        plan['targets'] = choose_targets(ui, home, {**current, 'targets': plan['targets'] or cli.recorded_targets(current)})
        plan['profile'] = choose_profile(ui, {**current, 'profile': plan['profile'] or current.get('profile')})
        plan['team'] = choose_team(ui, current)
        plan['identity'] = choose_identity(ui, home, {**current, 'user': plan['identity'] or current.get('user')})
        plan['choices'] = customize(ui, home, plan['profile'])
        action = review(ui, home, plan)
        if action == 'install':
            install(ui, home, plan)
            if not state and ui.confirm('Write a few lines about you and how you work, in your personal context, now?', default=False):
                open_context(ui, home)
            return 0
        if action == 'cancel':
            ui.print('Cancelled: the agents\' configuration was not changed.')
            return 1


def doctor_view(ui, home, live=False):
    code, lines = quietly(cli.doctor, home, None, live)
    summary = lines[:lines.index('Details')] if 'Details' in lines else lines
    checks = [line for line in lines if line.startswith('[Check]')]
    ui.panel('Checks', menu_wording([line for line in summary if line.strip() and line.strip() != 'Summary'] + (['Details to fix:'] + checks if checks else [])))
    return code


def uninstall_flow(ui, home):
    report = {}
    _, lines = quietly(cli.uninstall, home, True, None, None, report)
    ui.panel('Uninstall', lines)
    if not ui.confirm('Remove the kit configuration listed above? A backup is kept.', default=False):
        ui.print('Nothing removed.')
        return 1
    with ui.progress('Removing…') as step:
        code, lines = quietly(cli.uninstall, home, False, None, step)
    ui.panel('Result', lines)
    ui.print('The kit\'s private Python environment stays until you run the launcher with: uninstall --remove-runtime')
    return code


def live_check(ui, home):
    if os.environ.get('AI_KIT_NO_LIVE') == '1':
        ui.warn('Real calls to the model are turned off on this workstation (AI_KIT_NO_LIVE=1).')
        return 2
    ui.warn('This makes a real call to the model with your CLI and your account: your provider may bill it.')
    if not ui.confirm('Make this billed call now?', default=False):
        return 1
    return doctor_view(ui, home, live=True)


def menu(ui, home, state):
    action = ui.select('What do you want to do?', [
        ('update', 'Update: reapply the kit with my current choices'),
        ('modify', 'Change my choices (CLIs, profile, playbooks, commands, agents)'),
        ('check', 'Check the installation (local, no call to the model)'),
        ('context', 'Open my personal context'),
        ('uninstall', 'Uninstall the kit configuration'),
        ('live', 'Advanced: check the connection with a real call to the model (may be billed)'),
        ('quit', 'Quit')], 'update')
    if action == 'update':
        with ui.progress('Updating…') as step:
            notices, _ = quietly(cli.apply, state['profile'], home, False, None, progress=step)
        result(ui, home, notices)
        return 0
    if action == 'modify':
        return choose_and_install(ui, home, state)
    if action == 'check':
        return doctor_view(ui, home)
    if action == 'context':
        return open_context(ui, home)
    if action == 'uninstall':
        return uninstall_flow(ui, home)
    if action == 'live':
        return live_check(ui, home)
    return 0


def start(ui, home, setup=False):
    """Entry point without options: the first installation, or the menu when the kit is already installed."""
    try:
        if not setup:
            cli.migrate_kit_dir(home)
        state = read_json(home/'.ai-kit/state.json')
        ui.title('AI Kit '+kit_version())
        workstation(ui, home, state)
        if state and not setup:
            return menu(ui, home, state)
        return choose_and_install(ui, home, state)
    except Cancelled:
        ui.print('\nCancelled: the agents\' configuration was not changed.')
        return 130
