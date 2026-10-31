"""Claude Code adapter: a managed block of imports in ~/.claude/CLAUDE.md, skills, commands and agents in ~/.claude,
guardrails in ~/.claude/settings.json, MCP servers in ~/.claude.json, and the session transcripts for usage.

Claude Code ships skills of its own (code-review) and people keep personal skills in ~/.claude/skills, often with the
same names as the kit's: the kit's skills are installed with a prefix (skill_prefix in overrides.json, ai-kit- by
default) and the texts the kit installs name them that way. A command keeps its name unless a personal skill or command
already has it; it is then installed with the same prefix and the person is told."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Optional

from ..interface import DoctorContext, Plan, Status
from ..core import (ROOT, USER_CONTEXT, KitError, digest, hook_command, split_block, place_block, json_bytes, read_json, run_timed,
                    record_auto_friction, _ts)

CLAUDE_DIR = '.claude'
CLAUDE_MD = ('<!-- ai-kit:start : block managed by the AI Kit; do not edit here (30_USER.md, overrides.json, then update) -->', '<!-- ai-kit:end -->')
DEFAULT_PREFIX = 'ai-kit-'
PREFIX = re.compile(r'([a-z0-9][a-z0-9-]{0,19})?')
# Skills Claude Code itself ships: a kit skill installed without a prefix must not take one of these names.
BUNDLED_SKILLS = {'code-review', 'security-review', 'simplify', 'init', 'loop', 'schedule', 'claude-api', 'update-config',
                  'keybindings-help', 'fewer-permission-prompts', 'run', 'plugin-authoring', 'workflow-authoring'}
# Tools of the kit's agent definitions, in Claude Code's names.
TOOL_NAMES = {'read_file': 'Read', 'grep_search': 'Grep', 'list_directory': 'Glob', 'glob': 'Glob', 'run_shell_command': 'Bash'}
KIT_HOOK = re.compile(r'[\\/]\.ai-kit[\\/]hooks[\\/]')
LIVE_PROMPT = 'Reply with OK only.'

# --- Adapter interface ---------------------------------------------------------------------------------------------
NAME = 'claude'
LABEL = 'Claude Code'
COMMAND = 'claude'
HOME_DIR = CLAUDE_DIR
AGENT_TOOLS = 'native'  # an agent's "tools" list is the only set of tools Claude Code gives it
OBSERVES = {'prompt', 'skill', 'agent', 'error'}  # the session transcripts hold every tool call
MANAGED_PREFIXES = (CLAUDE_DIR+'/skills/', CLAUDE_DIR+'/commands/', CLAUDE_DIR+'/agents/ai-kit-')
BUILTIN_COMMANDS = {'add-dir', 'advisor', 'agents', 'alias', 'autocompact', 'branch', 'brief', 'btw', 'bug', 'cd', 'chrome', 'clear',
                    'color', 'compact', 'config', 'context', 'copy', 'cost', 'daemon', 'doctor', 'effort', 'exit', 'export', 'feedback',
                    'focus', 'fork', 'goal', 'help', 'hooks', 'ide', 'import', 'init', 'insights', 'keybindings', 'login', 'logout',
                    'loops', 'mcp', 'memory', 'model', 'permissions', 'plan', 'plugin', 'recap', 'reload-plugins', 'reload-skills',
                    'resume', 'rewind', 'skills', 'status', 'statusline', 'tasks', 'theme', 'todos', 'usage', 'vim', 'voice',
                    'code-review', 'security-review', 'simplify', 'loop', 'schedule'}


def skill_prefix(overrides):
    value = overrides.get('skill_prefix', DEFAULT_PREFIX)
    if not isinstance(value, str) or not PREFIX.fullmatch(value):
        raise KitError('skill_prefix must be up to 20 lowercase letters, digits or dashes (for example "ai-kit-" or "kit-"), or "" for none.')
    return value


def renamer(names, prefix):
    """Rewrites the references to the given skills in a kit text: `tdd`, "tdd", /tdd, the tdd skill → the prefixed names."""
    if not prefix or not names:
        return lambda text: text
    alternatives = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    pattern = re.compile(r'(?<![\w/.-])(`|"|/)?(' + alternatives + r')(?![\w-])(?=(`|"|\s+skill\b)?)')
    def replace(match):
        opener, name, closer = match.group(1), match.group(2), match.group(3)
        if not opener and not closer:
            return match.group(0)  # a plain word: the block of CLAUDE.md tells how to read it
        return (opener or '') + prefix + name
    return lambda text: pattern.sub(replace, text)


def front_matter_name(text, name):
    return re.sub(r'^(---\n(?:.*\n)*?)name:[^\n]*\n', lambda m: m.group(1)+'name: '+name+'\n', text, count=1)


def command_text(command, prompt):
    header = ['---', 'description: '+json.dumps(command['description'], ensure_ascii=False), '---', '']
    return '\n'.join(header) + prompt.replace('{{args}}', '$ARGUMENTS').strip() + '\n'


def agent_text(name, definition, defaults, body):
    tools = list(dict.fromkeys(TOOL_NAMES.get(t, t) for t in definition.get('tools', defaults.get('tools', []))))
    header = ['---', 'name: '+name, 'description: '+json.dumps(definition['description'], ensure_ascii=False), 'tools: '+', '.join(tools), '---', '']
    return '\n'.join(header) + body.strip() + '\n'


def import_path(home, path):
    """How CLAUDE.md names a file: from ~ for the person's own home (no space or accent to quote), absolute otherwise."""
    if home == Path.home().resolve():
        return '~/'+path.relative_to(home).as_posix()
    return path.as_posix()


