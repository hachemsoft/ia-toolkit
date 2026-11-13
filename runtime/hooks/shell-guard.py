#!/usr/bin/env python3
"""Shell guardrails of the kit (BeforeTool, shell tools): one script, the rules named on its command line.

    shell-guard.py dbt-prod-guard git-guard ...

Each rule is a guardrail a person turns on by its name in aikit.toml; the installer writes one hook for all of them, with
the names of the ones turned on. A name the script does not know is ignored; with no name, everything passes.

dbt-prod-guard: blocks a dbt command aimed at a production target.
One-off permission: AI_KIT_ALLOW_PROD=1 exported in the shell that starts the CLI (ignored when it comes from a .env file the CLI loads,
which the agent could write). A target only known at run time ($VAR, $(…)) is blocked.
Targets treated as production: prod, production, prd, or the AI_KIT_PROD_TARGETS list (comma-separated).

git-guard: blocks the git commands that discard work for good (reset --hard, clean -f, checkout or restore of the whole
tree, branch -D) and a forced push to a main branch (main, master, or the AI_KIT_PROTECTED_BRANCHES list).
bq-cost-guard: blocks `bq query` without --dry_run and without --maximum_bytes_billed.
infra-prod-guard: blocks terraform apply/destroy and the kubectl commands that change a cluster, when the workspace,
folder, variable file, context or namespace names production. Same one-off permission as dbt-prod-guard.

The three read the programs the command runs, not its text: `echo "git reset --hard"` and `grep -r "kubectl delete" docs`
pass. Limits: docs/hooks.md.

Output: JSON {"decision": "deny", "reason": ...} or {} to let it through. Never an exception towards the CLI.
"""
import json
import os
import re
import shlex
import sys
import time

class _Hit:
    def __init__(self, target):
        self._target = target
    def group(self, _index):
        return self._target

def default_target_hit(command, targets, payload):
    """Without --target or DBT_TARGET, the default target comes from profiles.yml (--profiles-dir, DBT_PROFILES_DIR, ~/.dbt): block it if it is production."""
    if re.search(r'(?:--target|-t)(?:[\s=,]|$)|\bDBT_TARGET=', command, re.I):
        return None
    if os.environ.get('DBT_TARGET', '').lower() in targets:
        return _Hit(os.environ['DBT_TARGET'] + ' (DBT_TARGET in the environment)')
    match = re.search(r'--profiles-dir[\s=]+[\'"]?([^\s\'"]+)', command)
    cwd = payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()
    candidates = []
    if match:
        candidates.append(os.path.join(cwd, match.group(1)) if not os.path.isabs(match.group(1)) else match.group(1))
    if os.environ.get('DBT_PROFILES_DIR'):
        candidates.append(os.environ['DBT_PROFILES_DIR'])
    candidates += [cwd, os.path.join(os.path.expanduser('~'), '.dbt')]
    for directory in candidates:
        path = os.path.join(directory, 'profiles.yml')
        try:
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
        except OSError:
            continue
        # Minimal reading without PyYAML: the `target: <name>` lines indented one level under a profile, and the
        # common Jinja form target: "{{ env_var('DBT_TARGET', 'prod') }}", resolved from the environment or its default.
        for line in re.findall(r'^[ \t]+target:[ \t]*(.+)$', text, re.M):
            jinja = re.search(r'env_var\(\s*[\'"]([A-Za-z0-9_]+)[\'"]\s*(?:,\s*[\'"]([A-Za-z0-9_-]+)[\'"])?', line)
            if jinja:
                found = os.environ.get(jinja.group(1)) or jinja.group(2)
                if not found:
                    return _Hit(line.strip() + ' (a target only known when dbt runs, in ' + path + ')')
            elif '{{' in line:
                return _Hit(line.strip() + ' (a target only known when dbt runs, in ' + path + ')')
            else:
                found = re.match(r'[\'"]?([A-Za-z0-9_-]+)', line.strip()).group(1)
            if found.lower() in targets:
                return _Hit(found + ' (default target from ' + path + ')')
        return None
    return None

def deny_output(payload, reason):
    """Refusal in the shape the CLI expects: Codex and the CLIs using the PreToolUse format validate their output strictly."""
    if payload.get('hook_event_name') == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
    return {'decision': 'deny', 'reason': reason}

