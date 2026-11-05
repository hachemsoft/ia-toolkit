"""doctor: local checks of an installation (files, guardrails, runtime, repo overrides) and, on request, the billed live check."""
import contextlib
import io
import json
from datetime import date
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from .core import (_PACKAGE_DIR, ROOT, USER_CONTEXT, SECRET, KitError, read_json, digest,
                   inside, load_commands, run_timed)
from . import versions
from .adapters import ADAPTERS
from .interface import DoctorContext, LiveCheck
from .settings import LEGACY_KIT_DIR, LEGACY_PERSONAL_FILE, PERSONAL_FILE, RETIRED_KEYS, allowed_domains, domain_allowed, load_profile, managed_context_names, merge_settings, organization, personal_settings, recorded_targets, resolve_mcp, retired_key_notice, setting_differences, team_settings, unknown_keys, version_changes


# A known case each guardrail must block; doctor runs it to prove the guardrail works, not just that its file exists.
GUARDRAIL_PROBES = {
    'dbt-prod-guard': lambda home: {'tool_name': 'run_shell_command', 'tool_input': {'command': 'dbt run --target prod'}, 'cwd': str(home)},
    'protected-paths': lambda home: {'tool_name': 'write_file', 'tool_input': {'file_path': str(home/'.ai-kit'/'overrides.toml')}, 'cwd': str(home)},
}
# session-news on a /clear: answers {} and writes nothing (a startup probe would mark the real news as announced).
HOOK_PROBES = {'session-news': lambda home: {'source': 'clear', 'hook_event_name': 'SessionStart'}}


def blocks(answer):
    return answer.get('decision') == 'deny' or answer.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'



def proc_ok(proc):
    return proc is not None and proc.returncode == 0


def command_parts(command):
    """Interpreter and script of a kit guardrail command (hook_command: "<python>" -I "<script>")."""
    parts = [part.strip('"\'') for part in (shlex.split(command, posix=(os.name != 'nt')) or [])]
    return (Path(parts[0]), Path(parts[-1])) if len(parts) >= 2 else (None, None)


def guardrail_checks(home, state, status):
    """Each enabled guardrail: its Python and script exist, and it really blocks a known case. A guardrail that cannot run lets everything through."""
    for name, hook in sorted(state.get('hooks', {}).items()):
        kind = 'Guardrail' if hook.get('event') == 'BeforeTool' else 'Hook'
        interpreter, script = command_parts(hook['group']['hooks'][0]['command'])
        if not interpreter or not interpreter.is_file():
            status(False, kind+' '+name+': Python not found ('+str(interpreter)+'); run update to point to the current Python')
            continue
        if not script.is_file():
            status(False, kind+' '+name+': script missing ('+str(script)+'); run update')
            continue
        probe = GUARDRAIL_PROBES.get(name) or HOOK_PROBES.get(name)
        if not probe:
            continue
        env = {k: v for k, v in os.environ.items() if k != 'AI_KIT_ALLOW_PROD'}
        env.update({'HOME': str(home), 'USERPROFILE': str(home)})
        proc = None
        try:
            proc = subprocess.run([str(interpreter), '-I', str(script)], input=json.dumps(probe(home)), capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=20, env=env)
            answer = json.loads(proc.stdout or '{}')
        except (OSError, ValueError, subprocess.SubprocessError):
            answer = {}
        if name in HOOK_PROBES:
            status(proc_ok(proc) and answer == {}, 'Hook '+name+': synthetic test, the script runs and answers (this does not prove the CLI calls it)')
        else:
            status(blocks(answer), 'Guardrail '+name+': synthetic test, the script blocks a known case when run (this does not prove the CLI calls it)')


REPO_SKILL_DIRS = ('.agents/skills', '.gemini/skills', '.codex/skills')
# A skills folder that some CLIs read in the home folder, where the kit writes nothing.
SHARED_SKILL_DIRS = ('.agents/skills',)