def block_text(p: Plan, prefix, renamed):
    lines = [CLAUDE_MD[0], '# AI Kit (Claude Code)', '', 'The kit context, imported from its files:', '']
    lines += ['@'+import_path(p.home, p.context_dir/name) for name in list(p.context_names)+[USER_CONTEXT]]
    lines += ['', 'In Claude Code:']
    if prefix:
        lines.append('- The kit\'s skills carry the prefix `'+prefix+'` (`'+prefix+'tdd` for `tdd`): wherever a kit text names a skill without it, use the prefixed name.')
    if renamed:
        lines.append('- Kit commands renamed because one of your own skills or commands has the same name: '
                     + ', '.join('/'+old+' is /'+new for old, new in sorted(renamed.items()))+'.')
    lines.append('- Claude Code loads CLAUDE.md, not AGENTS.md: in a repo, read the AGENTS.md at its root, and the one of the area you work in,'
                 ' before working, unless a CLAUDE.md there already imports it. The only CLAUDE.md the kit allows in a repo is one line,'
                 ' `@AGENTS.md`, which init-project-context proposes.')
    lines.append(CLAUDE_MD[1])
    return '\n'.join(lines)


def was_installed(state):
    return NAME in ((state.get('installed') or {}).get('clis') or [])


def present(home):
    return bool(shutil.which(COMMAND)) or (home/CLAUDE_DIR/'settings.json').is_file()


def is_managed(rel):
    return rel.startswith(MANAGED_PREFIXES)


def active_account(home):
    return None  # the Claude account lives with Claude Code's credentials


def install(p: Plan) -> None:
    """Skills (prefixed), commands (renamed on a collision) and agents in ~/.claude."""
    claude = p.home/CLAUDE_DIR
    prefix = skill_prefix(p.overrides)
    owned = set(p.old_files)
    if not prefix:
        taken = [s for s in p.selected if s in BUNDLED_SKILLS or ((claude/'skills'/s).exists() and not any(r.startswith(CLAUDE_DIR+'/skills/'+s+'/') for r in owned))]
        if taken:
            raise KitError('skill_prefix is empty, but these kit skills have the name of a skill already in ~/.claude/skills or shipped with'
                           ' Claude Code: '+', '.join(taken)+'. Set a prefix (for example "ai-kit-") or rename your own skills.')
    rewrite = renamer(p.selected, prefix)
    for skill, source in p.skill_sources:
        for src in source.rglob('*'):
            if not src.is_file():
                continue
            data = p.skill_file(skill, source, src)
            if src.suffix == '.md':
                text = rewrite(data.decode('utf-8'))
                if src == source/'SKILL.md':
                    text = front_matter_name(text, prefix+skill)
                data = text.encode('utf-8')
            p.managed_write(claude/'skills'/(prefix+skill)/src.relative_to(source), data, 'Claude Code skill')
    renamed = {}
    for command in p.commands:
        name = command['name']
        rel_skill, rel_command = CLAUDE_DIR+'/skills/'+name, CLAUDE_DIR+'/commands/'+name+'.md'
        personal = ((claude/'skills'/name).exists() and not any(r.startswith(rel_skill+'/') for r in owned)) \
            or ((claude/'commands'/(name+'.md')).exists() and rel_command not in owned)
        if personal:
            if not prefix:
                raise KitError('The kit command /'+name+' has the name of one of your own skills or commands in ~/.claude, and skill_prefix is empty: set a prefix.')
            renamed[name] = prefix+name
        p.managed_write(claude/'commands'/((prefix+name if personal else name)+'.md'), command_text(command, rewrite(command['prompt'])).encode('utf-8'), 'Claude Code command')
    defaults = read_json(ROOT/'agents/defaults.json')
    for agent, definition in p.agents:
        name = 'ai-kit-'+agent
        p.managed_write(claude/'agents'/(name+'.md'), agent_text(name, definition, defaults, rewrite(p.agent_body(definition))).encode('utf-8'), 'Claude Code agent')
    data = p.adapter_data.setdefault(NAME, {})
    data.update({'prefix': prefix, 'renamed': renamed})
    if renamed:
        p.notices.append('[Info] Claude Code: '+', '.join('/'+o+' installed as /'+n for o, n in sorted(renamed.items()))
                         + ', because one of your own skills or commands in ~/.claude already has that name.')


