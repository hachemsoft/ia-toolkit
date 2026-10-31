"""Codex CLI adapter: skills in ~/.codex/skills, managed blocks in ~/.codex/AGENTS.md and ~/.codex/config.toml."""
import json
import re
import shutil

from pathlib import Path
from typing import Optional

from ..interface import DoctorContext, Plan, Status
from ..core import (USER_CONTEXT, KitError, digest, hook_command, split_block, place_block, command_skill_text, redact, user_context_refusal,
                    skill_prefix, free_name, rename_references, renamed_skill_file, renamed_notice, _ts, live_call, LIVE_PROMPT, skills_read)

CODEX_DIR = '.codex'
# Managed block markers: no path, so they never change when a folder is renamed.
CODEX_MD = ('<!-- ai-kit:start : block managed by the AI Kit; do not edit here (30_USER.md, overrides.json, then update) -->', '<!-- ai-kit:end -->')
CODEX_TOML = ('# >>> ai-kit : block managed by the AI Kit; do not edit here (overrides.json, then update) >>>', '# <<< ai-kit <<<')
# Markers written by earlier versions (French, before and after 0.18): recognised to take the block over, then replaced.
LEGACY_STARTS = {
    CODEX_MD[0]: ('<!-- ai-kit:début : bloc géré par le kit IA ; modifier ~/.gemini/30_USER.md ou ~/.ai-toolkit/overrides.json, puis update -->',
                  '<!-- ai-kit:début : bloc géré par le Kit IA ; ne pas le modifier ici (30_USER.md, overrides.json, puis update) -->'),
    CODEX_TOML[0]: ('# >>> ai-kit : bloc géré par le kit IA ; modifier ~/.ai-toolkit/overrides.json, puis update >>>',
                    '# >>> ai-kit : bloc géré par le Kit IA ; ne pas le modifier ici (overrides.json, puis update) >>>'),
}
LEGACY_ENDS = {
    CODEX_MD[1]: ('<!-- ai-kit:fin -->',),
    CODEX_TOML[1]: (),
}
CODEX_EXPLICIT_ONLY = 'policy:\n  allow_implicit_invocation: false\n'

def explicit_only(skill_text):
    """Skill marked "on command only" in its front matter (disable-model-invocation: true)."""
    head = skill_text.split('\n---', 1)[0] if skill_text.startswith('---') else ''
    return bool(re.search(r'^disable-model-invocation:\s*true\s*$', head, re.M))

def normalize_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')

def read_block(text, markers, label):
    """Like split_block, but also recognises legacy markers. Returns (before, block with current markers, after, block as written)."""
    legacy = next((old for old in LEGACY_STARTS[markers[0]] if old in text), None)
    legacy_end = next((old for old in LEGACY_ENDS[markers[1]] if old in text), None)
    if legacy:
        text = text.replace(legacy, markers[0], 1)
    if legacy_end:
        text = text.replace(legacy_end, markers[1], 1)
    before, block, after = split_block(text, markers, label)
    written = block  # the block as it was written and recorded
    if block is not None and legacy:
        written = written.replace(markers[0], legacy, 1)
    if block is not None and legacy_end:
        written = written[:-len(markers[1])]+legacy_end
    return before, block, after, written

def toml_value(value):
    """TOML string, list or inline table; a JSON string is a valid TOML string."""
    if isinstance(value, dict):
        return '{ '+', '.join(json.dumps(str(k), ensure_ascii=False)+' = '+toml_value(v) for k, v in value.items())+' }'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '['+', '.join(toml_value(v) for v in value)+']'
    return json.dumps(str(value), ensure_ascii=False)

USER_COPY = '<!-- Copy of 30_USER.md, refreshed by update. -->'

def copied_user_text(block):
    """The copy of 30_USER.md inside a kit block of ~/.codex/AGENTS.md, or ''."""
    if not block or USER_COPY not in block:
        return ''
    return block.split(USER_COPY, 1)[1].rsplit(CODEX_MD[1], 1)[0].strip()

def codex_context_block(kit_text, practice_texts, user_text, renamed=None):
    lines = [CODEX_MD[0], '# AI Kit (Codex)', '',
             'In Codex, the kit commands are skills: they are called with `$intent`, `$build`, `$test`… (`/skills` lists them). Wherever this context or a skill writes `/intent`, read `$intent`, and in your answers always write kit commands with `$` (`$intent`), never with `/`.']
    if renamed:
        lines.append('Installed under another name, because one of the person\'s own skills already has the name: '
                     + ', '.join('`'+old+'` is `'+new+'`' for old, new in sorted(renamed.items()))+'.')
    lines += ['', kit_text.strip(), '']
    lines += [t.strip()+'\n' for t in practice_texts]
    if user_text.strip():
        lines += [USER_COPY, user_text.strip(), '']
    lines.append(CODEX_MD[1])
    return '\n'.join(lines)

