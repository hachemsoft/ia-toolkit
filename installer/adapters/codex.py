"""Codex CLI adapter: skills in ~/.codex/skills, managed blocks in ~/.codex/AGENTS.md and ~/.codex/config.toml."""
import json
import re
import shutil

from pathlib import Path
from typing import Optional

from ..interface import DoctorContext, Plan, Status
from ..core import (USER_CONTEXT, KitError, digest, hook_command, split_block, place_block, command_skill_text)

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

def codex_context_block(kit_text, practice_texts, user_text):
    lines = [CODEX_MD[0], '# AI Kit (Codex)', '',
             'In Codex, the kit commands are skills: they are called with `$intent`, `$build`, `$test`… (`/skills` lists them). Wherever this context or a skill writes `/intent`, read `$intent`, and in your answers always write kit commands with `$` (`$intent`), never with `/`.',
             '', kit_text.strip(), '']
    lines += [t.strip()+'\n' for t in practice_texts]
    if user_text.strip():
        lines += ['<!-- Copy of 30_USER.md, refreshed by update. -->', user_text.strip(), '']
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
    for skill, source in p.skill_sources:
        for src in source.rglob('*'):
            if src.is_file():
                p.managed_write(codex/'skills'/skill/src.relative_to(source), src.read_bytes(), 'Codex skill')
        # Codex honours "on command only" through agents/openai.yaml.
        if explicit_only((source/'SKILL.md').read_text(encoding='utf-8')) and not (source/'agents'/'openai.yaml').exists():
            p.managed_write(codex/'skills'/skill/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Codex skill')
    for command in p.commands:
        if command['name'] in p.selected:
            continue  # a skill with the same name serves as the command
        p.managed_write(codex/'skills'/command['name']/'SKILL.md', command_skill_text(command).encode('utf-8'), 'Codex command skill')
        p.managed_write(codex/'skills'/command['name']/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Codex command skill')
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
            user_text = p.user_file.read_text(encoding='utf-8') if p.user_file.exists() else (p.writes.get(p.user_file) or b'').decode('utf-8')
            block = codex_context_block(p.kit_text, p.practice_texts, user_text)
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
                    raise KitError('~/.codex/config.toml would become invalid with the kit block ('+str(exc)+'); nothing is written.')
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
        config = home/CODEX_DIR/'config.toml'
        text = config.read_text(encoding='utf-8') if config.is_file() else ''
        # Codex records each approved hook under [hooks.state."<config file>:pre_tool_use:<group>:<hook>"] with a trusted_hash.
        approved = len(re.findall(r'^\[hooks\.state\."(?![^"]*<session-flags>)[^"]*config\.toml:pre_tool_use:\d+:\d+"\]', text, re.M))
        status(approved >= len(state['hooks']), 'Codex: kit guardrails approved in Codex'+('' if approved >= len(state['hooks']) else ' (not yet: start codex and answer "Trust all and continue", otherwise they never run)'))
        if approved:
            print('[Info] If Codex asks again after an update ("Hooks need review"), the guardrail command changed: answer Trust again.')
    if not shutil.which('codex'):
        print('[Info] Codex set up by the kit but not on the PATH.')

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