def kit_groups(groups):
    return [i for i, g in enumerate(groups) if isinstance(g, dict) and any(isinstance(h, dict) and KIT_HOOK.search(str(h.get('command', ''))) for h in g.get('hooks', []))]


def hook_matcher(manifest_matcher):
    parts = manifest_matcher.split('|')
    tools = (['Bash'] if 'run_shell_command' in parts else []) + (['Write', 'Edit', 'MultiEdit', 'NotebookEdit'] if any(x != 'run_shell_command' for x in parts) else [])
    return '|'.join(tools)


def claude_server(name, server):
    """A kit MCP server (the Gemini settings form) in Claude Code's form."""
    if server.get('cwd'):
        raise KitError('MCP '+name+': "cwd" is not supported by Claude Code; give the full path in "command" instead.')
    if server.get('command'):
        out = {'type': 'stdio', 'command': server['command'], 'args': list(server.get('args', []))}
        if server.get('env'):
            out['env'] = dict(server['env'])
        return out
    out = {'type': 'http', 'url': server['httpUrl']} if server.get('httpUrl') else {'type': 'sse', 'url': server['url']}
    if server.get('headers'):
        out['headers'] = dict(server['headers'])
    return out


def finalize(p: Plan, active: bool = True) -> None:
    """The managed block of ~/.claude/CLAUDE.md, the kit's guardrail groups in ~/.claude/settings.json and its MCP servers
    in ~/.claude.json. Each is checked against what the kit last wrote: a kit entry edited by hand stops the update.
    Inactive: removes what a previous installation had put there; the rest of each file is the person's and stays."""
    if not active and not was_installed(p.state):
        return
    old_blocks = p.state.get('blocks', {})
    # CLAUDE.md
    rel = CLAUDE_DIR+'/CLAUDE.md'
    path = p.home/rel
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    before, old_block, after = split_block(original, CLAUDE_MD, '~/.claude/CLAUDE.md')
    if old_block is not None and old_blocks.get(rel) != digest(old_block.encode('utf-8')):
        raise KitError('Kit block edited by hand in ~/.claude/CLAUDE.md: move your changes outside the block, remove the block, then update.')
    outside = before.rstrip('\n')+('\n' if before.strip() and after.strip() else '')+after.lstrip('\n')
    block = block_text(p, p.adapter_data[NAME]['prefix'], p.adapter_data[NAME]['renamed']) if active else None
    if block is not None:
        p.blocks[rel] = digest(block.encode('utf-8'))
    text = place_block(outside, block, 'top')
    if text != original and (block is not None or old_block is not None):
        p.writes[path] = text.encode('utf-8')
    # settings.json: guardrails
    rel = CLAUDE_DIR+'/settings.json'
    path = p.home/rel
    settings = read_json(path) if path.exists() else {}
    hooks = settings.get('hooks', {})
    if not isinstance(hooks, dict) or not isinstance(hooks.get('PreToolUse', []), list):
        raise KitError('~/.claude/settings.json: hooks.PreToolUse must be a list; configuration left untouched.')
    groups = hooks.get('PreToolUse', [])
    mine = [groups[i] for i in kit_groups(groups)]
    if mine and old_blocks.get(rel) != digest(json_bytes(mine)):
        raise KitError('Kit guardrail edited by hand in ~/.claude/settings.json (hooks.PreToolUse): put it back or remove it, then update.')
    new_groups = []
    if active:
        for name, spec in p.hook_manifest.items():
            if name in p.enabled_hooks:
                new_groups.append({'matcher': hook_matcher(spec['matcher']),
                                   'hooks': [{'type': 'command', 'command': hook_command(p.hooks_dir/spec['script']), 'timeout': 20}]})
    if mine or new_groups:
        kept = [g for i, g in enumerate(groups) if i not in kit_groups(groups)] + new_groups
        if kept:
            hooks['PreToolUse'] = kept
        else:
            hooks.pop('PreToolUse', None)
        if hooks:
            settings['hooks'] = hooks
        else:
            settings.pop('hooks', None)
        p.writes[path] = json_bytes(settings)
    if new_groups:
        p.blocks[rel] = digest(json_bytes(new_groups))
    # ~/.claude.json: MCP servers
    rel = '.claude.json'
    path = p.home/rel
    previous = [name for name in p.state.get('mcp', {}) if name.startswith('ai-kit-')] if was_installed(p.state) else []
    data = read_json(path) if path.exists() and (previous or (active and p.enabled_mcp)) else {}
    servers = data.get('mcpServers', {})
    if not isinstance(servers, dict):
        raise KitError('~/.claude.json: mcpServers must be an object; configuration left untouched.')
    current = {name: servers[name] for name in previous if name in servers}
    if current and old_blocks.get(rel) != digest(json_bytes(current)):
        raise KitError('Kit MCP server edited by hand in ~/.claude.json: put it back or remove it, then update.')
    wanted = {name: claude_server(name, server) for name, server in p.enabled_mcp.items()} if active else {}
    for name in wanted:
        if name in servers and name not in previous:
            raise KitError('MCP name already in use in ~/.claude.json: '+name)
    if current or wanted:
        for name in current:
            servers.pop(name)
        servers.update(wanted)
        data['mcpServers'] = servers
        p.writes[path] = json_bytes(data)
    if wanted:
        p.blocks[rel] = digest(json_bytes(wanted))


