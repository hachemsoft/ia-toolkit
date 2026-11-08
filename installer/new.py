"""ai-kit new: creates a skill, an agent, a command or a profile in a clone of the kit, with its metadata (aikit-*), its version,
its checks, then a branch and a merge request after two answers. No model call; the only network is the push and the merge
request the person accepts. Skills and agents always go under contrib/: moving one to internal/ is a maintainer's act."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .adapters import ADAPTERS
from .core import KitError, redact
from .resolve import agent_catalog, skill_catalog
from .toml_files import read_toml, toml_value
from .ui import Cancelled, make_ui

KINDS = ('profile', 'skill', 'agent', 'command')
NAME = re.compile(r'[a-z0-9][a-z0-9-]*')
PLACEHOLDER = '<…'
SKILL_CATEGORIES = ('tool', 'domain', 'reference', 'workflow')
CATEGORY_LABELS = {'tool': 'tool: a utility, usually behind a command', 'domain': 'domain: a playbook, activated by the task',
                   'reference': 'reference: vocabulary other skills read', 'workflow': 'workflow: a step of the cycle'}
LOCK, SNAPSHOT = 'versions.lock.json', 'tests/golden/install-snapshot.json'
# The tests that hold what a new component must respect; the whole suite stays with the CI.
TARGET_TESTS = ('test_skills_catalog', 'test_skill_dependencies', 'test_commands', 'test_consistency', 'test_evals_runner', 'test_profiles_general', 'test_versions',
                'test_evals_and_playbooks', 'test_invariants', 'test_snapshot')
# What the version lock and the snapshot read: an uncommitted change here would be recorded by them and left out of the commit.
DIGESTS_READ = ('skills', 'agents', 'commands', 'practices', 'profiles', 'templates', 'runtime', 'installer', 'schemas', 'organization.toml', 'VERSION')
# The snapshot reference holds POSIX paths (tests/test_snapshot.py skips on Windows): rewritten there, it breaks every other system.
WINDOWS = os.name == 'nt'


def run_command(command, cwd):
    env = {**{k: v for k, v in os.environ.items() if k != 'AI_KIT_SOURCE_DIR'}, 'AI_KIT_NO_LIVE': '1'}
    try:
        done = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except OSError as exc:
        return 127, str(exc)
    # The output of a success is read by the code: a warning on stderr must not end up in a branch name or a path.
    return done.returncode, done.stdout if done.returncode == 0 else done.stdout+done.stderr


def at_terminal():
    """A person at a terminal, both ends (cli.interactive): a pipe must never answer for the commit or the push."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def clean(text):
    """What git, glab, gh or a check printed, without what looks like a secret or the user part of a URL."""
    return redact(re.sub(r'://[^/\s]+@', '://', text)).rstrip()


def read(repo, rel):
    return (repo/rel).read_text(encoding='utf-8')


def kit_repo(repo, run):
    """The clone of the kit to work in: a git repository of its own, holding the content (aikit.toml, skills/); a ZIP installation has none."""
    problem = 'ai-kit new needs a git clone of the kit (a ZIP installation has none): clone it, then run this from there.'
    if not repo:
        raise KitError(problem)
    repo = Path(repo).resolve()
    code, top = run(['git', 'rev-parse', '--show-toplevel'])
    # samefile: on Windows a temporary folder can be written in two forms, its short name and its long one.
    if code != 0 or not os.path.isdir(top.strip()) or not os.path.samefile(top.strip(), repo) or not (repo/'aikit.toml').is_file() or not (repo/'skills').is_dir() or not (repo/'profiles').is_dir():
        raise KitError(problem)
    return repo


def component_path(kind, name):
    return {'skill': 'skills/contrib/'+name+'/SKILL.md', 'agent': 'agents/contrib/'+name+'.md', 'command': 'commands/'+name+'.md', 'profile': 'profiles/'+name+'.toml'}[kind]