def as_text(value):
    """A command can arrive as a string or as a list of arguments (Codex: ["bash", "-lc", "..."])."""
    if isinstance(value, list):
        return ' '.join(str(v) for v in value)
    return str(value or '')

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash',
               'PowerShell', 'powershell')
DEFAULT_TARGETS = ('prod', 'production', 'prd')

def use_utf8():
    """The CLIs send and read UTF-8; on Windows the console defaults to cp1252: force UTF-8 for input and output."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

def unreadable_target(command):
    """Target value that is only resolved by the shell ($VAR, $(…), backticks, glued quotes): unknown, so treated as unsafe."""
    for match in re.finditer(r'(?:(?<![\w-])--target|(?<![\w-])-t|\bDBT_TARGET)(?:[\s=]+|(?<=-t))(\S+)', command):
        value = match.group(1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        if re.search(r'[$`"\']', value):
            return match.group(1)
    return None

def allow_from_env_file(payload):
    """File that sets AI_KIT_ALLOW_PROD among the .env files Gemini loads (repo folders up to the root, then ~/.gemini/.env), or None."""
    cwd = payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()
    candidates, current = [], os.path.abspath(cwd)
    while True:
        candidates += [os.path.join(current, '.gemini', '.env'), os.path.join(current, '.env')]
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    candidates.append(os.path.join(os.path.expanduser('~'), '.gemini', '.env'))
    for path in candidates:
        try:
            with open(path, encoding='utf-8', errors='replace') as handle:
                if re.search(r'^\s*(export\s+)?AI_KIT_ALLOW_PROD\s*=', handle.read(), re.M):
                    return path
        except OSError:
            continue
    return None

def dbt_prod_guard(raw, payload):
    """A dbt command on a production target: a refusal, a note when the person allowed it, or None."""
    # The shell removes backslashes and glued quotes: d''bt, pr\od are dbt and prod. Python calls dbt too (dbtRunner).
    command = raw.replace('\\\n', ' ').replace('\\', '').replace("''", '').replace('""', '')
    # `dbt`, `./dbt`, `/path/dbt`, `dbt.exe`, any case; also right after a quote, a backtick or a parenthesis (`sh -c "dbt …"`, `$(dbt …)`).
    if not (re.search(r'(^|[\s;&|/"\'`(])dbt(\.exe)?(\s|$|["\'`)])', command, re.I) or re.search(r'dbtRunner|dbt\.cli', command)):
        return None
    command = re.sub(r"['\"],\s*['\"]", ' ', command)  # dbtRunner().invoke(['run', '--target', 'prod']): the list as words
    # The organization's extra targets add to the defaults; they can never remove them (a .env cannot turn the guard off).
    extra = [t.strip().lower() for t in os.environ.get('AI_KIT_PROD_TARGETS', '').split(',') if t.strip() and t.strip().lower() != 'none']
    targets = list(dict.fromkeys(list(DEFAULT_TARGETS) + extra))
    alternation = '|'.join(re.escape(t) for t in targets)
    # --target prod, --target=prod, -t prod, -tprod, single or double quotes around the value.
    hits = (re.search(r'(?:--target|-t)(?:[\s=]+|(?<=-t))[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I)
            or re.search(r'\bDBT_TARGET=[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I))
    if not hits:
        unreadable = unreadable_target(command)
        if unreadable:
            return deny_output(payload, 'Blocked by the kit: the dbt target "' + unreadable + '" is only known when the command runs, so the kit cannot tell whether it is production. Write the target in plain text, for example --target dev.')
        hits = default_target_hit(command, targets, payload)
    if not hits:
        return None
    if os.environ.get('AI_KIT_ALLOW_PROD') == '1':
        origin = allow_from_env_file(payload)
        if not origin:
            return {'systemMessage': 'ai-kit: dbt command on a production target allowed by AI_KIT_ALLOW_PROD=1.'}
        return deny_output(payload, 'Blocked by the kit: AI_KIT_ALLOW_PROD is set in ' + origin + ', a file the agent can write. Export it in the shell that starts the CLI instead.')
    return deny_output(payload, 'Blocked by the kit: dbt command on the production target "' + hits.group(1) + '". Use the development target declared in AGENTS.md. An authorised person can export AI_KIT_ALLOW_PROD=1 for this session.')

# --- The programs a command runs (git-guard, bq-cost-guard, infra-prod-guard) ---

HEREDOC = re.compile(r'<<-?\s*[\'"]?([A-Za-z_][A-Za-z0-9_]*)[\'"]?')
SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'pwsh', 'powershell', 'cmd')
# Programs that run the program named after them.
WRAPPERS = ('sudo', 'doas', 'env', 'command', 'exec', 'time', 'nohup', 'nice', 'xargs', 'timeout', 'builtin')

def without_data_heredocs(text):
    """The command without the bodies of heredocs given to a program that is not a shell (cat <<EOF, python3 - <<EOF):
    that text is data. A heredoc given to sh, bash… is kept: it runs as commands."""
    out, skip_until = [], None
    for line in text.split('\n'):
        if skip_until is not None:
            if line.strip() == skip_until:
                skip_until = None
            continue
        out.append(line)
        match = HEREDOC.search(line)
        if match and not any(w.strip('"\'').rsplit('/', 1)[-1].lower() in SHELLS for w in line[:match.start()].split()):
            skip_until = match.group(1)
    return '\n'.join(out)

def program_name(word):
    name = word.rsplit('/', 1)[-1].lower()
    return name[:-4] if name.endswith('.exe') else name

def programs(command, depth=0):
    """(program, its arguments, the VAR=value written before it) for each program the shell would run: one per command of
    a line (; && || | and new lines), after sudo, env, xargs…, inside sh -c "…", eval, $(…) and backticks. A word that is
    only an argument (echo "git reset --hard", grep "kubectl delete") is not a program."""
    text = without_data_heredocs(command.replace('\\\r\n', ' ').replace('\\\n', ' ')).replace('\\', '/')
    text = re.sub(r'\r?\n', ' ; ', text)
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=';&|()')
        lexer.whitespace_split, lexer.commenters = True, ''
        tokens = list(lexer)
    except ValueError:  # an unbalanced quote: the words as written
        tokens = re.sub(r'[;&|()]+', ' ; ', text).replace('"', '').replace("'", '').split()
    found, segment = [], []
    for token in tokens + [';']:
        if not re.fullmatch(r'[;&|()]+', token):
            segment.append(token)
            continue
        words, segment = segment, []
        env, index = {}, 0
        while index < len(words):
            word = words[index]
            assignment = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)', word)
            if assignment:
                env[assignment.group(1)] = assignment.group(2)
            elif not (program_name(word) in WRAPPERS or word.startswith('-') or re.fullmatch(r'[0-9.]+[smhd]?', word)):
                break
            index += 1
        if index < len(words):
            program, args = program_name(words[index]), words[index+1:]
            runs = None
            if program == 'eval':
                runs = ' '.join(args)
            elif program in SHELLS:
                for at, arg in enumerate(args):
                    if re.fullmatch(r'-[a-z]*c|-command|/c|/k', arg.lower()):
                        runs = ' '.join(args[at+1:])
                        break
            if runs is not None and depth < 3:
                found += programs(runs, depth+1)
            else:
                found.append((program, args, env))
        if depth < 3:
            for word in words:  # $(…) and `…` run a command wherever they are written
                for inner in re.split(r'\$\(|`', word)[1:]:
                    found += programs(inner.rstrip(')'), depth+1)
    return found

def working_folder(payload):
    return payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()

def refusal(payload, text):
    return deny_output(payload, 'Blocked by the kit: ' + text)

# --- git-guard ---

GIT_VALUE_OPTIONS = ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--super-prefix')
WHOLE_TREE = ('.', './', ':/', '*')
MAIN_BRANCHES = ('main', 'master')
RUN_IT_YOURSELF = ' The agent does not run it: run it yourself in a terminal if that is what you want.'

def short_flag(args, letter):
    """-f, or the letter in a cluster of short options (-fd, -xdf)."""
    return any(re.fullmatch(r'-[A-Za-z]*' + letter + r'[A-Za-z]*', a) for a in args)

def current_branch(folder):
    """The branch checked out in the repository that holds the folder, read from .git/HEAD; None when it cannot be read."""
    current = os.path.abspath(folder)
    while True:
        git = os.path.join(current, '.git')
        try:
            if os.path.isfile(git):  # a worktree or a submodule: "gitdir: <path>"
                with open(git, encoding='utf-8') as handle:
                    git = os.path.join(current, handle.read().split(':', 1)[1].strip())
            if os.path.isdir(git):
                with open(os.path.join(git, 'HEAD'), encoding='utf-8') as handle:
                    match = re.match(r'ref: refs/heads/(\S+)', handle.read())
                return match.group(1) if match else None
        except (OSError, IndexError):
            return None
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent

def git_guard(raw, payload):
    """A git command that discards work for good, or a forced push to a main branch: a refusal, or None."""
    extra = [b.strip() for b in os.environ.get('AI_KIT_PROTECTED_BRANCHES', '').split(',') if b.strip()]
    protected = set(MAIN_BRANCHES) | set(extra)
    for program, args, _env in programs(raw):
        if program != 'git':
            continue
        folder, index = working_folder(payload), 0
        while index < len(args) and args[index].startswith('-'):  # git's own options, before the subcommand
            if args[index] in GIT_VALUE_OPTIONS and index + 1 < len(args):
                if args[index] == '-C':
                    folder = os.path.join(folder, args[index+1])
                index += 1
            index += 1
        if index >= len(args):
            continue
        verb, rest = args[index], args[index+1:]
        if verb == 'reset' and '--hard' in rest:
            return refusal(payload, '`git reset --hard` discards the changes that are not committed, for good.' + RUN_IT_YOURSELF)
        if verb == 'clean' and (short_flag(rest, 'f') or '--force' in rest) and not (short_flag(rest, 'n') or '--dry-run' in rest):
            return refusal(payload, '`git clean` with -f deletes the files git does not track, for good. `git clean -n` shows them.' + RUN_IT_YOURSELF)
        if verb == 'checkout' and (any(a in WHOLE_TREE for a in rest) or short_flag(rest, 'f') or '--force' in rest):
            return refusal(payload, 'this `git checkout` discards the changes of the whole working tree, for good.' + RUN_IT_YOURSELF)
        if verb == 'restore' and any(a in WHOLE_TREE for a in rest):
            staged_only = ('--staged' in rest or short_flag(rest, 'S')) and not ('--worktree' in rest or short_flag(rest, 'W'))
            if not staged_only:
                return refusal(payload, '`git restore` of the whole working tree discards the changes that are not committed, for good.' + RUN_IT_YOURSELF)
        if verb == 'branch' and (short_flag(rest, 'D') or (('--delete' in rest or short_flag(rest, 'd')) and ('--force' in rest or short_flag(rest, 'f')))):
            return refusal(payload, '`git branch -D` deletes a branch even when its commits are merged nowhere.' + RUN_IT_YOURSELF)
        if verb == 'push':
            refspecs = [a for a in rest if not a.startswith('-')][1:]  # after the remote
            targets = [r.lstrip('+').rsplit(':', 1)[-1].replace('refs/heads/', '') for r in refspecs]
            plain = short_flag(rest, 'f') or '--force' in rest or any(r.startswith('+') for r in refspecs)
            lease = any(a.startswith('--force-with-lease') or a == '--force-if-includes' for a in rest)
            deletes = '--delete' in rest or short_flag(rest, 'd') or any(r.startswith(':') for r in refspecs)
            everything = '--all' in rest or '--mirror' in rest
            if not targets and not everything:
                branch = current_branch(folder)
                targets = [branch] if branch else []
                unknown = branch is None
            else:
                unknown = False
            hit = [t for t in targets if t in protected]
            if (plain or lease or deletes) and hit:
                return refusal(payload, 'this `git push` rewrites or deletes the branch "' + hit[0] + '", which everyone shares.' + RUN_IT_YOURSELF)
            if plain and (everything or unknown):
                return refusal(payload, 'this forced `git push` does not name its branch, so the kit cannot tell whether it is a main branch. Name the branch, for example `git push --force-with-lease origin my-branch`.')
    return None

# --- bq-cost-guard ---

BQ_COMMANDS = ('query', 'ls', 'show', 'mk', 'rm', 'cp', 'load', 'extract', 'head', 'insert', 'update', 'cancel', 'wait', 'mkdef',
               'partition', 'version', 'help', 'init', 'shell', 'get-iam-policy', 'set-iam-policy', 'add-iam-policy-binding',
               'remove-iam-policy-binding', 'truncate', 'undelete')

def bq_cost_guard(raw, payload):
    """`bq query` with neither --dry_run nor --maximum_bytes_billed: a refusal, or None."""
    for program, args, _env in programs(raw):
        if program != 'bq' or next((a for a in args if a in BQ_COMMANDS), None) != 'query':
            continue
        dry = any(re.fullmatch(r'--dry_run(=(true|1))?', a, re.I) for a in args)
        capped = any(re.fullmatch(r'--maximum_bytes_billed(=[1-9][0-9]*)?', a) for a in args)
        if not (dry or capped):
            return refusal(payload, '`bq query` without --dry_run or --maximum_bytes_billed: a query is billed by the bytes it reads. '
                           'Run it with --dry_run first to see the bytes, then with --maximum_bytes_billed=<bytes>.')
    return None

# --- infra-prod-guard ---

KUBECTL_VALUE_OPTIONS = ('--context', '--cluster', '-n', '--namespace', '--kubeconfig', '--user', '-s', '--server', '--as', '--token',
                         '-f', '--filename', '-l', '--selector', '-o', '--output')
KUBECTL_CHANGES = ('delete', 'apply', 'replace', 'patch', 'scale', 'drain', 'edit', 'set', 'create')
KUBECTL_ROLLOUT_CHANGES = ('restart', 'undo', 'pause', 'resume')

def production_names():
    extra = [t.strip().lower() for t in os.environ.get('AI_KIT_PROD_TARGETS', '').split(',') if t.strip() and t.strip().lower() != 'none']
    return list(dict.fromkeys(list(DEFAULT_TARGETS) + extra))

def names_production(value, names):
    """prod, my-prod-cluster, envs/prod, gke_project_prod_eu: one of the words of the value is a production name."""
    return any(piece in names for piece in re.split(r'[^a-z0-9]+', str(value).lower()))

def option_values(args, options):
    """The values of --opt value and --opt=value, for the options named."""
    found = []
    for index, arg in enumerate(args):
        if arg in options and index + 1 < len(args):
            found.append((arg, args[index+1]))
        else:
            for option in options:
                if arg.startswith(option + '='):
                    found.append((option, arg[len(option)+1:]))
    return found

def read_text(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''

def folders_below_repo(folder):
    """The folder names from the repository root down to the folder (envs/prod); the folder's own name outside a repository."""
    current, names = os.path.abspath(folder), []
    while True:
        if os.path.exists(os.path.join(current, '.git')):
            return names
        parent = os.path.dirname(current)
        if parent == current:
            return [os.path.basename(os.path.abspath(folder))]
        names.append(os.path.basename(current))
        current = parent