def foreign_skills(home, state):
    """Skills in the home folder that the kit did not install: in every skills folder the kit writes to (read from the
    state, so no CLI is named here) and in the shared ones. Shown, never removed."""
    files = state.get('files', {})
    roots = {m.group(1) for rel in files if (m := re.match(r'^(.*/skills)/[^/]+/SKILL\.md$', rel))} | set(SHARED_SKILL_DIRS)
    found = []
    for rel in sorted(roots):
        base = home/rel
        if base.is_dir():
            found += [base/child.name for child in sorted(base.iterdir())
                      if (child/'SKILL.md').is_file() and rel+'/'+child.name+'/SKILL.md' not in files]
    return found


def skill_findings(folders):
    """What runtime/check_skills.py finds in those skills: the same rules as the kit's own CI."""
    if not folders:
        return []
    import importlib.util
    spec = importlib.util.spec_from_file_location('ai_kit_check_skills', ROOT/'runtime'/'check_skills.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.scan(folders, set())


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


def plain_text_problem(path):
    """Why 30_USER.md cannot be read as plain text (renamed, rich text, not UTF-8), or None."""
    if not path.is_file():
        others = sorted(p.name for p in path.parent.glob(path.stem+'*') if p.name != path.name and p.suffix.lower() in ('.txt', '.rtf', '.rtfd'))
        return path.name+' is missing'+(' (saved as '+', '.join(others)+'?): give it back its name '+path.name if others else '')+'.'
    data = path.read_bytes()
    if data.lstrip().startswith(b'{\\rtf'):
        return path.name+' was saved as rich text: reopen it and save it as plain text (TextEdit: Format > Make Plain Text).'
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return path.name+' is not UTF-8 text: save it again choosing the UTF-8 encoding.'
    return None


def mcp_report(home, state):
    """MCP lines of the summaries, from the installer's own resolution: configured, chosen but not provided by the
    organization, or turned off. Never claims a connection: the kit does not call MCP servers."""
    profile = load_profile(state['profile'])
    servers, undefined = resolve_mcp(organization().get('defaults', {}).get('mcp', {}), profile.get('mcp', []),
                                     personal_settings(home/'.ai-kit').get('mcp', {}), team_settings(state.get('team')).get('mcp', {}))
    off = [n for n in profile.get('mcp', []) if n not in servers and n not in undefined]
    lines = []
    if servers:
        lines.append('Data connections (MCP): '+', '.join(servers)+' configured; connection not verified (check it with your CLI\'s MCP command).')
    if undefined or off:
        missing = [n+' not provided by your organization yet' for n in undefined] + [n+' turned off (in your overrides.toml or by your team)' for n in off]
        about = 'the SQL and dbt files' if {'bigquery', 'dbt'} & set(undefined + off) else 'the files'
        lines.append('Data connections (MCP): '+'; '.join(missing)+'. You can work on '+about+' of your repo with its usual tools;'
                     ' access to the data through MCP needs a connection provided by your company (platform team, docs/mcp.md).')
    return lines or ['Data connections (MCP): none configured (optional, docs/mcp.md).']


def print_summary(home, state, live=None, problems=()):
    """What is ready, what is missing, the next action. Facts only: a CLI found is not a CLI signed in, and a connection
    is "verified" only when a real call was made (live: {cli name: 0 if the model answered}). Same text for setup and doctor."""
    print('\nSummary')
    if not state:
        print('  Kit configuration: not installed.')
        print('Next step: run setup from the kit folder (docs/getting-started.md#run-the-kit).')
        return
    commands = state.get('installed', {}).get('commands', [])
    print('  Kit configuration: installed (profile '+state['profile']+', version '+str(state.get('version'))+', '+str(len(commands))+' commands).')
    targeted = [a for a in ADAPTERS if a.NAME in (state.get('installed', {}).get('clis') or [])]
    found = []
    for adapter in targeted:
        if not shutil.which(adapter.COMMAND):
            print('  '+adapter.LABEL+': not found on this workstation; its configuration is prepared. Install it following your IT procedure, then run update.')
            continue
        found.append(adapter)
        result = (live or {}).get(adapter.NAME)
        print('  '+adapter.LABEL+': found; '+('connection verified: the model answered.' if result == 0 else
                                             'the model did not answer: see its diagnosis and fix.' if result is not None else
                                             'connection not verified.'))
    try:
        for line in mcp_report(home, state):
            print('  '+line)
    except KitError as exc:
        print('  Data connections (MCP): '+str(exc))
    if problems:
        print('  Failed checks, to fix ('+str(len(problems))+'): '+'; '.join(problems[:5])+('; and '+str(len(problems)-5)+' more in the details' if len(problems) > 5 else '')+'.')
    if problems:
        step = 'fix the points above, then run doctor again.'
    elif any(r not in (0, None) for r in (live or {}).values()):
        step = 'apply the fix shown above, then run doctor --live.'
    elif not found:
        step = 'install '+' or '.join(a.LABEL for a in targeted)+' following your IT procedure, then run update; meanwhile nothing else is needed.'
    else:
        names = ' or '.join('`'+a.COMMAND+'`' for a in found)
        step = 'open a terminal in your repo, start '+names+' and type /guide'+(' ($guide in Codex)' if any(a.NAME == 'codex' for a in found) else '')+'.'
        if not live or any((live or {}).get(a.NAME) != 0 for a in found):
            step += ' Connection not verified: if the CLI asks you to sign in, follow your IT procedure. doctor --live checks it with a real call to the model, which your provider may bill.'
    print('Next step: '+step)


def doctor(home, cwd=None, live=False):
    """Summary first (what is ready, what to fix, next step), then the detailed checks. Each check runs once:
    the details are collected while the checks run, and printed after the summary. Exit code: 1 if a check or the
    live call fails."""
    problems, results, details = [], {}, io.StringIO()
    if live:
        print('Checking the connection with a real call to the model (up to 90 s; your provider may bill it)…')
    with contextlib.redirect_stdout(details):
        code = doctor_checks(home, cwd, problems)
        if live:
            release_check()
            code = max(code, live_checks(home, results=results))
    print_summary(home, read_json(home/'.ai-kit/state.json'), results if live else None, problems)
    print('\nDetails\n'+details.getvalue(), end='')
    return code


def kit_version():
    return (ROOT/'VERSION').read_text(encoding='utf-8').strip()


def source_folder():
    """The kit folder the launcher was started from (release ZIP or clone), or None when the kit runs otherwise."""
    folder = os.environ.get('AI_KIT_SOURCE_DIR')
    return Path(folder) if folder and (Path(folder)/'VERSION').is_file() else None


def version_line():
    """ai-kit --version: which copy of the kit is running, so a stale copy on the PATH is easy to spot."""
    return 'AI Kit '+kit_version()+' — '+str(_PACKAGE_DIR)+' (Python '+sys.version.split()[0]+', '+sys.executable+')'


SCRIPT_INTERPRETER = re.compile(rb'^#!\s*"?([^"\r\n]*python[^"\r\n ]*)"?|^\'\'\'exec\' "([^"]+)"', re.M)


def kit_commands_on_path():
    """Every `ai-kit` command on the PATH, in the order the shell tries them: (path, version or None). The version is read
    from the command's own Python (its first line names it), never by running the command itself."""
    found, seen = [], set()
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        command = shutil.which('ai-kit', path=folder) if folder else None
        if not command or os.path.realpath(command) in seen:
            continue
        seen.add(os.path.realpath(command))
        version = None
        try:
            with open(command, 'rb') as handle:
                head = handle.read(4096) if not command.lower().endswith('.exe') else handle.read()[-4096:]
            match = SCRIPT_INTERPRETER.search(head)
            interpreter = (match.group(1) or match.group(2)).decode('utf-8', 'replace') if match else None
            if interpreter and os.path.isfile(interpreter):
                proc = subprocess.run([interpreter, '-I', '-c', 'import importlib.metadata as m; print(m.version("ai-kit"))'],
                                      capture_output=True, text=True, timeout=20)
                version = proc.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
        found.append((command, version))
    return found


def command_checks(home, state, status):
    """The `ai-kit` command the person chose: its script, the kit folder it runs, the PATH of this terminal."""
    from . import command as kit_command
    recorded = state.get('command') or {}
    if not recorded.get('chosen') or not recorded.get('folder'):
        return  # not chosen, or never installed (the kit ran without the launcher): setup and update already said so
    shim = home/'.ai-kit'/'bin'/kit_command.SHIM_NAME
    if not shim.is_file():
        status(False, 'The `ai-kit` command is missing: run the installer from the kit folder (Installer.cmd, or sh scripts/bootstrap.sh)')
        return
    folder = kit_command.shim_folder(shim.read_bytes()) or recorded.get('folder')
    if folder and Path(folder).is_dir():
        status(True, 'The `ai-kit` command runs the launcher of '+folder)
    else:
        status(False, 'The `ai-kit` command points to a kit folder that moved or was deleted ('+str(folder)+'): run the installer from the kit folder, it rewrites the command')
    on_path = [p for p in os.environ.get('PATH', '').split(os.pathsep) if p and os.path.normcase(os.path.normpath(p)) == os.path.normcase(os.path.normpath(str(shim.parent)))]
    if not on_path:
        print('[Info] '+str(shim.parent)+' is not on the PATH of this terminal: open a new one to use the `ai-kit` command'
              + ('' if os.name == 'nt' or recorded.get('startup_file') else '; add the line the installer gave to your shell startup file'))


def tracker_checks(home, state, status):
    """The friction tracker the organization set: the person's CLI present and signed in, frictions not sent yet."""
    config = state.get('friction_tracker')
    if not config:
        return
    from .core import friction_module
    friction = friction_module()
    cli = friction.TRACKERS.get(config.get('kind'), {}).get('cli')
    label = 'Friction tracker: '+str(config.get('kind'))+' '+str(config.get('project'))+', '
    exe = shutil.which(cli) if cli else None
    if not exe:
        status(False, label+str(cli)+' not on the PATH: install it following your IT procedure, then '+str(cli)+' auth login; frictions stay local meanwhile')
    else:
        try:
            signed = run_timed([exe, 'auth', 'status'], 15, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL).returncode == 0
        except (OSError, subprocess.SubprocessError):
            signed = False
        status(signed, label+cli+(' signed in' if signed else ' not signed in: run '+cli+' auth login (a personal access token); frictions stay local meanwhile'))
    pending = len(friction.unsent(str(home), config))
    if pending:
        print('[Info] '+str(pending)+' friction'+('s' if pending != 1 else '')+' not sent to the tracker yet: ai-kit friction --sync')


def news_checks(home, state, status):
    """The session-news hook: the kit folder it reads, the last remote read, what waits for the next session start."""
    if 'session-news' not in state.get('hooks', {}):
        print('[Info] session-news hook off (hooks.session-news = false): nothing announced at session start.')
        return
    from .core import news_module
    news = news_module()
    hook = news.hook_module()
    kit_dir = str(state.get('kit_dir') or '')
    if not kit_dir:
        print('[Info] Kit folder not recorded: session-news announces the installed version only (run the installer from the kit folder, then update).')
    else:
        status(os.path.isdir(kit_dir), 'Kit folder present for session-news: '+kit_dir+('' if os.path.isdir(kit_dir) else ' (moved or deleted: run the installer from its new place, then update)'))
    marker = read_json(home/'.ai-kit'/'news.json')
    last = marker.get('last_check') if isinstance(marker.get('last_check'), dict) else {}
    if (state.get('news') or {}).get('check_remote') is False:
        print('[Info] Kit remote not read by session-news (news.check_remote = false): a newer version is not proposed.')
    elif last:
        print('[Info] Kit remote last read by session-news: '+str(last.get('date'))+', '+str(last.get('result'))+(' ('+last['detail']+')' if last.get('detail') else '')
              + (', remote version '+last['remote_version'] if last.get('remote_version') else ''))
    else:
        print('[Info] Kit remote not read yet by session-news (once a day at session start; ai-kit news --check reads it now).')
    if marker.get('declined_version'):
        print('[Info] Version '+str(marker['declined_version'])+' declined (ai-kit news --later): the next one will be proposed.')
    if hook and kit_dir and os.path.isdir(kit_dir):
        today = date.today().isoformat()
        waiting = [e for e in hook.parse_news(hook.file_text(os.path.join(kit_dir, 'NEWS.md')))
                   if e['id'] not in (marker.get('announced_news') or []) and hook.aimed_at(e, str(state.get('profile') or ''), str(state.get('team') or ''), today)]
        if waiting:
            print('[Info] '+str(len(waiting))+' announcement'+('s' if len(waiting) != 1 else '')+' waiting for the next session start: '+', '.join(e['id'] for e in waiting))


def runtime_checks(home, status):
    """The private environment the launcher installs the kit in, and the copies of the kit a person may run instead."""
    from . import command as kit_command
    record = read_json(home/'.ai-kit/runtime/install.json', {})
    if record.get('status') == 'ready':
        print('[OK] Kit runtime ready: version '+str(record.get('version'))+', '+str(home/'.ai-kit/runtime/venv'))
    elif record.get('status') in ('installing', 'failed'):
        status(False, 'Kit runtime '+('interrupted during its installation' if record['status'] == 'installing' else 'failed to install')
               + ': run the installer again, it starts it over')
    else:
        print('[Info] No private kit environment in this home folder: the kit runs from '+str(_PACKAGE_DIR))
    source = source_folder()
    if source is not None:
        folder_version = (source/'VERSION').read_text(encoding='utf-8').strip()
        status(folder_version == kit_version(), 'The kit folder ('+folder_version+') and the installed kit package ('+kit_version()+') are the same version'
               + ('' if folder_version == kit_version() else ': run the installer from that folder, Update'))
    own = os.path.normcase(os.path.realpath(str(home/'.ai-kit'/'bin'/kit_command.SHIM_NAME)))
    commands = [(path, version) for path, version in kit_commands_on_path() if os.path.normcase(os.path.realpath(path)) != own]  # the kit's own command runs this very kit
    if commands:
        first, version = commands[0]
        if version != kit_version():
            status(False, 'The `ai-kit` command on your PATH is another copy of the kit ('+first+', version '+str(version or 'unknown')
                   + ', this kit '+kit_version()+'): typing ai-kit runs that one. Remove it (pipx uninstall ai-kit, or pip uninstall ai-kit'
                   + ' with its Python), or run the launcher of the kit folder')
        for other, other_version in commands[1:]:
            print('[Info] Another `ai-kit` command, not used because an earlier one comes first on the PATH: '+other+' (version '+str(other_version or 'unknown')+')')


def cli_version(command):
    """The version a CLI reports (<command> --version, local, no model call), or None."""
    path = shutil.which(command)
    if not path:
        return None
    try:
        proc = run_timed([path, '--version'], 15, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'\d+(?:\.\d+)+', (proc.stdout or '') + (proc.stderr or ''))
    return match.group(0) if match else None


def newer_than(found, verified):
    def parts(version):
        return tuple(int(x) for x in version.split('.')[:3])
    return parts(found) > parts(verified)


def doctor_checks(home, cwd=None, problems=None):
    issues = 0
    def status(ok,message):
        nonlocal issues
        print(('[OK] ' if ok else '[Check] ')+message)
        if not ok:
            issues += 1
            if problems is not None:
                problems.append(message)
    status(sys.version_info >= (3,9),'Python 3.9 minimum')
    runtime_checks(home, status)
    if (home/LEGACY_KIT_DIR).exists():
        status(False,'Old ~/'+LEGACY_KIT_DIR+' folder present: run update, which renames it to ~/.ai-kit')
    state = read_json(home/'.ai-kit/state.json')
    status(bool(state),'Kit installation; run setup if missing.')
    hints = []
    if state:
        print('Profile: '+state['profile']+' | version '+state['version'])
        command_checks(home, state, status)
        tracker_checks(home, state, status)
        news_checks(home, state, status)
        identity = state.get('user', {})
        print('Recorded identity: '+(identity.get('email') or identity.get('name') or 'none')+(' (source '+identity['source']+')' if identity.get('source') else ''))
        profile = load_profile(state['profile'])
        profile = {**profile, 'practices': state.get('practices') or profile['practices']}  # with the person's team
        ctx = DoctorContext(profile=profile, load_commands=load_commands, managed_context_names=managed_context_names,
                                    allowed_domains=allowed_domains, domain_allowed=domain_allowed)
        context = state.get('context_dir', '.gemini')
        user_file = home/context/USER_CONTEXT
        status(user_file.is_file(),'Personal context present: '+context+'/'+USER_CONTEXT)
        if user_file.is_file():
            problem = plain_text_problem(user_file)
            status(not problem, problem or USER_CONTEXT+' is plain UTF-8 text')
            if not problem and SECRET.search(user_file.read_text(encoding='utf-8')):
                status(False, USER_CONTEXT+' seems to contain a secret (key, token or password): remove it, the agent reads this file')
        for personal_file in (home/'.ai-kit'/PERSONAL_FILE, home/'.ai-kit'/LEGACY_PERSONAL_FILE):
            if personal_file.is_file() and SECRET.search(personal_file.read_text(encoding='utf-8', errors='replace')):
                status(False, '~/.ai-kit/'+personal_file.name+' seems to contain a secret: write ${VARIABLE} instead and define it in your environment (docs/mcp.md)')
        for rel,expected in state.get('files',{}).items():
            path = inside(home,rel)
            status(path.is_file() and digest(path.read_bytes())==expected,rel)
        guardrail_checks(home, state, status)
        folder_version = kit_version()
        status(state.get('version') == folder_version, 'Configuration applied by version '+str(state.get('version'))+', the kit running is '+folder_version
               + ('' if state.get('version') == folder_version else ': run update'))
        recorded = (state.get('installed') or {}).get('versions')
        if recorded:
            behind = version_changes(recorded, {kind: {n: v for n, v in names.items() if n in recorded.get(kind, {})}
                                                for kind, names in versions.catalog_versions().items()})
            status(not behind, 'Skills and agents at the versions of this kit' + (': '+', '.join(behind)+'; run update' if behind else ''))
        org_defaults = organization().get('defaults', {})
        team_layer = team_settings(state.get('team'))
        personal = personal_settings(home/'.ai-kit')
        layers = [('~/.ai-kit/overrides.toml', personal), ('organization.toml defaults', org_defaults)]
        layers += [('organization.toml teams.'+state['team'], team_layer)] if state.get('team') else []
        for label, settings in layers:
            for key in RETIRED_KEYS:
                if key in settings:
                    print(retired_key_notice(key).replace('overrides.toml', label, 1))
            unknown = unknown_keys(settings)
            status(not unknown, label+': only known keys'+(' (unknown: '+', '.join(unknown)+'; a typo? keys are listed in schemas/overrides.schema.json)' if unknown else ''))
        shared = merge_settings(org_defaults, team_layer)
        changed = setting_differences({k: v for k, v in shared.items() if k != 'mcp'}, merge_settings(shared, personal))
        if changed:
            print('[Info] Your overrides.toml changes organization or team defaults: '+', '.join(changed))
        if state.get('team'):
            sources = [s for s, present in (('practices/20-'+state['team']+'.md', (ROOT/'practices'/('20-'+state['team']+'.md')).is_file()),
                                            ('organization.toml teams.'+state['team'], bool(team_layer))) if present]
            print('[Info] Team: '+state['team']+' ('+(', '.join(sources) or 'nothing of its own yet')+')')
        root, overrides = repo_skill_overrides(state, cwd or os.getcwd())
        if overrides:
            print('[Check] This repo ('+root.name+') has skills named like kit skills: '+', '.join(path for _, path in overrides)
                  + '. Depending on the CLI, the repo\'s version, the kit\'s, or both are used (docs/cli/matrice.md):'
                  + ' give repo skills names of their own, and protect .agents/ with CODEOWNERS.')
        elif root:
            print('[OK] No repo skill named like a kit skill ('+root.name+')')
        own = foreign_skills(home, state)
        if own:
            print('[Info] Skills not installed by the kit: '+', '.join('~/'+f.relative_to(home).as_posix() for f in own))
            # Shown to review, not counted as failed checks: these skills are the person's own choice.
            for path, line, rule, _ in skill_findings(own):
                print('[Info] To review: ~/'+path.relative_to(home).as_posix()+(':'+str(line) if line else '')+' ('+rule+')')
        installed = set(state.get('installed', {}).get('clis') or [a.NAME for a in ADAPTERS])
        for adapter in ADAPTERS:
            if adapter.NAME in installed:
                adapter.doctor(home, state, status, ctx)
                hints.append(adapter.doctor_hint())
                found = cli_version(adapter.COMMAND)
                if found and newer_than(found, adapter.VERIFIED):
                    print('[Info] '+adapter.LABEL+' '+found+' is newer than the version the kit was checked on ('+adapter.VERIFIED+'). '
                          'If something stops working, the checks above and usage say what; log it with /friction.')
        try:
            servers, undefined = resolve_mcp(org_defaults.get('mcp', {}), profile.get('mcp', []), personal.get('mcp', {}), team_layer.get('mcp', {}))
            print('[Info] MCP servers: '+(', '.join(servers) or 'none')+(' | chosen but not defined in organization.toml: '+', '.join(undefined) if undefined else ''))
        except KitError as exc:
            status(False, str(exc))
    print('Local diagnosis only: authentication, MCP connection and IAM rights not tested; doctor --live makes a real call to the model, which your provider may bill.')
    for hint in hints:
        if hint:
            print(hint)
    return 1 if issues else 0


def release_check():
    """doctor --live: a newer published version of the kit (git tags of the kit folder's remote), without blocking anything.
    The kit folder is the clone the launcher was started from (the installed package has no .git), else the code's own folder."""
    folder = source_folder() or ROOT
    if not (folder/'.git').exists() or not shutil.which('git'):
        return
    try:
        subprocess.run(['git', '-C', str(folder), 'fetch', '--tags', '--quiet'], capture_output=True, timeout=20)
        tags = subprocess.run(['git', '-C', str(folder), 'tag', '--list', 'v*', '--sort=-v:refname'], capture_output=True, text=True, timeout=10).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return
    current = (folder/'VERSION').read_text(encoding='utf-8').strip()
    def key(version):
        return tuple(int(x) for x in re.findall(r'\d+', version)[:3])
    if tags and key(tags[0]) > key(current):
        print('[Info] AI Kit '+tags[0].lstrip('v')+' is published (this folder: '+current+'): run update, which fetches it.')


def live_checks(home, results=None):
    """Real call to the model by each installed CLI that supports it (doctor --live only); 1 if one does not answer.
    results, when given, receives {cli name: 0 if the model answered}: the summaries say "verified" only from it."""
    code = 0
    chosen = set(recorded_targets(read_json(home/'.ai-kit/state.json')) or [a.NAME for a in ADAPTERS])
    for adapter in ADAPTERS:
        # Only the CLIs the person chose: a billed call never goes to a CLI merely present on the workstation.
        if isinstance(adapter, LiveCheck) and adapter.NAME in chosen and shutil.which(adapter.COMMAND):
            answer = adapter.live(home)
            if results is not None:
                results[adapter.NAME] = answer
            code = max(code, answer)
    return code