def name_problem(repo, name, kind, run):
    """Why this name cannot be used, or None, before any other question: the format, a built-in command, a path git ignores,
    the skills and agents found in the clone, commands, profiles and the disk."""
    if not name or not NAME.fullmatch(name):
        return 'Invalid name "'+str(name)+'": lowercase letters, digits and dashes, starting with a letter or a digit.'
    if name.startswith('ai-kit-'):
        return 'The name "'+name+'" starts with ai-kit-, the prefix the kit gives its own installed names: choose another.'
    builtin = sorted(a.LABEL for a in ADAPTERS if name in a.BUILTIN_COMMANDS)
    if kind == 'command' and builtin:
        return 'The name "'+name+'" is a built-in command of '+', '.join(builtin)+': choose another.'
    if run(['git', 'check-ignore', '--', component_path(kind, name)])[0] == 0:
        return 'The name "'+name+'" gives a path the repo\'s .gitignore ignores: choose another.'
    taken = {'a skill': name in skill_catalog(repo),
             'an agent': name in agent_catalog(repo),
             'a command': (repo/'commands'/(name+'.md')).exists(),
             'a profile': (repo/'profiles'/(name+'.toml')).exists(),
             'a folder of skills/contrib': (repo/'skills/contrib'/name).exists(),
             'a file of agents/contrib': (repo/'agents/contrib'/(name+'.md')).exists()}
    for label, found in taken.items():
        if found:
            return 'The name "'+name+'" is already '+label+' of the kit: choose another.'
    return None


def with_case_section(page, name):
    """docs/eval-cases.md with the section of a contributed skill's case: a test refuses a case without one."""
    heading = '## Contributed skills\n\n'
    section = ('### `'+name+'`\n- **Checks**: <… what this case checks …>\n- **Prompt**: <… what a person types …>\n'
               '- **Passes when**: <… what the answer must show …>\n- **Why**: <… the behaviour this protects …>\n\n')
    at = page.index('## Last measured')
    return page[:at]+('' if heading in page else heading)+section+page[at:]


def next_case_file(repo, name):
    numbers = [int(p.name[:2]) for p in (repo/'evals/cases').glob('*.json') if p.name[:2].isdigit()]
    return 'evals/cases/{:02d}-{}.json'.format(max(numbers, default=0)+1, name)


def skill_changes(repo, name, owner, description, category):
    """{path: full new text}: nothing is written here."""
    meta = ['metadata:', '  aikit-version: "1.0.0"', '  aikit-origin: "contrib"', '  aikit-owner: '+json.dumps(owner, ensure_ascii=False),
            '  aikit-summary: '+json.dumps(description, ensure_ascii=False), '  aikit-category: '+json.dumps(category), '  aikit-tier: "optional"']
    body = ['---', 'name: '+name, 'description: '+json.dumps(description, ensure_ascii=False)] + meta + ['---', '', '# '+name, '',
            '<… the steps, in the imperative: what the agent does, in order …>', '', '## Forbidden',
            '<… what the agent must never do with this skill …>']
    if category == 'domain':
        body += ['', '## Rationalizations and rebuttals', '| Excuse | Rebuttal |', '| --- | --- |']
        body += ['| "<… a reason an agent gives to skip a step …>" | <… the reply it gets …> |']*3
        body += ['', '## In the kit commands',
                 '- `/build`: <… what this playbook changes in this step …>']
    case = {'name': name, 'requires': {'skills': [name]}, 'prompt': '<… what a person types …>',
            'expect': {'regex': ['<… what the answer must show …>']},
            '_doc': 'Skeleton to complete: the prompt and the criteria are placeholders, so evals/run.py skips this case until they are written.'}
    return {'skills/contrib/'+name+'/SKILL.md': '\n'.join(body)+'\n',
            next_case_file(repo, name): json.dumps(case, indent=2, ensure_ascii=False)+'\n',
            'docs/eval-cases.md': with_case_section(read(repo, 'docs/eval-cases.md'), name)}


def ask_text(ui, value, message, required_label=None, assume=False, default=''):
    """The option's value, or the question; with --yes, the default, and a required value has none."""
    if value:
        return value
    if assume:
        if required_label:
            raise KitError(required_label+' is required: give it with its option, or run without --yes to be asked.')
        return default
    # default is not offered in the field: what a person types would be added to a placeholder, not replace it.
    return ui.text(message, validate=(lambda v: None if v else 'Required.') if required_label else None) or default