def terraform_evidence(args, env, payload, names):
    """What names production for a terraform apply or destroy, or None."""
    folder = working_folder(payload)
    for _option, value in option_values(args, ('-chdir',)):
        if names_production(value, names):
            return 'the folder "' + value + '"'
        folder = os.path.join(folder, value)
    for _option, value in option_values(args, ('-var-file', '--var-file')):
        if names_production(value, names):
            return 'the variable file "' + value + '"'
    workspace = env.get('TF_WORKSPACE') or os.environ.get('TF_WORKSPACE') or read_text(os.path.join(folder, '.terraform', 'environment')).strip()
    if workspace and names_production(workspace, names):
        return 'the workspace "' + workspace + '"'
    for name in folders_below_repo(folder):
        if names_production(name, names):
            return 'the folder "' + name + '"'
    return None

def kubectl_evidence(args, env, names):
    """What names production for a kubectl command, or None. Without --context, the current context of the kubeconfig."""
    chosen = option_values(args, ('--context', '--cluster', '-n', '--namespace'))
    for option, value in chosen:
        if re.search(r'[$`]', value):
            return option + ' "' + value + '", only known when the command runs'
        if names_production(value, names):
            return option + ' "' + value + '"'
    if any(option in ('--context', '--cluster') for option, _value in chosen):
        return None
    files = [v for _o, v in option_values(args, ('--kubeconfig',))] or (env.get('KUBECONFIG') or os.environ.get('KUBECONFIG') or '').split(os.pathsep)
    for path in [f for f in files if f] or [os.path.join(os.path.expanduser('~'), '.kube', 'config')]:
        match = re.search(r'^current-context:[ \t]*[\'"]?([^\s\'"]+)', read_text(os.path.expanduser(path)), re.M)
        if match:
            return 'the current context "' + match.group(1) + '"' if names_production(match.group(1), names) else None
    return None