def summary(p: Plan) -> Optional[str]:
    prefix = p.adapter_data.get(NAME, {}).get('prefix', DEFAULT_PREFIX)
    return ('Claude Code: kit context imported by ~/.claude/CLAUDE.md, skills named '+(prefix or '(no prefix) ')+'…, commands and ai-kit-* agents in'
            ' ~/.claude, guardrails in ~/.claude/settings.json'+(', MCP servers in ~/.claude.json' if p.enabled_mcp else '')
            + '. Close open Claude Code sessions before an update (they rewrite ~/.claude.json), then start a new one.')


def doctor(home: Path, state: dict, status: Status, ctx: DoctorContext) -> None:
    if not shutil.which(COMMAND):
        print('[Info] Claude Code set up by the kit but not on the PATH.')
    blocks = state.get('blocks', {})
    path = home/CLAUDE_DIR/'CLAUDE.md'
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    try:
        _, block, _ = split_block(text, CLAUDE_MD, '~/.claude/CLAUDE.md')
    except KitError as exc:
        status(False, str(exc))
        block = None
    status(block is not None and digest(block.encode('utf-8')) == blocks.get(CLAUDE_DIR+'/CLAUDE.md'), 'Kit block intact in ~/.claude/CLAUDE.md')
    for line in (block or '').splitlines():
        if line.startswith('@'):
            target = Path(os.path.expanduser(line[1:]))
            status(target.is_file(), 'File imported by ~/.claude/CLAUDE.md present: '+line[1:])
    if state.get('hooks'):
        settings = read_json(home/CLAUDE_DIR/'settings.json') if (home/CLAUDE_DIR/'settings.json').is_file() else {}
        groups = (settings.get('hooks') or {}).get('PreToolUse', [])
        mine = [groups[i] for i in kit_groups(groups)] if isinstance(groups, list) else []
        status(bool(mine) and digest(json_bytes(mine)) == blocks.get(CLAUDE_DIR+'/settings.json'), 'Guardrails configured in ~/.claude/settings.json')
    kit_servers = [name for name in state.get('mcp', {})]
    if kit_servers:
        data = read_json(home/'.claude.json') if (home/'.claude.json').is_file() else {}
        missing = [n for n in kit_servers if n not in (data.get('mcpServers') or {})]
        status(not missing, 'MCP servers in ~/.claude.json'+(' (missing '+', '.join(missing)+': Claude Code may have rewritten the file while'
               ' a session was open; close Claude Code, then update)' if missing else ''))
    commands = sorted(rel.split('/')[2][:-3] for rel in state.get('files', {}) if rel.startswith(CLAUDE_DIR+'/commands/'))
    kit_skills = set((state.get('installed') or {}).get('skills', []))
    personal = sorted(c.name for c in (home/CLAUDE_DIR/'skills').iterdir() if c.is_dir() and c.name in kit_skills
                      and not any(r.startswith(CLAUDE_DIR+'/skills/'+c.name+'/') for r in state.get('files', {}))) if (home/CLAUDE_DIR/'skills').is_dir() else []
    if personal:
        print('[Info] Your own skills in ~/.claude/skills with the name of a kit skill (both are available; the kit\'s carry its prefix): '+', '.join(personal))
    print('[Info] Claude Code: '+str(len(commands))+' kit commands ('+', '.join('/'+c for c in commands[:6])+(' …' if len(commands) > 6 else '')+').')