def skill_answers(args, ui, repo):
    owner = ask_text(ui, args.owner, 'Owner (a person or a team, who keeps maintaining it)', '--owner', args.yes)
    description = ask_text(ui, args.description, 'One line: what it does and when to use it (Triggers: …)', None, args.yes, '<… what it does; Triggers: … >')
    category = args.category or ('tool' if args.yes else ui.select('Category', [(c, CATEGORY_LABELS[c]) for c in SKILL_CATEGORIES], 'tool'))
    if category not in SKILL_CATEGORIES:
        raise KitError('--category must be one of '+', '.join(SKILL_CATEGORIES)+'.')
    return skill_changes(repo, args.name, owner, description, category), 'Add contributed skill '+args.name+' (owner '+owner+')'


def agent_changes(repo, name, owner, description):
    body = ['---', 'name: '+name, 'description: '+json.dumps(description, ensure_ascii=False), 'tools: [read_file, grep_search]',
            'max_turns: 12', 'timeout_mins: 5', 'metadata:', '  aikit-version: "1.0.0"', '  aikit-origin: "contrib"',
            '  aikit-owner: '+json.dumps(owner, ensure_ascii=False), '---', '',
            '<… its mission: what the parent gives it, what it looks for, what it never does, what it delivers …>']
    return {'agents/contrib/'+name+'.md': '\n'.join(body)+'\n'}


def agent_answers(args, ui, repo):
    owner = ask_text(ui, args.owner, 'Owner (a person or a team, who keeps maintaining it)', '--owner', args.yes)
    description = ask_text(ui, args.description, 'One line: its mission', None, args.yes, '<… its mission in one line …>')
    return agent_changes(repo, args.name, owner, description), 'Add contributed agent '+args.name+' (owner '+owner+')'


def command_changes(name, description, skill):
    body = ['---', 'name: '+name, 'description: '+json.dumps(description, ensure_ascii=False), 'category: tool',
            'skills: ['+skill+']', 'order: 1000', '---', '',
            'Activate the '+skill+' skill (if this skill is not installed here, follow the instructions below directly).',
            '', 'Input: {{args}}', '', "Answer in the user's language. State in one line the level of ceremony (quick, standard or full) and why.",
            '<… what the command does and how it ends …>']
    return {'commands/'+name+'.md': '\n'.join(body)+'\n'}


def command_answers(args, ui, repo):
    skill = ask_text(ui, args.skill, 'The skill it activates', '--skill', args.yes)
    entry = skill_catalog(repo).get(skill, {})
    if 'path' not in entry:
        raise KitError('Unknown skill "'+skill+'": a command activates a skill of the kit (skills/**/SKILL.md); create it first (ai-kit new skill).')
    if entry.get('category') == 'domain':
        raise KitError('"'+skill+'" is a domain playbook: the steps of the workflow chain it through its "In the kit commands" section; commands stay neutral.')
    description = ask_text(ui, args.description, 'One line in English, shown by /help', None, args.yes, '<… one line in English, shown by /help …>')
    return command_changes(args.name, description, skill), 'Add command '+args.name


def toml_list(key, values):
    return key+' = ['+', '.join(toml_value(v) for v in values)+']'


def profile_changes(repo, name, label, playbooks, agents):
    general = read_toml(repo/'profiles/general.toml')
    highest = max(read_toml(p).get('order', 0) for p in (repo/'profiles').glob('*.toml'))
    skills = general['skills']+[s for s in playbooks if s not in general['skills']]
    lines = ['# A profile: what one job installs. See profiles/general.toml; a domain playbook is never added to general.',
             'id = '+toml_value(name), 'label = '+toml_value(label), 'order = '+str(highest-highest % 10+10),
             toml_list('practices', general['practices']), toml_list('skills', skills), toml_list('mcp', []),
             toml_list('agents', agents), toml_list('commands', general['commands'])]
    return {'profiles/'+name+'.toml': '\n'.join(lines)+'\n'}


def profile_answers(args, ui, repo):
    label = ask_text(ui, args.label, 'Label in the setup menu (Job: what it is for)', '--label', args.yes)
    if '|' in label:
        raise KitError('The label cannot hold a | : it goes into the profile table of the docs.')
    general = read_toml(repo/'profiles/general.toml')
    playbooks, agents = [], general['agents']
    if not args.yes:
        catalog = skill_catalog(repo)
        playbooks = ui.checkbox('Domain playbooks to add', [(n, n, False) for n, e in catalog.items() if e.get('category') == 'domain' and e.get('origin') != 'contrib'])
        known = agent_catalog(repo)
        agents = ui.checkbox('Agents', [(n, n, n in agents) for n, e in known.items() if e.get('origin') != 'contrib'])
    return profile_changes(repo, args.name, label, playbooks, agents), 'Add profile '+args.name