def infra_prod_guard(raw, payload):
    """terraform apply/destroy or a kubectl command that changes a cluster, on production: a refusal, a note when allowed, or None."""
    names = production_names()
    for program, args, env in programs(raw):
        what = evidence = None
        if program in ('terraform', 'tofu', 'terragrunt'):
            verb = next((a for a in args if not a.startswith('-')), None)
            if verb in ('apply', 'destroy'):
                what, evidence = program + ' ' + verb, terraform_evidence(args, env, payload, names)
        elif program == 'kubectl':
            words, index = [], 0
            while index < len(args):
                if args[index] in KUBECTL_VALUE_OPTIONS:
                    index += 1
                elif not args[index].startswith('-'):
                    words.append(args[index])
                index += 1
            if words and (words[0] in KUBECTL_CHANGES or (words[0] == 'rollout' and words[1:2] and words[1] in KUBECTL_ROLLOUT_CHANGES)):
                what, evidence = 'kubectl ' + words[0], kubectl_evidence(args, env, names)
        if not evidence:
            continue
        if os.environ.get('AI_KIT_ALLOW_PROD') == '1':
            origin = allow_from_env_file(payload)
            if not origin:
                return {'systemMessage': 'ai-kit: ' + what + ' on production allowed by AI_KIT_ALLOW_PROD=1.'}
            return refusal(payload, 'AI_KIT_ALLOW_PROD is set in ' + origin + ', a file the agent can write. Export it in the shell that starts the CLI instead.')
        return refusal(payload, '`' + what + '` on production (' + evidence + '). The agent does not change production: run it yourself, '
                       'or an authorised person can export AI_KIT_ALLOW_PROD=1 for this session.')
    return None