def doctor_hint():
    return 'Claude Code: check /memory, /skills, /agents, /hooks and /mcp in a session.' if shutil.which(COMMAND) else None


def live(home):
    """Real call to the model (doctor --live only), with a generic diagnosis; 0 if Claude Code answers."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = run_timed([COMMAND, '-p', LIVE_PROMPT, '--max-turns', '1'], 90, cwd=tmp, text=True, encoding='utf-8', stdin=subprocess.DEVNULL)
            output, code = proc.stdout+'\n'+proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            output, code = '', None
        except OSError as exc:
            output, code = str(exc), None
    if code == 0 and 'OK' in output:
        print('[OK] Real call to the model: Claude Code answers.')
        return 0
    diagnostic = ('Claude Code did not answer in time.' if code is None and not output else
                  'Claude Code did not answer as expected (code '+str(code)+').')
    print('[Check] '+diagnostic)
    print('        Fix: start claude and sign in (/login) following your IT procedure; behind a company proxy, Claude Code uses HTTPS_PROXY.'
          ' Never disable certificate checks.')
    record_auto_friction(home, diagnostic, NAME)
    return 1


COMMAND_TAG = re.compile(r'<command-name>(/[^<]+)</command-name>(?:.*?<command-args>(.*?)</command-args>)?', re.S)


def history(home, state):
    """Usage events from ~/.claude/projects/*/*.jsonl: prompts (a slash command as /name), skills called through the Skill
    tool (the prefix removed), ai-kit-* agents, API errors."""
    root = home/CLAUDE_DIR/'projects'
    if not root.is_dir():
        return
    kit_skills = set((state.get('installed') or {}).get('skills', []))
    def unprefixed(name):
        """The kit name of a skill called with its prefix (ai-kit-tdd → tdd), whatever the prefix was."""
        if name in kit_skills:
            return name
        return next((s for s in sorted(kit_skills, key=len, reverse=True) if len(name) > len(s) and name.endswith(s)), name)
    for path in sorted(root.glob('*/*.jsonl')):
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            ts = _ts(entry.get('timestamp'))
            session = 'claude:'+str(entry.get('sessionId') or path.stem)
            content = (entry.get('message') or {}).get('content') if isinstance(entry.get('message'), dict) else None
            if entry.get('isApiErrorMessage'):
                yield {'kind': 'error', 'session': session, 'ts': ts}
            elif entry.get('type') == 'user' and isinstance(content, str) and not entry.get('isMeta'):
                tag = COMMAND_TAG.search(content)
                text = (tag.group(1)+' '+(tag.group(2) or '')).strip() if tag else content.strip()
                yield {'kind': 'prompt', 'session': session, 'ts': ts, 'text': text}
            elif entry.get('type') == 'assistant' and isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get('type') != 'tool_use':
                        continue
                    data = item.get('input') or {}
                    if item.get('name') == 'Skill' and data.get('skill'):
                        yield {'kind': 'skill', 'session': session, 'ts': ts, 'name': unprefixed(str(data['skill']))}
                    elif item.get('name') in ('Agent', 'Task') and str(data.get('subagent_type', '')).startswith('ai-kit-'):
                        yield {'kind': 'agent', 'session': session, 'ts': ts, 'name': str(data['subagent_type'])}