ANSWERS = {'skill': skill_answers, 'agent': agent_answers, 'command': command_answers, 'profile': profile_answers}


def shared_files(kind):
    """What the checks rewrite, on top of the component's own files."""
    return [LOCK] + ([] if WINDOWS else [SNAPSHOT]) + (['docs/getting-started.md'] if kind in ('profile', 'command') else [])


def refuse_changed(paths, run):
    """Uncommitted changes in a file this command rewrites, or in what the version lock and the snapshot read: they would be
    recorded in its commit without being in it, and the branch would fail in CI. Untracked files count: use stash -u."""
    code, out = run(['git', 'status', '--porcelain', '--untracked-files=all', '--', *paths, *DIGESTS_READ])
    if code == 0 and out.strip():
        raise KitError('Uncommitted changes in what this command rewrites or records; commit them or set them aside first (git stash -u):\n'+out.rstrip())


def undo_lines(repo, changes, kind):
    """Before anything is written: how to get back to where this run started, by hand. Nothing is removed for the person."""
    existing = [rel for rel in changes if (repo/rel).exists()]
    # A skill's folder, not only its file: an empty folder left behind keeps the name taken.
    created = list(dict.fromkeys('/'.join(rel.split('/')[:3]) if rel.startswith('skills/contrib/') else rel for rel in changes if not (repo/rel).exists()))
    return ['To undo: git restore -- '+' '.join(existing+shared_files(kind)), '         then delete '+' '.join(created)]


def preview(changes, kind):
    print('Files to write:')
    for rel in changes:
        print('  '+rel)
    print('Then updated by the checks: '+', '.join(shared_files(kind)))


def finish(kind, changes):
    """What is left to the person. A skeleton is recorded at 1.0.0: its first content changes its digest, so it takes a version."""
    left = [rel for rel, text in changes.items() if PLACEHOLDER in text]
    if left:
        print('Still to write, the parts marked '+PLACEHOLDER+' …>:')
        for rel in left:
            print('  '+rel)
    if kind in ('skill', 'agent'):
        print('After writing the content: raise its aikit-version to 1.0.1 in its front matter, then python3 scripts/versions.py --update (the tests refuse a change under the same version).')
        print('To write the content, ask your agent in your CLI to use the write-a-skill skill (extra_skills if it is not installed).')
    if kind == 'profile':
        print('Left to you: the profile table of README.md.')
    if kind == 'command':
        print('Left to you: its entry in docs/tools.md.')


def verify(kind, changes, run, undo):
    """The repo's own scripts, never a copy of what they do: the first failure stops, with its real output."""
    python = sys.executable
    own = [rel for rel in changes if rel.startswith(('skills/contrib/', 'agents/contrib/', 'commands/'))]
    steps = [[python, 'runtime/check_skills.py', *own]] if own else []
    steps += [[python, 'scripts/versions.py', '--update']]
    steps += [] if WINDOWS else [[python, 'tests/snapshot.py', '--update']]
    steps += [[python, 'scripts/profile_table.py', '--write']] if kind in ('profile', 'command') else []
    steps += [[python, '-m', 'unittest', 'discover', '-s', 'tests', '-p', module+'.py'] for module in TARGET_TESTS]
    for command in steps:
        shown = ' '.join(c if c != python else 'python' for c in command)
        code, out = run(command)
        print(('[OK] ' if code == 0 else '[Failed] ')+shown)
        if code != 0:
            print(clean(out))
            print('No commit. The files stay here for review; git status lists them.')
            print('\n'.join(undo))
            return False
    if WINDOWS and kind in ('profile', 'command'):
        print('[Check] tests/golden/install-snapshot.json holds POSIX paths: not rewritten here. On Mac or Linux, python3 tests/snapshot.py --update on this branch, or the CI fails.')
    return True


def current_branch(run):
    code, out = run(['git', 'branch', '--show-current'])
    return out.strip() if code == 0 else ''