def codex_config_block(agent_entries, hook_commands, mcp_servers):
    lines = [CODEX_TOML[0]]
    for name, (description, config_file) in agent_entries.items():
        lines += ['', '[agents.'+name+']', 'description = '+toml_value(description), 'config_file = '+toml_value(config_file)]
    for command in hook_commands:
        lines += ['', '[[hooks.PreToolUse]]', 'matcher = ".*"', '', '[[hooks.PreToolUse.hooks]]', 'type = "command"', 'command = '+toml_value(command), 'timeout = 20']
    for name, server in mcp_servers.items():
        lines += ['', '[mcp_servers.'+name+']']
        for key in ('command', 'args', 'env', 'cwd'):
            if key in server:
                lines.append(key+' = '+toml_value(server[key]))
        if server.get('url') or server.get('httpUrl'):
            lines.append('url = '+toml_value(server.get('httpUrl') or server.get('url')))
        if server.get('headers'):
            lines.append('http_headers = '+toml_value(server['headers']))
    lines += ['', CODEX_TOML[1]]
    return '\n'.join(lines)

# --- Adapter interface ---------------------------------------------------------------------------------------------
NAME = 'codex'
LABEL = 'Codex CLI'
COMMAND = 'codex'
HOME_DIR = CODEX_DIR
BUILTIN_COMMANDS = {'skills', 'model', 'review', 'init', 'new', 'compact', 'diff', 'mention', 'status', 'mcp', 'approvals', 'logout', 'quit', 'exit', 'hooks', 'agents', 'resume'}
MANAGED_PREFIXES = (CODEX_DIR+'/skills/', CODEX_DIR+'/ai-kit/')
AGENT_TOOLS = 'instruction'  # a role file holds developer_instructions only: the session's sandbox and approvals apply
# history.jsonl holds the prompts; the session files (~/.codex/sessions) the tool calls: skill files read, agents spawned, errors.
OBSERVES = {'prompt', 'skill', 'agent', 'error'}

def is_managed(rel):
    return rel.startswith(MANAGED_PREFIXES)

def active_account(home):
    return None  # the Codex account is not read: it lives with the credentials

def doctor_hint():
    return 'Codex: check /skills in Codex and run codex doctor.' if shutil.which(COMMAND) else None

def present(home):
    return bool(shutil.which('codex')) or (home/CODEX_DIR).is_dir()

codex_present = present