def record_refusal(guardrail):
    """One line per refusal in ~/.ai-kit/refusals.jsonl: when, and which guardrail; never the command, so no path and no
    secret is kept. `ai-kit usage` counts them. Only the installed copy records (the one in ~/.ai-kit/hooks), not a
    doctor probe; the file keeps its last 1000 lines. A failure to record never changes the answer."""
    folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.basename(folder) != '.ai-kit' or os.environ.get('AI_KIT_PROBE') == '1':
        return
    path = os.path.join(folder, 'refusals.jsonl')
    try:
        if os.path.exists(path) and os.path.getsize(path) > 200000:
            with open(path, encoding='utf-8', errors='replace') as handle:
                kept = handle.readlines()[-1000:]
            with open(path, 'w', encoding='utf-8') as handle:
                handle.writelines(kept)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'guardrail': guardrail}) + '\n')
    except OSError:
        pass

def passes(payload, note=None):
    """The answer that lets a tool call through. agy requires a decision in every answer (its hooks docs: `decision`,
    required) and refuses an empty object without a reason; "allow" hands the call to agy's own permissions. The other
    CLIs read an empty object as nothing to say."""
    answer = dict(note or {})
    if isinstance(payload, dict) and 'toolCall' in payload:
        answer['decision'] = 'allow'
    return json.dumps(answer, ensure_ascii=False)