def check_branch(kind, name, run):
    """Before anything is written: a branch to start from, and the new branch's name free."""
    if not current_branch(run):
        raise KitError('No current branch (detached HEAD): switch to a branch first.')
    branch = 'new-'+kind+'-'+name
    if run(['git', 'rev-parse', '--verify', '--quiet', 'refs/heads/'+branch])[0] == 0:
        raise KitError('The branch '+branch+' already exists: delete it or choose another name.')
    return branch


def remote_parts(url):
    """(host, path) of a remote, without any user or token it may carry; None when it cannot be read."""
    url = url.strip()
    match = re.fullmatch(r'([a-z+]+)://([^/]+)/(.+?)(?:\.git)?/?', url)
    if match:
        host = match.group(2).rpartition('@')[2]  # the last @: a password may hold one
        return (host.partition(':')[0] if match.group(1).endswith('ssh') else host), match.group(3)  # an ssh port is not the web's
    if '://' in url:  # file:// has no host: no web page to name
        return None
    match = re.fullmatch(r'(?:[^@/\s]+@)?([^:/\s]+):(.+?)(?:\.git)?/?', url)
    return (match.group(1), match.group(2)) if match else None


def merge_request_url(parts, base, branch):
    host, path = parts
    if 'github' in host:
        return 'https://'+host+'/'+path+'/compare/'+base+'...'+branch+'?expand=1'
    return ('https://'+host+'/'+path+'/-/merge_requests/new?merge_request%5Bsource_branch%5D='+branch
            + '&merge_request%5Btarget_branch%5D='+base)


def open_merge_request(parts, base, branch, run):
    """Through the person's own glab or gh when signed in; otherwise, or if it fails, the page to open it by hand."""
    github = bool(parts) and 'github' in parts[0]
    tool = 'gh' if github else 'glab'
    command = ['gh', 'pr', 'create', '--fill', '--base', base] if github else ['glab', 'mr', 'create', '--fill', '--yes', '--target-branch', base]
    if parts and shutil.which(tool) and run([tool, 'auth', 'status'])[0] == 0:
        code, out = run(command)
        print(clean(out) or ('Merge request opened.' if code == 0 else ''))
        if code == 0:
            return
        print(tool+' did not open it.')
    print('Open the merge request here: '+merge_request_url(parts, base, branch) if parts else 'Open the merge request on your host.')


def shown_remote(url):
    """A remote as a person reads it, without any user or token."""
    parts = remote_parts(url)
    return 'https://'+parts[0]+'/'+parts[1] if parts else clean(url.strip())


def ship(paths, message, branch, ui, run, undo):
    """Two questions, always, whatever --yes says: the commit, then the push and the merge request. main never moves."""
    base = current_branch(run)
    fetch_code, fetch_url = run(['git', 'remote', 'get-url', 'origin'])
    push_code, push_url = run(['git', 'remote', 'get-url', '--push', 'origin'])  # where the push really goes: a pushurl can differ
    shown = shown_remote(push_url) if push_code == 0 else 'no remote named origin'
    print('Commit: '+message+'\nBranch: '+branch+' from '+base+'\nRemote: '+shown)
    stat = run(['git', 'diff', '--stat', '--', *paths])[1]
    if stat.strip():
        print(clean(stat))
    if not ui.confirm('Create the branch '+branch+' from '+base+' and commit these files?', default=False):
        print('No commit. The files stay here for review.')
        print('\n'.join(undo))
        return 1
    code, out = run(['git', 'switch', '--quiet', '-c', branch])
    if code != 0:
        print('[Failed] git switch\n'+clean(out)+'\nNo commit. The files stay here for review.')
        print('\n'.join(undo))
        return 1
    for command in (['git', 'add', '--', *paths], ['git', 'commit', '--quiet', '-m', message, '--', *paths]):
        code, out = run(command)
        if code != 0:
            print('[Failed] git '+command[1]+'\n'+clean(out))
            # Back where it started: a hook or a missing identity must not leave the person on an empty branch with a taken name.
            run(['git', 'restore', '--staged', '--', *paths])
            if run(['git', 'switch', '--quiet', base])[0] == 0 and run(['git', 'branch', '-d', branch])[0] == 0:
                print('No commit. Back on '+base+'; the files stay here for review.')
            else:
                print('No commit. Still on '+branch+': git switch '+base+', then git branch -d '+branch+'. The files stay here for review.')
            print('\n'.join(undo))
            return 1
    back = 'You are on '+branch+'. To go back: git switch '+base+'. To undo the commit: git switch '+base+' and git branch -D '+branch+'.'
    if push_code != 0:
        print('Committed on '+branch+'. No remote named origin to push to.\n'+back)
        return 1
    try:
        if not ui.confirm('Push '+branch+' to '+shown+' and open a merge request into '+base+'?', default=False):
            print('Committed on '+branch+'. Nothing pushed.\n'+back)
            return 1
    except Cancelled:
        print('Cancelled: committed on '+branch+', nothing pushed.\n'+back)
        return 130
    code, out = run(['git', 'push', '-u', 'origin', branch])
    if code != 0:
        print('[Failed] git push\n'+clean(out)+'\n'+back)
        return 1
    open_merge_request(remote_parts(fetch_url) if fetch_code == 0 else None, base, branch, run)
    print(back+'\nOn the remote: close the merge request, and git push origin --delete '+branch+'.')
    return 0