def install(p: Plan) -> None:
    """Skills (with native "on command only"), command skills and agent roles."""
    codex = p.home/CODEX_DIR
    root, prefix = codex/'skills', skill_prefix(p.overrides)
    def free(name, what):
        return free_name(name, lambda n: root/n, lambda n: CODEX_DIR+'/skills/'+n, p.old_files, prefix, what)
    names = {s: free(s, 'skill') for s in p.selected}
    commands = {c['name']: free(c['name'], 'command') for c in p.commands if c['name'] not in p.selected}
    mapping = {**{o: n for o, n in names.items() if o != n}, **{o: n for o, n in commands.items() if o != n}}
    for skill, source in p.skill_sources:
        target = root/names[skill]
        for src in source.rglob('*'):
            if src.is_file():
                data = renamed_skill_file(p.skill_file(skill, source, src), src, source, mapping, names[skill] if names[skill] != skill else None)
                p.managed_write(target/src.relative_to(source), data, 'Codex skill')
        # Codex honours "on command only" through agents/openai.yaml.
        if explicit_only((source/'SKILL.md').read_text(encoding='utf-8')) and not (source/'agents'/'openai.yaml').exists():
            p.managed_write(target/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Codex skill')
    for command in p.commands:
        if command['name'] in p.selected:
            continue  # a skill with the same name serves as the command
        named = {**command, 'name': commands[command['name']], 'prompt': rename_references(command['prompt'], mapping)}
        p.managed_write(root/named['name']/'SKILL.md', command_skill_text(named).encode('utf-8'), 'Codex command skill')
        p.managed_write(root/named['name']/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Codex command skill')
    p.adapter_data.setdefault(NAME, {})['renamed'] = mapping
    notice = renamed_notice(LABEL, names, commands, '$')
    if notice:
        p.notices.append(notice)
    agents = p.adapter_data.setdefault(NAME, {}).setdefault('agents', {})
    for agent, definition in p.agents:
        name = 'ai-kit-'+agent
        role_file = codex/'ai-kit'/'agents'/(name+'.toml')
        p.managed_write(role_file, ('# AI Kit agent, managed by the kit.\ndeveloper_instructions = '+toml_value(p.agent_body(definition))+'\n').encode('utf-8'), 'Codex agent')
        agents[name] = (definition['description'], str(role_file))

def finalize(p: Plan, active: bool = True) -> None:
    """Managed blocks in ~/.codex/AGENTS.md and ~/.codex/config.toml; the rest of both files is left alone. Inactive: removes the blocks."""
    old_blocks = p.state.get('blocks', {})
    for rel, markers, position, label in ((CODEX_DIR+'/AGENTS.md', CODEX_MD, 'top', '~/.codex/AGENTS.md'), (CODEX_DIR+'/config.toml', CODEX_TOML, 'end', '~/.codex/config.toml')):
        path = p.home/rel
        text = original = path.read_text(encoding='utf-8') if path.exists() else ''
        before, old_block, after, written = read_block(text, markers, label)
        if old_block is not None and old_blocks.get(rel) != digest(normalize_newlines(written).encode('utf-8')):
            raise KitError('Kit block edited by hand in '+label+': move your changes outside the block (or into overrides.json), remove the block, then update.')
        outside = before.rstrip('\n')+('\n' if before.strip() and after.strip() else '')+after.lstrip('\n')
        block = None
        if active and rel.endswith('AGENTS.md'):
            data = p.writes.get(p.user_file) or (p.user_file.read_bytes() if p.user_file.exists() else b'')
            refusal = user_context_refusal(data)
            if refusal:
                # The source stays as it is; Codex keeps the last copy it had, and the person is told why.
                user_text = copied_user_text(old_block)
                p.notices.append('[Check] '+USER_CONTEXT+' not copied into ~/.codex/AGENTS.md: '+refusal+'. Codex keeps its previous copy'
                                 ' until the file is fixed and update runs again. The kit configuration itself is installed.')
            else:
                user_text = data.decode('utf-8')
            block = codex_context_block(p.kit_text, p.practice_texts, user_text, p.adapter_data.get(NAME, {}).get('renamed'))
        elif active:
            if p.enabled_hooks and re.search(r'^\s*(hooks\.)?PreToolUse\s*=', outside, re.M):
                raise KitError('~/.codex/config.toml already defines hooks.PreToolUse in another form: the kit cannot add its guardrails without rewriting it.')
            if re.search(r'^\s*\[\s*(agents|mcp_servers)\.ai-kit-', outside, re.M):
                raise KitError('~/.codex/config.toml already contains ai-kit- entries outside the kit block: remove them, then update.')
            hook_commands = [hook_command(p.hooks_dir/p.hook_manifest[name]['script']) for name in p.enabled_hooks]
            block = codex_config_block(p.adapter_data.get(NAME, {}).get('agents', {}), hook_commands, p.enabled_mcp)
        if block is not None:
            # Normalised line endings: a 30_USER.md edited on Windows (CRLF) must not change the digest of the block read back.
            block = normalize_newlines(block)
        new_text = place_block(outside, block, position)
        if rel.endswith('config.toml') and block is not None:
            try:
                tomllib = __import__('tomllib')  # Python 3.11+; before that, no validation and the block is written as generated
            except ImportError:
                tomllib = None
            if tomllib is not None:
                try:
                    tomllib.loads(new_text)
                except ValueError as exc:
                    raise KitError('~/.codex/config.toml would become invalid with the kit block ('+redact(str(exc))+'); nothing is written.')
        if block is not None:
            p.blocks[rel] = digest(block.encode('utf-8'))
        if new_text != original and (block is not None or old_block is not None):
            p.writes[path] = new_text.encode('utf-8')  # never deleted: the file belongs to the person

def summary(p: Plan) -> Optional[str]:
    return 'Codex: skills in ~/.codex/skills, kit blocks in ~/.codex/AGENTS.md and ~/.codex/config.toml; commands are called $intent, $build…'+(' On first launch, Codex asks you to approve the kit guardrails: answer "Trust", otherwise they do not run.' if p.enabled_hooks else '')

def doctor(home: Path, state: dict, status: Status, ctx: DoctorContext) -> None:
    blocks = state.get('blocks', {})
    if not blocks:
        return
    for rel, markers in ((CODEX_DIR+'/AGENTS.md', CODEX_MD), (CODEX_DIR+'/config.toml', CODEX_TOML)):
        path = home/rel
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        try:
            _, block, _, written = read_block(text, markers, rel)
        except KitError as exc:
            status(False, str(exc))
            continue
        status(block is not None and digest(written.encode('utf-8')) == blocks.get(rel), 'Kit block intact in ~/'+rel)
    agents_md = home/CODEX_DIR/'AGENTS.md'
    user_file = home/state.get('context_dir', '.gemini')/USER_CONTEXT
    if agents_md.exists() and user_file.exists():
        current = user_file.read_text(encoding='utf-8').strip() in agents_md.read_text(encoding='utf-8')
        status(current, 'Codex has the latest version of 30_USER.md'+('' if current else ' (run update after editing it)'))
    if (home/CODEX_DIR/'AGENTS.override.md').exists():
        status(False, '~/.codex/AGENTS.override.md exists: Codex reads it instead of AGENTS.md, the kit context is ignored')
    if state.get('hooks'):
        recorded, message = hook_approval(home)
        if recorded:
            print(message)  # never [OK]: a record found does not prove the kit's guardrails are the ones approved
        else:
            status(False, message)
    if not shutil.which('codex'):
        print('[Info] Codex set up by the kit but not on the PATH.')

def hook_approval(home):
    """(records found, message) about Codex approving the kit guardrails, never more than can be said. Codex records an
    approval under [hooks.state."<config file>:pre_tool_use:<group>:<hook>"] with a trusted_hash; the kit does not know how
    that hash is computed, nor which group indexes are its own when other hooks exist, so a record found is not proof that
    the kit's guardrails are the ones approved. No record at all means they are not approved."""
    config = home/CODEX_DIR/'config.toml'
    text = config.read_text(encoding='utf-8') if config.is_file() else ''
    records = re.findall(r'^\[hooks\.state\."(?![^"]*<session-flags>)[^"]*config\.toml:pre_tool_use:\d+:\d+"\]', text, re.M)
    if not records:
        return False, ('Codex: kit guardrails approved in Codex (not yet: no approval recorded; start codex and answer'
                       ' "Trust all and continue", otherwise they never run)')
    return True, ('[Info] Codex guardrails: approval not verifiable automatically ('+str(len(records))+' approval record(s) found,'
                  ' which may belong to other hooks). In Codex, /hooks shows what is approved; after an update that changed a'
                  ' guardrail command, Codex asks again ("Hooks need review"): answer Trust.')

LIVE_RULES = (
    (r'Not logged in|codex login|401|Unauthorized|invalid_api_key', 'Codex is not signed in, or its sign-in expired.', 'Run codex login following your IT procedure (ChatGPT account or API key).'),
    (r'usage limit|429|rate limit|quota', 'Codex quota or usage limit reached.', 'Wait for the limit to reset, or ask for a higher plan or quota.'),
    (r'model[^\n]{0,40}(not found|does not exist|not supported)|model_not_found', 'The model Codex asked for is not available on your access.', 'Choose another one with /model in codex, or in ~/.codex/config.toml (outside the kit block).'),
)

def live(home):
    """doctor --live: one real call with codex exec, read-only and ephemeral; 0 when the model answers."""
    return live_call(home, NAME, LABEL, [COMMAND, 'exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '-s', 'read-only', LIVE_PROMPT], LIVE_RULES)

def history(home, state):
    """~/.codex/history.jsonl: one line per prompt (session_id, ts in seconds, text); commands typed as $intent or /intent."""
    path = home/CODEX_DIR/'history.jsonl'
    if not path.is_file() or not any(rel.startswith(CODEX_DIR+'/skills/') for rel in state.get('files', {})):
        return
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        stamp = entry.get('ts', 0)
        if not isinstance(stamp, (int, float)):
            continue
        yield {'kind': 'prompt', 'session': ('codex:'+str(entry['session_id'])) if entry.get('session_id') else None, 'ts': stamp/1000 if stamp > 1e12 else stamp, 'text': str(entry.get('text', '')).strip()}
    yield from session_events(home, state)

def session_events(home, state):
    """~/.codex/sessions/**/rollout-*.jsonl: a kit skill counts when a tool call reads its SKILL.md, an agent when
    spawn_agent names an ai-kit-* role; error events count as errors."""
    kit_skills = set((state.get('installed') or {}).get('skills', []))
    for path in sorted((home/CODEX_DIR/'sessions').glob('**/rollout-*.jsonl')):
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        session = 'codex:'+path.stem.split('-', 6)[-1]
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            payload = entry.get('payload') if isinstance(entry, dict) else None
            if not isinstance(payload, dict):
                continue
            ts, kind = _ts(entry.get('timestamp')), payload.get('type')
            if entry.get('type') == 'session_meta' and payload.get('id'):
                session = 'codex:'+str(payload['id'])
            elif entry.get('type') == 'event_msg' and kind in ('error', 'stream_error'):
                yield {'kind': 'error', 'session': session, 'ts': ts}
            elif kind in ('function_call', 'custom_tool_call', 'local_shell_call'):
                call = str(payload.get('arguments') or payload.get('input') or payload.get('action') or '')
                if payload.get('name') == 'spawn_agent':
                    try:
                        role = str((json.loads(call) or {}).get('agent_type') or '')
                    except (ValueError, AttributeError):
                        role = ''
                    if role.startswith('ai-kit-'):
                        yield {'kind': 'agent', 'session': session, 'ts': ts, 'name': role}
                for name in skills_read(call, kit_skills):
                    yield {'kind': 'skill', 'session': session, 'ts': ts, 'name': name}