# The rules this script knows, by the guardrail name a person writes in aikit.toml.
RULES = {'dbt-prod-guard': dbt_prod_guard, 'git-guard': git_guard, 'bq-cost-guard': bq_cost_guard, 'infra-prod-guard': infra_prod_guard}

def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    # Three input shapes: Gemini CLI (tool_name / tool_input.command), Antigravity (toolCall.name / toolCall.args.CommandLine),
    # Codex (hook_event_name PreToolUse, tool_name / tool_input.command as a string or a list).
    call = payload.get('toolCall') or {}
    tool = payload.get('tool_name') or call.get('name')
    if tool not in SHELL_TOOLS:
        print(passes(payload))
        return
    args = payload.get('tool_input') or call.get('args') or {}
    if not isinstance(args, dict):
        args = {'command': args}
    raw = as_text(args.get('command') or args.get('cmd') or args.get('CommandLine'))
    note = None
    for name in dict.fromkeys(sys.argv[1:]):
        rule = RULES.get(name)
        if not rule:
            continue
        try:
            answer = rule(raw, payload)
        except Exception:
            answer = None  # a rule that fails lets the command through: a broken guardrail must not stop every command
        if answer and 'systemMessage' not in answer:
            record_refusal(name)
            print(json.dumps(answer, ensure_ascii=False))
            return
        note = note or answer
    print(passes(payload, note))

if __name__ == '__main__':
    main()