def parser():
    p = argparse.ArgumentParser(prog='ai-kit new', description='Create a component of the kit in a clone of its repository.', add_help=True)
    p.add_argument('kind', nargs='?', choices=KINDS, help='what to create')
    p.add_argument('--name')
    p.add_argument('--owner', help='skill, agent: who keeps maintaining it')
    p.add_argument('--description')
    p.add_argument('--category', help='skill: '+', '.join(SKILL_CATEGORIES))
    p.add_argument('--skill', help='command: the skill it activates')
    p.add_argument('--label', help='profile: its label in the setup menu')
    p.add_argument('--yes', action='store_true', help='no question about the content; the commit and the push are always asked')
    p.add_argument('--no-mr', action='store_true', help='stop after the checks: no branch, no commit')
    p.add_argument('--plain', action='store_true')
    return p


def main(argv, repo=None, ui=None, run=None):
    args = parser().parse_args(argv)
    if not args.kind:
        print('What to create: '+', '.join(KINDS)+'. For example: ai-kit new skill --name my-skill --owner my-team')
        return 2
    start = Path(repo).resolve() if repo else None
    run = run or (lambda command: run_command(command, start))
    repo = kit_repo(repo, run)
    if ui is None and not at_terminal() and not (args.no_mr and args.yes):
        raise KitError('ai-kit new asks a person for the commit and the push, and this is not a terminal. Run it in a terminal, or with --no-mr --yes to write the files and stop after the checks.')
    # Before any question. What the component adds or rewrites is under these paths; the case file is a new one.
    refuse_changed([*(['docs/eval-cases.md'] if args.kind == 'skill' else []), *shared_files(args.kind)], run)
    ui = ui or make_ui(args.plain)
    try:
        args.name = args.name or ('' if args.yes else ui.text('Name', validate=lambda v: name_problem(repo, v, args.kind, run)))
        problem = name_problem(repo, args.name, args.kind, run)
        if problem:
            raise KitError(problem)
        branch = None if args.no_mr else check_branch(args.kind, args.name, run)
        changes, message = ANSWERS[args.kind](args, ui, repo)
        preview(changes, args.kind)
        if not args.yes and not ui.confirm('Create them?', default=True):
            print('Nothing written.')
            return 1
    except Cancelled:
        print('Cancelled: nothing written.')
        return 130
    except ValueError as exc:  # a catalog that does not parse, a heading no longer there: located, not a traceback
        raise KitError('The repo is not in the expected shape: '+str(exc)+'. Restore it (git status, git diff), then run this again.')
    undo = undo_lines(repo, changes, args.kind)
    try:
        for rel, text in changes.items():
            path = repo/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='\n') as f:  # the same bytes on Windows: the version digests read them
                f.write(text)
        if not verify(args.kind, changes, run, undo):
            return 1
    except KeyboardInterrupt:  # the checks are the long moment of this command
        print('\nInterrupted: no commit.')
        print('\n'.join(undo))
        return 130
    finish(args.kind, changes)
    if args.no_mr:
        print('Stopped after the checks (--no-mr): no branch, no commit.')
        print('\n'.join(undo))
        return 0
    try:
        return ship([*changes, *shared_files(args.kind)], message, branch, ui, run, undo)
    except Cancelled:
        print('Cancelled: nothing more done. git status and git log say where this stands.')
        print('\n'.join(undo))
        return 130


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
